#!/usr/bin/env python3
"""
FalconOps AI - Database Monitoring Agent v2.0.0
Lightweight external agent that collects REAL database metrics and pushes them to the FalconOps API.
Supports: PostgreSQL (psycopg2), MySQL (pymysql), Oracle (python-oracledb, thin mode — no
Instant Client required), SQL Server (pyodbc — requires the msodbcsql ODBC driver on this host).

Every metric below is either a real value read from the database's own system views, or `None`
when it genuinely can't be obtained (missing extension, insufficient privilege, not applicable
to this topology e.g. not a replica — see the inline comment at each such field for why). This
agent never fabricates a number to fill a gap — a missing metric on the FalconOps dashboard is
honest; a random one is not.

Usage:
    python3 falcon_db_agent.py --config /etc/falconops/db_agent.yaml
    python3 falcon_db_agent.py --config /etc/falconops/db_agent.yaml --dry-run --once
    python3 falcon_db_agent.py --config /etc/falconops/db_agent.yaml --simulate --once   # demo mode, explicit opt-in only
"""
import os
import sys
import time
import json
import argparse
import logging
import random
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("falcon-db-agent")

VERSION = "2.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# Optional drivers — only the one matching this agent's configured db.type needs
# to actually be installed (the install script installs exactly one). Importing
# lazily here means a missing driver only breaks the engine that needs it, not
# every engine.
# ─────────────────────────────────────────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

try:
    import pymysql
    import pymysql.cursors
    _HAS_MYSQL = True
except ImportError:
    _HAS_MYSQL = False

try:
    import oracledb
    _HAS_ORACLE = True
except ImportError:
    _HAS_ORACLE = False

try:
    import pyodbc
    _HAS_MSSQL = True
except ImportError:
    _HAS_MSSQL = False


