"""
Platform overview + FalconOps's own internal dependency map.

Overview reuses self_monitor.py's existing health-computation functions
directly rather than re-deriving Mongo ping/system-resource/process-info
logic a second time — those are the same real checks SelfMonitoringPage.js
already renders. This module only adds version/deployment-shape context
self_monitor.py doesn't carry, and a couple of new plain fields.

The "dependency map" here is NOT the customer-monitored-service topology
(that's topology_service.py / TopologyPage.js, and stays there) — it's a
small, static description of FalconOps's OWN deployment shape (confirmed by
reading docker-compose.yml directly): one FastAPI process, its datastores,
and the background jobs living inside it. Static because it IS static —
docker-compose.yml doesn't change at runtime, and presenting it as if it
were dynamically discovered would be dishonest for no benefit.
"""
import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# A real signal, not an arbitrary tri-state: green means the collection
# responded fast, amber means it responded but slowly enough to be worth an
# operator's attention (a real latency threshold, not a fabricated status),
# red means the query itself failed.
WARNING_LATENCY_MS = 250

# Kept in sync by hand with main.py's `FastAPI(..., version="1.0.0")` — there
# is no lower-risk way to read a sibling module's FastAPI app version from a
# service module without importing main.py at load time, which is exactly
# the circular import job_control.py's lazy `_main()` trick exists to avoid.
PLATFORM_VERSION = "1.0.0"

INTERNAL_DEPENDENCY_MAP = {
    "note": "Static description of docker-compose.yml's actual topology, not a dynamically discovered graph.",
    "nodes": [
        {"id": "nginx", "label": "Nginx (gateway)", "kind": "gateway"},
        {"id": "frontend", "label": "Frontend (static React build)", "kind": "frontend"},
        {"id": "backend", "label": "FalconOps Backend (this process)", "kind": "app"},
        {"id": "mongo", "label": "MongoDB", "kind": "datastore"},
        {"id": "redis", "label": "Redis", "kind": "datastore"},
        {"id": "kafka", "label": "Kafka (optional)", "kind": "datastore"},
        {"id": "victoria_metrics", "label": "VictoriaMetrics (optional)", "kind": "datastore"},
    ],
    "edges": [
        {"from": "nginx", "to": "frontend"},
        {"from": "nginx", "to": "backend"},
        {"from": "backend", "to": "mongo"},
        {"from": "backend", "to": "redis"},
        {"from": "backend", "to": "kafka"},
        {"from": "backend", "to": "victoria_metrics"},
    ],
}


async def get_overview() -> Dict[str, Any]:
    from ...routes import self_monitor  # cross-module reuse of its health helpers — see module docstring

    mongo = await self_monitor._mongo_health()
    resources = self_monitor._system_resources()
    process = self_monitor._process_info()
    components = await get_service_components()

    healthy = sum(1 for s in components if s["status"] == "healthy")
    warning = sum(1 for s in components if s["status"] == "warning")
    critical = sum(1 for s in components if s["status"] == "critical")

    return {
        "version": PLATFORM_VERSION,
        "process": process,
        "mongo": mongo,
        "resources": resources,
        "services_healthy": healthy,
        "services_warning": warning,
        "services_critical": critical,
        "services_total": len(components),
    }


def get_dependency_map() -> Dict[str, Any]:
    return INTERNAL_DEPENDENCY_MAP


async def get_service_components() -> List[Dict[str, Any]]:
    """Every internal application component (self_monitor.py's own
    SERVICE_HEALTH_TARGETS list, reused directly — see that module for the
    canonical list), each with a real green/warning/red status: red is an
    actual failed query, amber is an actual slow one (> WARNING_LATENCY_MS),
    green is a fast successful one. Never a fabricated status."""
    from ...core.database import db
    from ...routes.self_monitor import SERVICE_HEALTH_TARGETS

    out: List[Dict[str, Any]] = []
    for name, collection, desc in SERVICE_HEALTH_TARGETS:
        started = time.perf_counter()
        try:
            count = await db[collection].estimated_document_count()
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            status = "warning" if latency_ms > WARNING_LATENCY_MS else "healthy"
            out.append({
                "name": name, "collection": collection, "description": desc,
                "status": status, "latency_ms": latency_ms, "document_count": count, "error": None,
            })
        except Exception as e:
            out.append({
                "name": name, "collection": collection, "description": desc,
                "status": "critical", "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "document_count": 0, "error": str(e)[:200],
            })
    return out


__all__ = ["PLATFORM_VERSION", "get_overview", "get_dependency_map", "get_service_components"]
