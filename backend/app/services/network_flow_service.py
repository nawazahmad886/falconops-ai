"""
FalconOps AI - Network Flow Service
Enriches and persists netflow batches reported by the oneagent netflow plugin
(oneagent/pkg/plugins/netflow) -- established TCP connections observed via
/proc/net/tcp{,6}, NOT eBPF packet capture. See that plugin's file header for
exactly what is and isn't visible with this approach (no L7/TLS, no byte
counters, periodic snapshot so short-lived connections can be missed).

Reuses, rather than reimplements: geo_ip_service.get_ip_intel() for ASN/ISP/
proxy enrichment and threat_intel_service.is_malicious_ip() for IOC matching
(both already exist and are exercised elsewhere in this codebase) — flows are
only ever enriched, never used to fabricate data these services can't provide.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import geo_ip_service
from . import threat_intel_service

logger = logging.getLogger(__name__)

MAX_BATCH_ENRICH_CONCURRENCY = 10
NETFLOW_TTL_DAYS = 7

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.oneagent_netflows.create_index([("host", 1), ("received_at", -1)], name="host_time")
        await db.oneagent_netflows.create_index([("remote_ip", 1), ("received_at", -1)], name="remote_ip_time")
        await db.oneagent_netflows.create_index(
            "received_at", expireAfterSeconds=NETFLOW_TTL_DAYS * 24 * 3600, name="netflow_ttl")
        _indexes_ready = True
    except Exception as e:
        logger.debug(f"oneagent_netflows index create skipped: {e}")


class NetworkFlowService:
    """Enriches oneagent netflow batches with GeoIP/ASN + threat intel, persists them,
    feeds public+malicious remote IPs into the security threat engine, and serves the
    network query API (flows/summary, dependencies)."""

    async def enrich_and_persist_batch(self, host: str, raw_flows: List[Dict]) -> Dict[str, Any]:
        await _ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()
        docs: List[Dict[str, Any]] = []
        threats_fired = 0

        # Import here (not module scope) to avoid a circular import at startup —
        # security_service already imports several sibling services the same way.
        from .security_service import threat_engine

        for item in raw_flows:
            remote_ip = item.get("remote_ip")
            local_ip = item.get("local_ip")
            if not remote_ip or not local_ip:
                continue

            doc: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "host": host,
                "local_ip": local_ip,
                "local_port": item.get("local_port"),
                "remote_ip": remote_ip,
                "remote_port": item.get("remote_port"),
                "state": item.get("state"),
                "pid": item.get("pid"),
                "process_name": item.get("process_name"),
                "service": item.get("service") or "unknown",
                "tenant_id": None,  # oneagent ingest isn't tenant-scoped today (matches ingest_metrics/ingest_traces)
                "received_at": now,
                "source": "oneagent",
            }

            # get_ip_intel/is_malicious_ip both already no-op (return {}/None) for
            # private/loopback IPs without making an HTTP call — safe to call
            # unconditionally rather than re-deriving a public-IP check here.
            intel = await geo_ip_service.get_ip_intel(remote_ip)
            if intel:
                doc["remote_ip_intel"] = intel

            ioc_match = await threat_intel_service.is_malicious_ip(remote_ip)
            if ioc_match:
                doc["threat_match"] = {
                    "source": ioc_match.get("source"),
                    "malware_family": ioc_match.get("malware_family"),
                }

            docs.append(doc)

            flow_for_detection = {
                "host": host, "local_port": doc["local_port"], "remote_ip": remote_ip,
                "service": doc["service"],
            }
            fired = await threat_engine.process_netflow(flow_for_detection, ioc_match)
            if fired:
                threats_fired += len(fired)

        if docs:
            await db.oneagent_netflows.insert_many(docs)

        return {"ingested": len(docs), "threats_detected": threats_fired}

    async def get_flow_summary(self, hours: int = 1, host: Optional[str] = None) -> Dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query: Dict[str, Any] = {"received_at": {"$gte": since}}
        if host:
            query["host"] = host

        flows = await db.oneagent_netflows.find(query, {"_id": 0}).to_list(20000)

        remote_ip_counts: Dict[str, int] = {}
        service_counts: Dict[str, int] = {}
        threat_count = 0
        for f in flows:
            remote_ip_counts[f["remote_ip"]] = remote_ip_counts.get(f["remote_ip"], 0) + 1
            service_counts[f["service"]] = service_counts.get(f["service"], 0) + 1
            if f.get("threat_match"):
                threat_count += 1

        top_talkers = sorted(remote_ip_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        top_services = sorted(service_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

        return {
            "window_hours": hours,
            "total_flows": len(flows),
            "distinct_remote_ips": len(remote_ip_counts),
            "threat_flagged_flows": threat_count,
            "top_talkers": [{"remote_ip": ip, "count": c} for ip, c in top_talkers],
            "top_services": [{"service": s, "count": c} for s, c in top_services],
        }

    async def get_network_dependencies(self, hours: int = 24) -> Dict[str, Any]:
        """Best-effort service-to-service graph: resolves a remote_ip to another
        agent's reported hostname/services where possible (join against
        db.oneagent_agents), otherwise falls back to the raw IP. There is no
        guaranteed way to resolve every remote IP to a service name -- not every
        host necessarily runs oneagent -- so unresolved edges are expected, not
        a bug."""
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        flows = await db.oneagent_netflows.find(
            {"received_at": {"$gte": since}}, {"_id": 0, "host": 1, "service": 1, "remote_ip": 1}
        ).to_list(20000)

        agents = await db.oneagent_agents.find({}, {"_id": 0, "host": 1}).to_list(500)
        known_hosts = {a["host"] for a in agents}

        edges: Dict[str, Dict[str, Any]] = {}
        for f in flows:
            source = f"{f['host']}:{f['service']}"
            target = f["remote_ip"] if f["remote_ip"] not in known_hosts else f["remote_ip"]
            key = f"{source}->{target}"
            if key not in edges:
                edges[key] = {"source": source, "target": target, "count": 0}
            edges[key]["count"] += 1

        return {
            "window_hours": hours,
            "edges": sorted(edges.values(), key=lambda e: e["count"], reverse=True),
            "edge_count": len(edges),
        }


network_flow_service = NetworkFlowService()