def load_config(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        with open(path) as f:
            return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Rate tracker — several real metrics (TPS, IO ms/op, Oracle/SQL-Server CPU%)
# are only meaningful as a delta between two samples over time, not a single
# point-in-time read. This agent runs as a persistent loop (one process, one
# `while True`), so an in-memory previous-sample cache is enough — no need for
# a state file. First sample after (re)start always returns None for any
# rate-based metric: there is no prior sample to diff against yet, and a
# guessed "first value" would be exactly the kind of fabrication this rewrite
# is trying to eliminate.
# ─────────────────────────────────────────────────────────────────────────────
class RateTracker:
    def __init__(self):
        self._prev = {}

    def rate_per_sec(self, key, cumulative_value, now=None):
        now = now or time.monotonic()
        prev = self._prev.get(key)
        self._prev[key] = (cumulative_value, now)
        if prev is None:
            return None
        prev_value, prev_time = prev
        dt = now - prev_time
        if dt <= 0 or cumulative_value < prev_value:
            # Counter reset (DB restarted) or clock oddity — don't report a
            # nonsensical negative/inf rate, wait for the next clean sample.
            return None
        return (cumulative_value - prev_value) / dt

    def delta(self, key, cumulative_value, now=None):
        """Like rate_per_sec but returns the raw delta, not divided by time —
        used where the caller wants delta-of-a-delta (e.g. avg ms/op needs
        both the cumulative-time delta AND the cumulative-count delta)."""
        now = now or time.monotonic()
        prev = self._prev.get(key)
        self._prev[key] = (cumulative_value, now)
        if prev is None:
            return None
        prev_value, _ = prev
        d = cumulative_value - prev_value
        return d if d >= 0 else None


_rates = RateTracker()


def _empty_metrics():
    """Every field defaults to None ('not measured'), not 0 or a fabricated
    number — each collector fills in only what it could actually obtain."""
    return {
        "active_sessions": None, "total_connections": None, "cpu_usage": None,
        "memory_usage": None, "tps": None, "cache_hit_ratio": None,
        "io_read_ms": None, "io_write_ms": None, "db_size_bytes": None,
        "replication_lag_ms": None, "agent_version": VERSION,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────
def collect_postgres(cfg):
    if not _HAS_PG:
        raise RuntimeError("psycopg2 is not installed — run: pip install psycopg2-binary")

    conn = psycopg2.connect(
        host=cfg["host"], port=cfg.get("port", 5432), user=cfg["username"],
        password=cfg["password"], dbname=cfg["database"], connect_timeout=10,
    )
    metrics = _empty_metrics()
    slow_queries, locks = [], []
    try:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE state = 'active'")
        metrics["active_sessions"] = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM pg_stat_activity")
        metrics["total_connections"] = cur.fetchone()["n"]

        cur.execute("""
            SELECT sum(xact_commit) AS commits, sum(xact_rollback) AS rollbacks,
                   sum(blks_hit) AS blks_hit, sum(blks_read) AS blks_read,
                   sum(blk_read_time) AS read_ms, sum(blk_write_time) AS write_ms
            FROM pg_stat_database
        """)
        row = cur.fetchone()
        # Postgres's sum() over a bigint column returns numeric, which psycopg2 maps to
        # Decimal — cast to float immediately so nothing Decimal-typed reaches the JSON
        # payload later (stdlib json.dumps doesn't know how to serialize Decimal).
        commits, rollbacks = float(row["commits"] or 0), float(row["rollbacks"] or 0)
        hit, read = float(row["blks_hit"] or 0), float(row["blks_read"] or 0)
        read_ms_raw = float(row["read_ms"] or 0)

        rate = _rates.rate_per_sec(("pg", cfg["host"], "xacts"), commits + rollbacks)
        metrics["tps"] = round(rate) if rate is not None else None

        metrics["cache_hit_ratio"] = round(hit / (hit + read) * 100, 2) if (hit + read) > 0 else None

        # blk_read_time/blk_write_time are cumulative ms and only populated when
        # track_io_timing is on (server default is OFF) — 0 for both is
        # ambiguous (could mean "no IO" or "timing disabled"), so we check the
        # server setting explicitly rather than guess.
        cur.execute("SHOW track_io_timing")
        io_timing_on = cur.fetchone()["track_io_timing"] == "on"
        if io_timing_on:
            read_delta = _rates.delta(("pg", cfg["host"], "read_ms"), read_ms_raw)
            read_blk_delta = _rates.delta(("pg", cfg["host"], "read_blks"), read)
            metrics["io_read_ms"] = round(read_delta / read_blk_delta, 3) if read_delta and read_blk_delta else None
            # io_write_ms deliberately left None: pg_stat_database.blk_write_time has no
            # matching per-database write-block counter to divide by (pg_stat_bgwriter's
            # buffer-write counts are cluster-wide, a different scope) — reporting a
            # cumulative ms figure under the same "ms per operation" label the other three
            # engines use for this field would be comparing different units silently.
        # else: leave both None — track_io_timing is off, not "0ms of IO"

        cur.execute("SELECT pg_database_size(current_database()) AS sz")
        metrics["db_size_bytes"] = cur.fetchone()["sz"]

        cur.execute("SELECT pg_is_in_recovery() AS standby")
        if cur.fetchone()["standby"]:
            cur.execute("SELECT extract(epoch FROM now() - pg_last_xact_replay_timestamp()) * 1000 AS lag_ms")
            r = cur.fetchone()
            metrics["replication_lag_ms"] = round(r["lag_ms"], 1) if r["lag_ms"] is not None else None
        # else: this instance is a primary, not a replica — lag is genuinely N/A, not 0.

        # cpu_usage / memory_usage: Postgres has no built-in system view for host-level
        # CPU/RAM without an extension (pg_stat_kcache, external exporter). Left None
        # rather than guessed — a real limitation of SQL-only Postgres monitoring.

        try:
            cur.execute("""
                SELECT query, calls, round(mean_exec_time::numeric, 1) AS duration_ms,
                       round((total_exec_time)::numeric, 1) AS total_ms
                FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10
            """)
            for r in cur.fetchall():
                slow_queries.append({
                    "query": r["query"][:500], "duration_ms": float(r["duration_ms"] or 0),
                    "calls": r["calls"], "user": None, "fingerprint": r["query"][:200],
                })
        except Exception:
            # pg_stat_statements extension not installed — honestly empty, logged once.
            logger.info("pg_stat_statements not available — slow-query capture disabled "
                        "(run: CREATE EXTENSION pg_stat_statements; as superuser to enable)")

        cur.execute("""
            SELECT pid, mode, locktype, granted
            FROM pg_locks WHERE NOT granted LIMIT 20
        """)
        for r in cur.fetchall():
            locks.append({"pid": r["pid"], "mode": r["mode"], "locktype": r["locktype"], "granted": r["granted"]})
    finally:
        conn.close()

    return {"metrics": metrics, "slow_queries": slow_queries, "locks": locks}


# ─────────────────────────────────────────────────────────────────────────────
# MySQL
# ─────────────────────────────────────────────────────────────────────────────
def collect_mysql(cfg):
    if not _HAS_MYSQL:
        raise RuntimeError("pymysql is not installed — run: pip install pymysql")

    conn = pymysql.connect(
        host=cfg["host"], port=cfg.get("port", 3306), user=cfg["username"],
        password=cfg["password"], database=cfg["database"], connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )
    metrics = _empty_metrics()
    slow_queries, locks = [], []
    try:
        cur = conn.cursor()

        def status(name):
            cur.execute("SHOW GLOBAL STATUS LIKE %s", (name,))
            r = cur.fetchone()
            return int(r["Value"]) if r else None

        metrics["total_connections"] = status("Threads_connected")
        cur.execute("SELECT count(*) AS n FROM information_schema.processlist WHERE command != 'Sleep'")
        metrics["active_sessions"] = cur.fetchone()["n"]

        commits, rollbacks = status("Com_commit"), status("Com_rollback")
        if commits is not None and rollbacks is not None:
            rate = _rates.rate_per_sec(("mysql", cfg["host"], "xacts"), commits + rollbacks)
            metrics["tps"] = round(rate) if rate is not None else None

        read_requests, reads = status("Innodb_buffer_pool_read_requests"), status("Innodb_buffer_pool_reads")
        if read_requests and read_requests > 0:
            metrics["cache_hit_ratio"] = round((1 - (reads or 0) / read_requests) * 100, 2)

        cur.execute("SELECT SUM(data_length + index_length) AS sz FROM information_schema.tables WHERE table_schema = %s",
                    (cfg["database"],))
        sz = cur.fetchone()["sz"]
        # MySQL's SUM() over exact-value (int/bigint) columns returns DECIMAL, which pymysql
        # maps to Python Decimal — cast so this stays JSON-serializable like everything else.
        metrics["db_size_bytes"] = int(sz) if sz is not None else None

        try:
            cur.execute("SHOW SLAVE STATUS")
            r = cur.fetchone()
            if r and r.get("Seconds_Behind_Master") is not None:
                metrics["replication_lag_ms"] = int(r["Seconds_Behind_Master"]) * 1000
            # else: not a replica — N/A, not 0.
        except Exception:
            pass  # SHOW SLAVE STATUS needs REPLICATION CLIENT priv — left None if denied.

        try:
            cur.execute("""
                SELECT DIGEST_TEXT AS query, COUNT_STAR AS calls,
                       ROUND(AVG_TIMER_WAIT / 1000000000, 1) AS duration_ms
                FROM performance_schema.events_statements_summary_by_digest
                WHERE DIGEST_TEXT IS NOT NULL
                ORDER BY AVG_TIMER_WAIT DESC LIMIT 10
            """)
            for r in cur.fetchall():
                slow_queries.append({
                    "query": (r["query"] or "")[:500], "duration_ms": float(r["duration_ms"] or 0),
                    "calls": r["calls"], "user": None, "fingerprint": (r["query"] or "")[:200],
                })
        except Exception:
            logger.info("performance_schema statement digest not available — slow-query capture disabled "
                        "(requires performance_schema=ON, default in MySQL 5.7+/8.0+)")

        try:
            cur.execute("""
                SELECT waiting_pid AS pid, 'row_lock' AS mode
                FROM sys.innodb_lock_waits LIMIT 20
            """)
            for r in cur.fetchall():
                locks.append({"pid": r["pid"], "mode": r["mode"], "locktype": "innodb", "granted": False})
        except Exception:
            pass  # sys schema view not present on older MySQL — left empty, not fabricated.

        # cpu_usage / memory_usage: not obtainable from MySQL system views without an
        # external OS-level agent — left None (same real limitation as Postgres).
    finally:
        conn.close()

    return {"metrics": metrics, "slow_queries": slow_queries, "locks": locks}


# ─────────────────────────────────────────────────────────────────────────────
# Oracle — python-oracledb in "thin" mode talks the Oracle wire protocol
# directly, no Oracle Instant Client install required for standard connections.
# ─────────────────────────────────────────────────────────────────────────────
def collect_oracle(cfg):
    if not _HAS_ORACLE:
        raise RuntimeError("oracledb is not installed — run: pip install oracledb")

    dsn = f"{cfg['host']}:{cfg.get('port', 1521)}/{cfg['database']}"
    conn = oracledb.connect(user=cfg["username"], password=cfg["password"], dsn=dsn)
    metrics = _empty_metrics()
    slow_queries, locks = [], []
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE' AND type = 'USER'")
        metrics["active_sessions"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM v$session WHERE type = 'USER'")
        metrics["total_connections"] = cur.fetchone()[0]

        cur.execute("SELECT name, value FROM v$sysstat WHERE name IN ('user commits', 'user rollbacks')")
        stats = dict(cur.fetchall())
        total_xacts = int(stats.get("user commits", 0) + stats.get("user rollbacks", 0))
        rate = _rates.rate_per_sec(("ora", cfg["host"], "xacts"), total_xacts)
        metrics["tps"] = round(rate) if rate is not None else None

        cur.execute("SELECT name, value FROM v$sysstat WHERE name IN ('session logical reads', 'physical reads')")
        stats = dict(cur.fetchall())
        logical, physical = stats.get("session logical reads", 0), stats.get("physical reads", 0)
        metrics["cache_hit_ratio"] = round((1 - physical / logical) * 100, 2) if logical > 0 else None

        cur.execute("""
            SELECT event, average_wait_micro FROM v$system_event
            WHERE event IN ('db file sequential read', 'db file scattered read', 'db file parallel write')
        """)
        # average_wait_micro is exact microseconds since it was added (9i+) — used instead
        # of the legacy average_wait, whose unit (centiseconds vs hundredths-of-a-second)
        # has been inconsistently documented across Oracle versions.
        wait_stats = dict(cur.fetchall())
        reads = [v for k, v in wait_stats.items() if 'read' in k]
        if reads:
            metrics["io_read_ms"] = round(sum(reads) / len(reads) / 1000, 3)
        if 'db file parallel write' in wait_stats:
            metrics["io_write_ms"] = round(wait_stats['db file parallel write'] / 1000, 3)

        try:
            cur.execute("SELECT SUM(bytes) FROM dba_data_files")
            metrics["db_size_bytes"] = cur.fetchone()[0]
        except Exception:
            # dba_data_files needs a privileged role — fall back to what this user owns.
            try:
                cur.execute("SELECT SUM(bytes) FROM user_segments")
                metrics["db_size_bytes"] = cur.fetchone()[0]
            except Exception:
                pass

        try:
            cur.execute("SELECT value FROM v$dataguard_stats WHERE name = 'apply lag'")
            r = cur.fetchone()
            if r and r[0]:
                # Format is typically '+00 00:00:03' (interval day to second) — parse seconds.
                import re as _re
                m = _re.search(r"(\d+)\s+(\d+):(\d+):(\d+)", r[0])
                if m:
                    d, h, mi, s = (int(x) for x in m.groups())
                    metrics["replication_lag_ms"] = ((d * 86400) + (h * 3600) + (mi * 60) + s) * 1000
        except Exception:
            pass  # not a Data Guard standby, or view not accessible — N/A, not 0.

        # Oracle DOES expose real host CPU via v$osstat — genuinely obtainable, unlike
        # Postgres/MySQL. Two-sample delta of BUSY_TIME vs total (BUSY_TIME + IDLE_TIME).
        try:
            cur.execute("SELECT stat_name, value FROM v$osstat WHERE stat_name IN ('BUSY_TIME', 'IDLE_TIME')")
            os_stats = dict(cur.fetchall())
            busy_delta = _rates.delta(("ora", cfg["host"], "busy"), os_stats.get("BUSY_TIME", 0))
            idle_delta = _rates.delta(("ora", cfg["host"], "idle"), os_stats.get("IDLE_TIME", 0))
            if busy_delta is not None and idle_delta is not None and (busy_delta + idle_delta) > 0:
                metrics["cpu_usage"] = round(busy_delta / (busy_delta + idle_delta) * 100, 1)
        except Exception:
            pass  # v$osstat needs SELECT_CATALOG_ROLE or similar — left None if denied.

        try:
            # V$SQL (shared-pool cache), not AWR — avoids requiring the licensed
            # Diagnostics/Tuning Pack that ASH/AWR-based slow-query views need.
            cur.execute("""
                SELECT sql_text, executions,
                       ROUND(elapsed_time / GREATEST(executions, 1) / 1000, 1) AS avg_ms
                FROM v$sql WHERE executions > 0
                ORDER BY elapsed_time / GREATEST(executions, 1) DESC
                FETCH FIRST 10 ROWS ONLY
            """)
            for sql_text, executions, avg_ms in cur.fetchall():
                slow_queries.append({
                    "query": (sql_text or "")[:500], "duration_ms": float(avg_ms or 0),
                    "calls": executions, "user": None, "fingerprint": (sql_text or "")[:200],
                })
        except Exception:
            logger.info("v$sql not accessible — slow-query capture disabled (needs SELECT on v$sql)")

        try:
            cur.execute("""
                SELECT s.sid, l.type, DECODE(l.block, 1, 'BLOCKING', 'WAITING') AS mode
                FROM v$lock l JOIN v$session s ON l.sid = s.sid
                WHERE l.block = 1 OR l.request > 0
                FETCH FIRST 20 ROWS ONLY
            """)
            for sid, ltype, mode in cur.fetchall():
                locks.append({"pid": sid, "mode": mode, "locktype": ltype, "granted": mode == "BLOCKING"})
        except Exception:
            pass
    finally:
        conn.close()

    return {"metrics": metrics, "slow_queries": slow_queries, "locks": locks}


# ─────────────────────────────────────────────────────────────────────────────
# SQL Server — pyodbc requires the msodbcsql ODBC driver installed on this
# host (a real native dependency, unlike Oracle's thin-mode driver above).
# The generated install script (see db_monitoring.py) installs it via apt/yum
# for sqlserver targets.
# ─────────────────────────────────────────────────────────────────────────────
def collect_sqlserver(cfg):
    if not _HAS_MSSQL:
        raise RuntimeError("pyodbc is not installed — run: pip install pyodbc "
                            "(and install the 'msodbcsql18' ODBC driver package for your OS)")

    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={cfg['host']},{cfg.get('port', 1433)};"
        f"DATABASE={cfg['database']};UID={cfg['username']};PWD={cfg['password']};"
        f"TrustServerCertificate=yes;Connection Timeout=10"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    metrics = _empty_metrics()
    slow_queries, locks = [], []
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE status = 'running' AND is_user_process = 1")
        metrics["active_sessions"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process = 1")
        metrics["total_connections"] = cur.fetchone()[0]

        cur.execute("""
            SELECT cntr_value FROM sys.dm_os_performance_counters
            WHERE counter_name = 'Transactions/sec' AND instance_name = '_Total'
        """)
        r = cur.fetchone()
        if r:
            rate = _rates.rate_per_sec(("mssql", cfg["host"], "xacts"), r[0])
            metrics["tps"] = round(rate) if rate is not None else None

        cur.execute("""
            SELECT counter_name, cntr_value FROM sys.dm_os_performance_counters
            WHERE counter_name IN ('Buffer cache hit ratio', 'Buffer cache hit ratio base')
        """)
        bch = dict(cur.fetchall())
        base = bch.get("Buffer cache hit ratio base")
        if base:
            metrics["cache_hit_ratio"] = round(bch.get("Buffer cache hit ratio", 0) / base * 100, 2)

        cur.execute("""
            SELECT SUM(num_of_reads) AS reads, SUM(io_stall_read_ms) AS read_ms,
                   SUM(num_of_writes) AS writes, SUM(io_stall_write_ms) AS write_ms
            FROM sys.dm_io_virtual_file_stats(DB_ID(), NULL)
        """)
        row = cur.fetchone()
        read_delta = _rates.delta(("mssql", cfg["host"], "read_ms"), row.read_ms or 0)
        reads_delta = _rates.delta(("mssql", cfg["host"], "reads"), row.reads or 0)
        write_delta = _rates.delta(("mssql", cfg["host"], "write_ms"), row.write_ms or 0)
        writes_delta = _rates.delta(("mssql", cfg["host"], "writes"), row.writes or 0)
        metrics["io_read_ms"] = round(read_delta / reads_delta, 3) if read_delta and reads_delta else None
        metrics["io_write_ms"] = round(write_delta / writes_delta, 3) if write_delta and writes_delta else None

        cur.execute("SELECT SUM(CAST(size AS BIGINT)) * 8.0 * 1024 FROM sys.master_files WHERE database_id = DB_ID()")
        metrics["db_size_bytes"] = int(cur.fetchone()[0] or 0)

        try:
            cur.execute("""
                SELECT secondary_lag_seconds FROM sys.dm_hadr_database_replica_states
                WHERE database_id = DB_ID() AND is_local = 1
            """)
            r = cur.fetchone()
            if r and r[0] is not None:
                metrics["replication_lag_ms"] = int(r[0]) * 1000
        except Exception:
            pass  # not in an Availability Group — N/A, not 0.

        # Well-known real technique: SystemIdle/SQLProcessUtilization are self-reported
        # by SQL Server's own scheduler monitor ring buffer — genuine host CPU%, not a guess.
        try:
            cur.execute("""
                SELECT TOP 1 record FROM sys.dm_os_ring_buffer_scheduler_monitor
                WHERE ring_buffer_type = 'RING_BUFFER_SCHEDULER_MONITOR' ORDER BY timestamp DESC
            """)
            r = cur.fetchone()
            if r:
                import re as _re
                m = _re.search(r"<SystemIdle>(\d+)</SystemIdle>", r[0])
                if m:
                    metrics["cpu_usage"] = round(100 - int(m.group(1)), 1)
        except Exception:
            pass

        try:
            cur.execute("""
                SELECT physical_memory_in_use_kb FROM sys.dm_os_process_memory
            """)
            used_kb = cur.fetchone()[0]
            cur.execute("SELECT total_physical_memory_kb FROM sys.dm_os_sys_memory")
            total_kb = cur.fetchone()[0]
            if total_kb:
                metrics["memory_usage"] = round(used_kb / total_kb * 100, 1)
        except Exception:
            pass

        try:
            cur.execute("""
                SELECT TOP 10 SUBSTRING(st.text, 1, 500) AS query, qs.execution_count,
                       CAST(qs.total_elapsed_time / 1000.0 / GREATEST(qs.execution_count, 1) AS DECIMAL(18,1)) AS avg_ms
                FROM sys.dm_exec_query_stats qs
                CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
                ORDER BY qs.total_elapsed_time / GREATEST(qs.execution_count, 1) DESC
            """)
            for query, execution_count, avg_ms in cur.fetchall():
                slow_queries.append({
                    "query": query or "", "duration_ms": float(avg_ms or 0),
                    "calls": execution_count, "user": None, "fingerprint": (query or "")[:200],
                })
        except Exception:
            logger.info("dm_exec_query_stats not accessible — slow-query capture disabled "
                        "(needs VIEW SERVER STATE permission)")

        try:
            cur.execute("""
                SELECT request_session_id, resource_type, request_status
                FROM sys.dm_tran_locks WHERE request_status = 'WAIT'
            """)
            for sid, rtype, status in cur.fetchmany(20):
                locks.append({"pid": sid, "mode": status, "locktype": rtype, "granted": False})
        except Exception:
            pass
    finally:
        conn.close()

    return {"metrics": metrics, "slow_queries": slow_queries, "locks": locks}


# ─────────────────────────────────────────────────────────────────────────────
# Demo-only fake data — never called automatically. Only reachable via the
# explicit --simulate flag, so a real deployment can never silently end up
# here just because a driver import failed or a connection errored.
# ─────────────────────────────────────────────────────────────────────────────
def collect_simulated(cfg):
    return {
        "metrics": {
            "active_sessions": random.randint(5, 120),
            "total_connections": random.randint(20, 300),
            "cpu_usage": round(random.uniform(10, 85), 1),
            "memory_usage": round(random.uniform(30, 90), 1),
            "tps": random.randint(50, 2000),
            "cache_hit_ratio": round(random.uniform(85, 99.9), 2),
            "io_read_ms": round(random.uniform(0.5, 15), 2),
            "io_write_ms": round(random.uniform(0.5, 10), 2),
            "db_size_bytes": random.randint(100000000, 50000000000),
            "replication_lag_ms": round(random.uniform(0, 500), 1),
            "agent_version": VERSION,
        },
        "slow_queries": [
            {
                "query": "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at",
                "duration_ms": round(random.uniform(500, 5000), 1),
                "calls": random.randint(10, 500),
                "user": "app_user",
                "fingerprint": "SELECT * FROM orders WHERE status = ?",
            }
        ] if random.random() > 0.5 else [],
        "locks": [],
    }


_COLLECTORS = {
    "postgres": collect_postgres, "postgresql": collect_postgres,
    "mysql": collect_mysql,
    "oracle": collect_oracle,
    "sqlserver": collect_sqlserver, "mssql": collect_sqlserver,
}


def collect(db_cfg, simulate=False):
    if simulate:
        return collect_simulated(db_cfg)
    db_type = (db_cfg.get("type") or "").lower()
    fn = _COLLECTORS.get(db_type)
    if fn is None:
        raise RuntimeError(f"Unknown database.type '{db_type}' — expected one of: "
                            f"{sorted(set(_COLLECTORS))}")
    return fn(db_cfg)


def push_metrics(api_url, api_key, instance_id, data):
    url = f"{api_url}/api/db-monitoring/metrics/ingest"
    payload = {
        "instance_id": instance_id,
        "metrics": data["metrics"],
        "slow_queries": data.get("slow_queries", []),
        "locks": data.get("locks", []),
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="FalconOps DB Monitoring Agent")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--simulate", action="store_true",
                         help="Demo/test mode ONLY — pushes fabricated random metrics instead of "
                              "connecting to a real database. Never used automatically.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_cfg = cfg.get("database", {})
    api_cfg = cfg.get("api", {})
    interval = cfg.get("collection_interval", 60)

    logger.info(f"FalconOps DB Agent v{VERSION} starting "
                f"(type={db_cfg.get('type')}, interval={interval}s, simulate={args.simulate})")

    while True:
        try:
            data = collect(db_cfg, simulate=args.simulate)
            if args.dry_run:
                logger.info(f"[DRY RUN] {json.dumps(data, indent=2, default=str)}")
            else:
                result = push_metrics(api_cfg.get("endpoint", ""), api_cfg.get("key", ""), api_cfg.get("instance_id", ""), data)
                logger.info(f"Pushed: {result}")
        except Exception as e:
            # A failed collection cycle pushes nothing rather than a fabricated
            # or zeroed reading — a gap in the FalconOps dashboard is the honest
            # signal that something (connectivity, credentials, permissions) is wrong.
            logger.error(f"Collection failed: {e}")

        if args.once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
