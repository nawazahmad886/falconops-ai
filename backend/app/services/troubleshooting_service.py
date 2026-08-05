"""
FalconOps AI — Troubleshooting Command Center.

Read-only diagnostics only — every command in COMMAND_CATALOG is risk="low"
by design (no restart/scale/delete here; those already exist as RASED/
remediation actions with their own approval gates). Scoping note, disclosed
rather than hidden: this does NOT execute arbitrary commands against
arbitrary customer infrastructure — that "remote exec agent on any host" model
was explicitly declined earlier in this project for security reasons. Instead
each category reuses a real, already-scoped connection this platform already
has:

  - linux:      the FalconOps backend's OWN host/container (psutil) — real
                 self-diagnostics, not a stand-in for a customer's server.
  - kubernetes:  the same "kubernetes_cluster" integration restart_pod uses
                 (rased/actions/adapters/k8s_real.py) — real, read-only API
                 calls against a cluster the operator explicitly configured.
  - network:     network_path_service.py's real traceroute/TCP/TLS probes —
                 safe by nature (active probing needs no agent on the target).
  - database:    the real, already-collected data from db_monitoring.py's
                 configured DB agents (db_instances/db_metrics/db_slow_queries/
                 db_locks) — the latest real reading, timestamped, not a fresh
                 on-demand query (no live per-instance SQL connection here).
  - oneagent_host: diagnostics against any OneAgent-MONITORED host (not just
                 this backend's own host, unlike the "linux" category above) —
                 but still no remote execution: every command here reads
                 telemetry OneAgent already streamed into Mongo (metrics/
                 processes/connections/logs), honestly labeled with its real
                 collection timestamp. OneAgent's transport is send-only
                 (confirmed in oneagent/pkg/transport/transport.go — heartbeat
                 only ever POSTs out, never receives) — this project explicitly
                 declined a remote-exec-agent-on-any-host model for security
                 reasons, so "diagnostics" here means "query what's already
                 been collected," never "probe the host live."

A command that has nothing configured to run against returns an honest
"not configured" result — never fabricated output.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


COMMAND_CATALOG: List[Dict[str, Any]] = [
    {"id": "linux_cpu_mem", "category": "linux", "label": "CPU / Memory", "risk": "low",
     "description": "CPU%, memory usage, load average on the FalconOps backend host."},
    {"id": "linux_disk", "category": "linux", "label": "Disk Usage", "risk": "low",
     "description": "Filesystem usage on the FalconOps backend host."},
    {"id": "linux_processes", "category": "linux", "label": "Top Processes", "risk": "low",
     "description": "Top processes by CPU on the FalconOps backend host."},
    {"id": "k8s_get_pods", "category": "kubernetes", "label": "Get Pods", "risk": "low",
     "description": "List pods in a namespace.", "params": ["namespace"]},
    {"id": "k8s_get_nodes", "category": "kubernetes", "label": "Get Nodes", "risk": "low",
     "description": "List cluster nodes and their status."},
    {"id": "k8s_describe_pod", "category": "kubernetes", "label": "Describe Pod", "risk": "low",
     "description": "Events and status for one pod.", "params": ["namespace", "pod_name"]},
    {"id": "net_ping", "category": "network", "label": "Ping / Reachability", "risk": "low",
     "description": "TCP+TLS reachability and latency to a host:port.", "params": ["hostname", "port"]},
    {"id": "net_traceroute", "category": "network", "label": "Traceroute", "risk": "low",
     "description": "Real ICMP traceroute to an IP.", "params": ["target_ip"]},
    {"id": "net_dns", "category": "network", "label": "DNS Lookup", "risk": "low",
     "description": "Resolve a hostname (A/AAAA/PTR).", "params": ["hostname"]},
    {"id": "db_active_sessions", "category": "database", "label": "Active Sessions", "risk": "low",
     "description": "Latest collected active-session count for a DB instance.", "params": ["instance_id"]},
    {"id": "db_slow_queries", "category": "database", "label": "Slow Queries", "risk": "low",
     "description": "Latest collected slow-query log for a DB instance.", "params": ["instance_id"]},
    {"id": "db_locks", "category": "database", "label": "Locks", "risk": "low",
     "description": "Latest collected lock/blocking data for a DB instance.", "params": ["instance_id"]},
    {"id": "oneagent_host_snapshot", "category": "oneagent_host", "label": "Host Snapshot", "risk": "low",
     "description": "Latest collected CPU/memory/disk metrics for an OneAgent-monitored host.", "params": ["host"]},
    {"id": "oneagent_host_processes", "category": "oneagent_host", "label": "Process List", "risk": "low",
     "description": "Current discovered process list for an OneAgent-monitored host (from its last heartbeat).", "params": ["host"]},
    {"id": "oneagent_host_connections", "category": "oneagent_host", "label": "Network Connections", "risk": "low",
     "description": "Recently observed TCP connections for an OneAgent-monitored host.", "params": ["host"]},
    {"id": "oneagent_host_logs", "category": "oneagent_host", "label": "Recent Logs", "risk": "low",
     "description": "Most recent log lines collected from an OneAgent-monitored host.", "params": ["host"]},
]

_BY_ID = {c["id"]: c for c in COMMAND_CATALOG}


def list_commands(category: Optional[str] = None) -> List[Dict[str, Any]]:
    if category:
        return [c for c in COMMAND_CATALOG if c["category"] == category]
    return list(COMMAND_CATALOG)


async def _run_linux(command_id: str) -> Dict[str, Any]:
    import psutil
    if command_id == "linux_cpu_mem":
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.2), "cpu_count": psutil.cpu_count(),
            "memory_percent": mem.percent, "memory_used_gb": round(mem.used / 1e9, 2),
            "memory_total_gb": round(mem.total / 1e9, 2), "load_average": psutil.getloadavg(),
        }
    if command_id == "linux_disk":
        disk = psutil.disk_usage("/")
        return {"total_gb": round(disk.total / 1e9, 2), "used_gb": round(disk.used / 1e9, 2),
                "free_gb": round(disk.free / 1e9, 2), "percent": disk.percent}
    if command_id == "linux_processes":
        procs = sorted(
            ({"pid": p.pid, "name": p.info.get("name"), "cpu_percent": p.info.get("cpu_percent")}
             for p in psutil.process_iter(["name", "cpu_percent"])),
            key=lambda p: p["cpu_percent"] or 0, reverse=True,
        )
        return {"top_processes": procs[:15]}
    raise ValueError(f"unknown linux command: {command_id}")


async def _run_k8s(command_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from .rased.actions.executors import _get_k8s_cluster_config
    from .rased.actions.adapters import k8s_real

    cluster_config = await _get_k8s_cluster_config()
    if not cluster_config:
        return {"available": False, "reason": "no kubernetes_cluster integration configured"}

    import asyncio
    from kubernetes import client as k8s_client

    def _call():
        api_client = k8s_real.build_api_client(cluster_config)
        try:
            core = k8s_client.CoreV1Api(api_client)
            if command_id == "k8s_get_pods":
                namespace = params.get("namespace", "default")
                pods = core.list_namespaced_pod(namespace=namespace, _request_timeout=10)
                return {"pods": [{"name": p.metadata.name, "phase": p.status.phase,
                                   "restarts": sum(c.restart_count for c in (p.status.container_statuses or []))}
                                  for p in pods.items]}
            if command_id == "k8s_get_nodes":
                nodes = core.list_node(_request_timeout=10)
                return {"nodes": [{"name": n.metadata.name,
                                    "ready": any(c.type == "Ready" and c.status == "True" for c in n.status.conditions)}
                                   for n in nodes.items]}
            if command_id == "k8s_describe_pod":
                namespace, pod_name = params.get("namespace", "default"), params["pod_name"]
                events = core.list_namespaced_event(
                    namespace=namespace, field_selector=f"involvedObject.name={pod_name}", _request_timeout=10,
                )
                return {"events": [{"reason": e.reason, "message": e.message, "type": e.type} for e in events.items]}
            raise ValueError(f"unknown k8s command: {command_id}")
        finally:
            api_client.close()

    try:
        result = await asyncio.to_thread(_call)
        return {"available": True, **result}
    except Exception as e:
        logger.warning(f"troubleshooting k8s command {command_id} failed: {e}")
        return {"available": False, "reason": str(e)[:300]}


async def _run_network(command_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from . import network_path_service as nps

    if command_id == "net_traceroute":
        target_ip = params.get("target_ip")
        if not target_ip:
            return {"available": False, "reason": "target_ip required"}
        return {"available": True, **await nps.run_traceroute(target_ip)}

    if command_id == "net_ping":
        hostname, port = params.get("hostname"), int(params.get("port", 443))
        if not hostname:
            return {"available": False, "reason": "hostname required"}
        try:
            import socket
            target_ip = socket.gethostbyname(hostname)
        except socket.gaierror as e:
            return {"available": False, "reason": f"DNS resolution failed: {e}"}
        return {"available": True, **await nps.measure_endpoint(hostname, target_ip, port, "https")}

    if command_id == "net_dns":
        hostname = params.get("hostname")
        if not hostname:
            return {"available": False, "reason": "hostname required"}
        import socket
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            ips = sorted({info[4][0] for info in addr_info})
            return {"available": True, "hostname": hostname, "resolved_ips": ips}
        except socket.gaierror as e:
            return {"available": False, "reason": str(e)}

    raise ValueError(f"unknown network command: {command_id}")


async def _run_database(command_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from ..core.database import db as mongo_db

    instance_id = params.get("instance_id")
    if not instance_id:
        return {"available": False, "reason": "instance_id required"}

    collection_map = {
        "db_active_sessions": ("db_metrics", {"instance_id": instance_id}, [("collected_at", -1)]),
        "db_slow_queries": ("db_slow_queries", {"instance_id": instance_id}, [("collected_at", -1)]),
        "db_locks": ("db_locks", {"instance_id": instance_id}, [("collected_at", -1)]),
    }
    entry = collection_map.get(command_id)
    if entry is None:
        raise ValueError(f"unknown database command: {command_id}")
    collection_name, query, sort = entry

    docs = await mongo_db[collection_name].find(query, {"_id": 0}).sort(sort).limit(20).to_list(20)
    if not docs:
        return {"available": False, "reason": f"no collected data for instance_id '{instance_id}' — "
                                                 "is the DB monitoring agent running for it?"}
    return {"available": True, "readings": docs, "note": "latest collected reading, not a fresh live query"}


async def _run_oneagent_host(command_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from ..core.database import db

    host = params.get("host")
    if not host:
        return {"available": False, "reason": "host required"}

    agent_doc = await db.oneagent_agents.find_one({"host": host}, {"_id": 0})
    if not agent_doc:
        return {"available": False, "reason": f"no OneAgent reporting for host '{host}'"}

    if command_id == "oneagent_host_snapshot":
        metrics = await db.metrics_timeseries.find(
            {"tags.host": host}, {"_id": 0, "name": 1, "value": 1, "unit": 1, "timestamp": 1},
        ).sort("timestamp", -1).limit(30).to_list(30)
        if not metrics:
            return {"available": False, "reason": f"no metrics collected yet for host '{host}'"}
        return {"available": True, "metrics": metrics, "note": "latest collected readings, not a fresh live probe"}

    if command_id == "oneagent_host_processes":
        services = agent_doc.get("services") or []
        return {"available": True, "processes": services, "as_of": agent_doc.get("last_seen"),
                "note": "from the agent's last heartbeat, not a fresh live process scan"}

    if command_id == "oneagent_host_connections":
        conns = await db.oneagent_netflows.find({"host": host}, {"_id": 0}).sort("received_at", -1).limit(50).to_list(50)
        if not conns:
            return {"available": False, "reason": f"no connections collected yet for host '{host}' (netflow plugin may not be enabled)"}
        return {"available": True, "connections": conns, "note": "latest collected snapshot, not a fresh live probe"}

    if command_id == "oneagent_host_logs":
        logs = await db.logs.find({"host": host}, {"_id": 0}).sort("timestamp", -1).limit(50).to_list(50)
        if not logs:
            return {"available": False, "reason": f"no logs collected yet for host '{host}'"}
        return {"available": True, "logs": logs, "note": "most recently collected log lines"}

    raise ValueError(f"unknown oneagent_host command: {command_id}")


async def run_command(command_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    spec = _BY_ID.get(command_id)
    if spec is None:
        raise ValueError(f"Unknown command_id: {command_id!r}. Known: {sorted(_BY_ID)}")
    params = params or {}
    started = datetime.now(timezone.utc)

    try:
        if spec["category"] == "linux":
            output = await _run_linux(command_id)
        elif spec["category"] == "kubernetes":
            output = await _run_k8s(command_id, params)
        elif spec["category"] == "network":
            output = await _run_network(command_id, params)
        elif spec["category"] == "database":
            output = await _run_database(command_id, params)
        elif spec["category"] == "oneagent_host":
            output = await _run_oneagent_host(command_id, params)
        else:
            raise ValueError(f"unknown category: {spec['category']}")
        ok = True
    except Exception as e:
        logger.warning(f"troubleshooting command {command_id} failed: {e}")
        output = {"error": str(e)[:500]}
        ok = False

    result = {
        "command_id": command_id, "category": spec["category"], "label": spec["label"],
        "ok": ok, "output": output, "run_at": started.isoformat(),
        "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
    }
    await _audit(command_id, params, result)
    return result


async def _audit(command_id: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
    from ..core.database import db as mongo_db
    try:
        await mongo_db.troubleshooting_audit.insert_one({
            "command_id": command_id, "params": params, "ok": result["ok"],
            "run_at": result["run_at"], "duration_ms": result["duration_ms"],
        })
    except Exception as e:
        logger.warning(f"troubleshooting audit write failed: {e}")


__all__ = ["COMMAND_CATALOG", "list_commands", "run_command"]
