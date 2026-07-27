"""
FalconOps AI - Connector SDK: polling scheduler

Mirrors soc_ingestion_service.generic_ingestion_scheduler()'s exact shape
(while-True / try-except-log / asyncio.sleep, per-doc last_polled_at
tracking) — a parallel scheduler, not a reuse of poll_generic_source()
itself, since that mechanism's single-bearer-header/flat-list-JSON
assumptions are too weak for real connector auth/response semantics.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from ..core.database import db
from ..services import soc_ingestion_service
from ..services.metrics_timeseries_service import metrics_timeseries_service
from ..services.topology_service import topology_service
from .base import EventsCapable, MetricsCapable, TopologyCapable
from .registry import CONNECTOR_REGISTRY
from .service import build_connector

logger = logging.getLogger(__name__)

CONNECTOR_POLL_TICK_SECONDS = 60


def _poll_interval_seconds(doc: Dict[str, Any]) -> int:
    raw = doc.get("poll_interval_seconds") or (doc.get("config") or {}).get("scrape_interval_seconds") or 60
    try:
        return max(30, int(raw))
    except (TypeError, ValueError):
        return 60


def _due(doc: Dict[str, Any]) -> bool:
    last = doc.get("last_polled_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
    return elapsed >= _poll_interval_seconds(doc)


async def poll_connector_once(integration_id: str) -> Dict[str, Any]:
    """Runs exactly one poll cycle for one connector — used both by the
    scheduler's tick and by the on-demand POST /api/connectors/{id}/poll route."""
    connector = await build_connector(integration_id)
    if connector is None:
        return {"polled": False, "reason": "not configured"}

    health = await connector.health()
    if health.status == "unhealthy":
        logger.info(f"connector '{integration_id}' unhealthy, skipping poll: {health.message}")
        return {"polled": False, "reason": health.message}

    counts: Dict[str, int] = {}

    if isinstance(connector, MetricsCapable):
        points = await connector.fetch_metrics()
        if points:
            batch = [p.to_ingest_dict() for p in points]
            await metrics_timeseries_service.ingest_batch(batch, tenant_id=connector.tenant_id)
        counts["metrics"] = len(points)

    if isinstance(connector, EventsCapable):
        events = await connector.fetch_events()
        if events:
            await soc_ingestion_service.ingest_batch(events)
        counts["events"] = len(events)

    if isinstance(connector, TopologyCapable):
        discovery = await connector.discover_topology()
        created_nodes = 0
        created_edges = 0
        name_to_id: Dict[str, str] = {}
        for node in discovery.get("nodes", []):
            environment = node.get("environment", "production")
            existing = await topology_service.get_service_by_name(node["name"], environment, connector.tenant_id)
            if existing:
                name_to_id[node["name"]] = existing["id"]
                continue
            created = await topology_service.create_service_node(
                node["name"], node.get("service_type", "external"),
                environment=environment, tenant_id=connector.tenant_id,
            )
            name_to_id[node["name"]] = created["id"]
            created_nodes += 1
        for edge in discovery.get("edges", []):
            source_id = name_to_id.get(edge["source_name"])
            target_id = name_to_id.get(edge["target_name"])
            if source_id and target_id:
                await topology_service.create_connection(
                    source_id, target_id, connection_type=edge.get("connection_type", "http"),
                    tenant_id=connector.tenant_id,
                )
                created_edges += 1
        counts["topology_nodes"] = created_nodes
        counts["topology_edges"] = created_edges

    await db.integrations.update_one(
        {"integration_id": integration_id},
        {"$set": {"last_polled_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"polled": True, "counts": counts}


async def connector_poll_scheduler():
    """Background loop started once at app startup (see main.py)."""
    while True:
        try:
            docs = await db.integrations.find(
                {"integration_id": {"$in": list(CONNECTOR_REGISTRY.keys())}, "enabled": True}, {"_id": 0}
            ).to_list(200)
            for doc in docs:
                if not _due(doc):
                    continue
                try:
                    await poll_connector_once(doc["integration_id"])
                except Exception as e:
                    logger.error(f"connector poll failed for '{doc['integration_id']}': {e}")
        except Exception as e:
            logger.error(f"connector_poll_scheduler tick failed: {e}")
        await asyncio.sleep(CONNECTOR_POLL_TICK_SECONDS)
