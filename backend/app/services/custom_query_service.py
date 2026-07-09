"""
FalconOps AI - Custom Query Monitoring Service
Handles execution simulation, result storage, and time-series data for custom database queries.
"""
import uuid
import random
import math
from datetime import datetime, timezone, timedelta

from ..core.database import db


async def execute_query_simulation(query_doc: dict) -> dict:
    """Simulate executing a custom SQL query and return results."""
    query_text = query_doc.get("query", "").lower()
    query_name = query_doc.get("name", "")
    
    # Determine result shape based on query pattern
    result = _generate_simulated_result(query_text, query_name)
    
    execution_doc = {
        "id": str(uuid.uuid4()),
        "query_id": query_doc["id"],
        "instance_id": query_doc["instance_id"],
        "query_name": query_name,
        "query_text": query_doc.get("query", ""),
        "status": "success",
        "duration_ms": round(random.uniform(5, 800), 2),
        "rows_returned": result.get("row_count", 0),
        "value": result.get("value"),
        "values": result.get("values", {}),
        "raw_rows": result.get("raw_rows", []),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.db_custom_results.insert_one({**execution_doc})
    execution_doc.pop("_id", None)
    return execution_doc


def _generate_simulated_result(query_text: str, query_name: str) -> dict:
    """Generate realistic simulated query results based on query patterns."""
    now = datetime.now(timezone.utc)
    
    # Pattern: COUNT queries -> single numeric value
    if "count(" in query_text or "count (*" in query_text:
        val = random.randint(10, 5000)
        return {"value": val, "row_count": 1, "values": {"count": val}}
    
    # Pattern: AVG/SUM/MAX/MIN aggregate
    if any(agg in query_text for agg in ["avg(", "sum(", "max(", "min("]):
        val = round(random.uniform(0.5, 99.9), 2)
        return {"value": val, "row_count": 1, "values": {"result": val}}
    
    # Pattern: table_size / database_size
    if "pg_size" in query_text or "table_size" in query_text or "database_size" in query_name.lower():
        val = round(random.uniform(100, 50000), 1)
        return {"value": val, "row_count": 1, "values": {"size_mb": val}}
    
    # Pattern: connection count
    if "pg_stat_activity" in query_text or "connection" in query_name.lower():
        active = random.randint(5, 120)
        idle = random.randint(10, 200)
        waiting = random.randint(0, 15)
        return {
            "value": active + idle + waiting,
            "row_count": 1,
            "values": {"active": active, "idle": idle, "waiting": waiting},
        }
    
    # Pattern: replication lag
    if "replication" in query_text or "lag" in query_name.lower():
        lag = round(random.uniform(0, 5.0), 3)
        return {"value": lag, "row_count": 1, "values": {"lag_seconds": lag}}
    
    # Pattern: cache/hit ratio
    if "cache" in query_text or "hit_ratio" in query_name.lower() or "hit ratio" in query_name.lower():
        ratio = round(random.uniform(92, 99.9), 2)
        return {"value": ratio, "row_count": 1, "values": {"hit_ratio_pct": ratio}}
    
    # Pattern: deadlock/lock
    if "deadlock" in query_text or "lock" in query_name.lower():
        val = random.randint(0, 8)
        return {"value": val, "row_count": 1, "values": {"lock_count": val}}
    
    # Pattern: transactions per second
    if "xact" in query_text or "transaction" in query_name.lower() or "tps" in query_name.lower():
        val = random.randint(50, 3000)
        return {"value": val, "row_count": 1, "values": {"tps": val}}
    
    # Pattern: table row counts (multi-row)
    if "information_schema" in query_text or "pg_stat_user_tables" in query_text:
        tables = ["users", "orders", "products", "sessions", "audit_logs", "payments"]
        rows = [{"table_name": t, "row_count": random.randint(100, 500000)} for t in tables[:random.randint(3, 6)]]
        return {"value": sum(r["row_count"] for r in rows), "row_count": len(rows), "values": {"total_rows": sum(r["row_count"] for r in rows)}, "raw_rows": rows}
    
    # Default: single numeric
    val = round(random.uniform(1, 1000), 2)
    return {"value": val, "row_count": 1, "values": {"result": val}}


async def get_query_timeseries(query_id: str, hours: int = 24) -> list:
    """Get time-series results for a specific custom query."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    results = await db.db_custom_results.find(
        {"query_id": query_id, "executed_at": {"$gte": since}},
        {"_id": 0}
    ).sort("executed_at", 1).to_list(length=500)
    return results


async def get_dashboard_widgets(instance_id: str, hours: int = 24) -> list:
    """Get all custom query widgets with their latest data for the dashboard."""
    queries = await db.db_custom_queries.find(
        {"instance_id": instance_id}, {"_id": 0}
    ).to_list(length=50)
    
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    widgets = []
    for q in queries:
        # Get latest result
        latest = await db.db_custom_results.find_one(
            {"query_id": q["id"]},
            {"_id": 0},
            sort=[("executed_at", -1)]
        )
        
        # Get time-series for chart
        results = await db.db_custom_results.find(
            {"query_id": q["id"], "executed_at": {"$gte": since}},
            {"_id": 0}
        ).sort("executed_at", 1).to_list(length=200)
        
        # Get execution stats
        total_execs = await db.db_custom_results.count_documents({"query_id": q["id"]})
        
        widgets.append({
            "query": q,
            "latest_result": latest,
            "timeseries": results,
            "total_executions": total_execs,
        })
    
    return widgets


async def seed_custom_queries(instance_id: str) -> dict:
    """Seed demo custom queries and historical results for an instance."""
    
    sample_queries = [
        {
            "name": "Active Connections",
            "query": "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';",
            "interval": 30,
            "chart_type": "line",
            "description": "Monitor active database connections",
            "unit": "connections",
            "color": "#00E0FF",
        },
        {
            "name": "Cache Hit Ratio",
            "query": "SELECT round(sum(blks_hit)*100/sum(blks_hit+blks_read),2) AS hit_ratio FROM pg_stat_database;",
            "interval": 60,
            "chart_type": "area",
            "description": "Database buffer cache hit ratio percentage",
            "unit": "%",
            "color": "#10B981",
        },
        {
            "name": "Transaction Rate",
            "query": "SELECT sum(xact_commit+xact_rollback) AS total_xact FROM pg_stat_database;",
            "interval": 30,
            "chart_type": "bar",
            "description": "Transactions per collection interval",
            "unit": "txn",
            "color": "#8B5CF6",
        },
        {
            "name": "Dead Tuples Count",
            "query": "SELECT sum(n_dead_tup) FROM pg_stat_user_tables;",
            "interval": 120,
            "chart_type": "line",
            "description": "Total dead tuples needing vacuum",
            "unit": "tuples",
            "color": "#F59E0B",
        },
        {
            "name": "Database Size",
            "query": "SELECT pg_database_size(current_database())/1024/1024 AS size_mb;",
            "interval": 300,
            "chart_type": "area",
            "description": "Current database size in megabytes",
            "unit": "MB",
            "color": "#EC4899",
        },
        {
            "name": "Replication Lag",
            "query": "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag_seconds;",
            "interval": 30,
            "chart_type": "line",
            "description": "Streaming replication lag in seconds",
            "unit": "sec",
            "color": "#EF4444",
        },
    ]
    
    created_queries = []
    total_results = 0
    now = datetime.now(timezone.utc)
    
    for sq in sample_queries:
        query_id = str(uuid.uuid4())
        query_doc = {
            "id": query_id,
            "instance_id": instance_id,
            "name": sq["name"],
            "query": sq["query"],
            "interval": sq["interval"],
            "chart_type": sq.get("chart_type", "line"),
            "description": sq.get("description", ""),
            "unit": sq.get("unit", ""),
            "color": sq.get("color", "#00E0FF"),
            "enabled": True,
            "created_at": now.isoformat(),
        }
        await db.db_custom_queries.insert_one({**query_doc})
        query_doc.pop("_id", None)
        created_queries.append(query_doc)
        
        # Generate historical results (last 24 hours)
        results_to_insert = []
        base_value = _get_base_value(sq["name"])
        
        for i in range(96):  # ~15 min intervals over 24h
            ts = now - timedelta(minutes=15 * (96 - i))
            # Generate realistic time-series with trends and noise
            hour_of_day = ts.hour
            # Daily pattern: peak during business hours
            daily_factor = 1.0 + 0.3 * math.sin(math.pi * (hour_of_day - 6) / 12) if 6 <= hour_of_day <= 18 else 0.7
            noise = random.gauss(0, base_value * 0.08)
            trend = i * base_value * 0.001  # Slight upward trend
            value = max(0, round(base_value * daily_factor + noise + trend, 2))
            
            result_doc = {
                "id": str(uuid.uuid4()),
                "query_id": query_id,
                "instance_id": instance_id,
                "query_name": sq["name"],
                "query_text": sq["query"],
                "status": "success",
                "duration_ms": round(random.uniform(3, 200), 2),
                "rows_returned": 1,
                "value": value,
                "values": {_get_value_key(sq["name"]): value},
                "executed_at": ts.isoformat(),
            }
            results_to_insert.append(result_doc)
        
        if results_to_insert:
            await db.db_custom_results.insert_many(results_to_insert)
            total_results += len(results_to_insert)
    
    return {
        "queries_created": len(created_queries),
        "results_seeded": total_results,
        "queries": created_queries,
    }


def _get_base_value(name: str) -> float:
    """Get a realistic base value for a metric type."""
    mapping = {
        "Active Connections": 45,
        "Cache Hit Ratio": 97.5,
        "Transaction Rate": 850,
        "Dead Tuples Count": 12000,
        "Database Size": 2500,
        "Replication Lag": 0.3,
    }
    return mapping.get(name, 50)


def _get_value_key(name: str) -> str:
    """Get the result value key for a metric type."""
    mapping = {
        "Active Connections": "count",
        "Cache Hit Ratio": "hit_ratio_pct",
        "Transaction Rate": "tps",
        "Dead Tuples Count": "dead_tuples",
        "Database Size": "size_mb",
        "Replication Lag": "lag_seconds",
    }
    return mapping.get(name, "result")
