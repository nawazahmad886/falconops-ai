"""
FalconOps AI - Smart Correlation Engine
Topology-aware, multi-signal event correlation for intelligent incident creation
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from collections import defaultdict
from ..core.database import db
from .correlation_shared import multi_dimension_group


class SmartCorrelationEngine:
    """Graph + time + metric pattern correlation engine"""

    async def correlate(
        self,
        time_window_minutes: int = 10,
        min_signals: int = 2,
        tenant_id: Optional[str] = None,
    ) -> Dict:
        """Run full smart correlation across alerts, anomalies, topology."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=time_window_minutes)).isoformat()

        # 1. Gather uncorrelated active alerts
        alert_query = {
            "status": {"$in": ["triggered", "acknowledged"]},
            "incident_id": None,
            "created_at": {"$gte": start},
        }
        if tenant_id:
            alert_query["tenant_id"] = tenant_id
        alerts = await db.alerts_engine.find(alert_query, {"_id": 0}).to_list(500)

        if len(alerts) < min_signals:
            return {"incidents_created": 0, "alerts_processed": len(alerts), "incidents": [], "correlation_details": []}

        # 2. Load topology graph
        topo_nodes = await db.topology_nodes.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(500)
        topo_edges = await db.topology_edges.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(1000)
        service_map = {n["name"]: n for n in topo_nodes}
        service_id_map = {n["id"]: n for n in topo_nodes}

        # Build adjacency: child -> parents (upstream deps)
        upstream = defaultdict(set)
        downstream = defaultdict(set)
        for e in topo_edges:
            upstream[e["source_id"]].add(e["target_id"])
            downstream[e["target_id"]].add(e["source_id"])

        # 3. Group alerts by multiple dimensions (shared grouping logic — see
        # correlation_shared.py; this engine only supplies its own field extraction for
        # db.alerts_engine's schema and its own fixed confidence values, unchanged from
        # before this was extracted).
        groups = multi_dimension_group(
            alerts, service_map, service_id_map, upstream, downstream,
            get_service=self._get_service, get_host=self._get_host,
            confidence_fn=self._confidence_fn,
        )

        # 4. Create incidents from groups
        created = []
        correlated_alert_ids = set()
        details = []

        for group in groups:
            group_alerts = group["alerts"]
            # Skip if all already correlated
            group_alerts = [a for a in group_alerts if a["id"] not in correlated_alert_ids]
            if len(group_alerts) < min_signals:
                continue

            alert_ids = [a["id"] for a in group_alerts]
            severities = {"critical": 1, "high": 2, "medium": 3, "low": 4, "info": 5}
            highest = min(group_alerts, key=lambda a: severities.get(a.get("severity", "info"), 5))
            sev_map = {"critical": "sev1", "high": "sev2", "medium": "sev3", "low": "sev4", "info": "sev5"}
            inc_severity = sev_map.get(highest["severity"], "sev3")

            hosts = list({a.get("tags", {}).get("host") for a in group_alerts if a.get("tags", {}).get("host")})
            services = list({a.get("entity_name") for a in group_alerts if a.get("entity_name")})
            metrics = list({a.get("metric_name") for a in group_alerts if a.get("metric_name")})

            incident_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            incident_doc = {
                "id": incident_id,
                "title": f"{group['reason']} ({len(group_alerts)} alerts)",
                "description": f"Smart correlation: {group['reason']}. Metrics: {', '.join(metrics[:5])}. Hosts: {', '.join(hosts[:5])}.",
                "severity": inc_severity,
                "status": "active",
                "source": f"smart_correlation:{group['type']}",
                "affected_services": services,
                "affected_hosts": hosts,
                "alert_ids": alert_ids,
                "alert_count": len(alert_ids),
                "tenant_id": tenant_id,
                "created_by": "system:smart_correlation",
                "created_at": now_iso,
                "updated_at": now_iso,
                "acknowledged_at": None,
                "resolved_at": None,
                "root_cause": None,
                "root_cause_analysis": None,
                "resolution_steps": [],
                "timeline": [{"timestamp": now_iso, "action": "created", "user": "system:smart_correlation", "details": f"Auto-correlated: {group['reason']}"}],
                "assignee": None,
                "team": None,
                "priority_score": self._priority_score(inc_severity, len(services)),
                "sla_breach_at": None,
                "is_sla_breached": False,
                "correlation_confidence": group.get("confidence", 0.7),
                "correlation_type": group["type"],
                "root_cause_entity": group.get("root_cause_entity"),
            }
            await db.incidents_engine.insert_one(incident_doc)
            await db.alerts_engine.update_many({"id": {"$in": alert_ids}}, {"$set": {"incident_id": incident_id}})
            correlated_alert_ids.update(alert_ids)

            clean = {k: v for k, v in incident_doc.items() if k != "_id"}
            created.append(clean)

            # Autonomous investigation — fire-and-forget, must never affect incident
            # creation. This incident is a real db.incidents_engine record, so the
            # orchestrator's later validate/escalate/learn steps (wired to
            # incident_engine.py's resolve path) apply to it too.
            try:
                from . import autonomous_ops_orchestrator as orchestrator
                asyncio.create_task(orchestrator.investigate_and_recommend(incident_id, highest, tenant_id=tenant_id))
            except Exception:
                pass
            details.append({"type": group["type"], "reason": group["reason"], "alerts": len(alert_ids), "confidence": group.get("confidence", 0.7)})

        return {
            "incidents_created": len(created),
            "alerts_processed": len(alerts),
            "incidents": created,
            "correlation_details": details,
        }

    # Field extraction + confidence scoring for this engine's schema (db.alerts_engine:
    # entity_name/tags.host rather than legacy db.alerts' top-level service/host) — the
    # actual grouping loop now lives in correlation_shared.multi_dimension_group,
    # shared with ai_correlation.py. Confidence values unchanged from before extraction.

    def _get_service(self, a: Dict) -> Optional[str]:
        return a.get("entity_name") or a.get("tags", {}).get("service")

    def _get_host(self, a: Dict) -> Optional[str]:
        return a.get("tags", {}).get("host") or a.get("entity_id")

    def _confidence_fn(self, group_type: str, combined_alerts: List[Dict]) -> float:
        return {
            "topology_dependency": 0.85,
            "same_host": 0.75,
            "metric_pattern": 0.8,
            "same_service": 0.65,
        }.get(group_type, 0.7)

    def _priority_score(self, severity: str, affected_count: int) -> int:
        scores = {"sev1": 100, "sev2": 80, "sev3": 60, "sev4": 40, "sev5": 20}
        return scores.get(severity, 50) + affected_count * 5


smart_correlation_engine = SmartCorrelationEngine()
