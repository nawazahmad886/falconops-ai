"""
FalconOps AI - Smart Correlation Engine
Topology-aware, multi-signal event correlation for intelligent incident creation
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from collections import defaultdict
from ..core.database import db


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

        # 3. Group alerts by multiple dimensions
        groups = self._multi_dimension_group(alerts, service_map, upstream, downstream, service_id_map)

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
            }
            await db.incidents_engine.insert_one(incident_doc)
            await db.alerts_engine.update_many({"id": {"$in": alert_ids}}, {"$set": {"incident_id": incident_id}})
            correlated_alert_ids.update(alert_ids)

            clean = {k: v for k, v in incident_doc.items() if k != "_id"}
            created.append(clean)
            details.append({"type": group["type"], "reason": group["reason"], "alerts": len(alert_ids), "confidence": group.get("confidence", 0.7)})

        return {
            "incidents_created": len(created),
            "alerts_processed": len(alerts),
            "incidents": created,
            "correlation_details": details,
        }

    def _multi_dimension_group(self, alerts, service_map, upstream, downstream, service_id_map):
        """Group alerts by host, service, topology dependency, and metric pattern."""
        groups = []
        used = set()

        # --- Topology-based: alerts on services that share a dependency chain ---
        service_alerts = defaultdict(list)
        for a in alerts:
            svc = a.get("entity_name") or a.get("tags", {}).get("service")
            if svc and svc in service_map:
                service_alerts[svc].append(a)

        for svc, svc_alerts in service_alerts.items():
            node = service_map.get(svc)
            if not node:
                continue
            # Find sibling services sharing same upstream dep
            for dep_id in upstream.get(node["id"], set()):
                dep_node = service_id_map.get(dep_id)
                if not dep_node:
                    continue
                siblings = [sid for sid in downstream.get(dep_id, set()) if sid != node["id"]]
                for sib_id in siblings:
                    sib_node = service_id_map.get(sib_id)
                    if sib_node and sib_node["name"] in service_alerts:
                        combined = svc_alerts + service_alerts[sib_node["name"]]
                        ids = frozenset(a["id"] for a in combined)
                        if ids not in used and len(combined) >= 2:
                            used.add(ids)
                            groups.append({
                                "type": "topology_dependency",
                                "reason": f"Shared dependency: {dep_node['name']} affects {svc}, {sib_node['name']}",
                                "alerts": combined,
                                "confidence": 0.85,
                            })

        # --- Host-based grouping ---
        host_groups = defaultdict(list)
        for a in alerts:
            host = a.get("tags", {}).get("host") or a.get("entity_id")
            if host:
                host_groups[host].append(a)
        for host, h_alerts in host_groups.items():
            if len(h_alerts) >= 2:
                ids = frozenset(a["id"] for a in h_alerts)
                if ids not in used:
                    used.add(ids)
                    groups.append({
                        "type": "same_host",
                        "reason": f"Multiple alerts on host {host}",
                        "alerts": h_alerts,
                        "confidence": 0.75,
                    })

        # --- Metric pattern: same metric spiking across hosts ---
        metric_groups = defaultdict(list)
        for a in alerts:
            mn = a.get("metric_name")
            if mn:
                metric_groups[mn].append(a)
        for metric, m_alerts in metric_groups.items():
            hosts_affected = {a.get("tags", {}).get("host") for a in m_alerts}
            if len(hosts_affected) >= 2:
                ids = frozenset(a["id"] for a in m_alerts)
                if ids not in used:
                    used.add(ids)
                    groups.append({
                        "type": "metric_pattern",
                        "reason": f"{metric} anomaly across {len(hosts_affected)} hosts",
                        "alerts": m_alerts,
                        "confidence": 0.8,
                    })

        # --- Service-based fallback ---
        for svc, svc_alerts in service_alerts.items():
            if len(svc_alerts) >= 2:
                ids = frozenset(a["id"] for a in svc_alerts)
                if ids not in used:
                    used.add(ids)
                    groups.append({
                        "type": "same_service",
                        "reason": f"Multiple alerts on service {svc}",
                        "alerts": svc_alerts,
                        "confidence": 0.65,
                    })

        groups.sort(key=lambda g: g.get("confidence", 0), reverse=True)
        return groups

    def _priority_score(self, severity: str, affected_count: int) -> int:
        scores = {"sev1": 100, "sev2": 80, "sev3": 60, "sev4": 40, "sev5": 20}
        return scores.get(severity, 50) + affected_count * 5


smart_correlation_engine = SmartCorrelationEngine()
