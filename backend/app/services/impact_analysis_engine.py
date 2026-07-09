"""
FalconOps AI - Impact Analysis Engine
Business impact quantification from topology, metrics, and alerts
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from collections import defaultdict
from ..core.database import db


class ImpactAnalysisEngine:
    """Evaluate business impact of incidents using topology + metrics + alerts"""

    async def analyze_incident_impact(self, incident_id: str, tenant_id: Optional[str] = None) -> Dict:
        """Full impact analysis for an incident."""
        incident = await db.incidents_engine.find_one({"id": incident_id}, {"_id": 0})
        if not incident:
            return {"error": "Incident not found"}

        # Gather alerts
        alerts = []
        if incident.get("alert_ids"):
            alerts = await db.alerts_engine.find({"id": {"$in": incident["alert_ids"]}}, {"_id": 0}).to_list(100)

        # Determine directly affected services + hosts
        affected_services = set(incident.get("affected_services", []))
        affected_hosts = set(incident.get("affected_hosts", []))
        for a in alerts:
            if a.get("entity_name"):
                affected_services.add(a["entity_name"])
            h = a.get("tags", {}).get("host")
            if h:
                affected_hosts.add(h)

        # Load topology
        nodes = await db.topology_nodes.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(500)
        edges = await db.topology_edges.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(1000)
        name_to_node = {n["name"]: n for n in nodes}
        id_to_node = {n["id"]: n for n in nodes}

        # Build downstream graph (who depends on whom)
        # downstream[target_id] = list of source_ids (services calling target)
        downstream_map = defaultdict(set)
        for e in edges:
            downstream_map[e["target_id"]].add(e["source_id"])

        # BFS to find blast radius
        affected_node_ids = set()
        for svc in affected_services:
            node = name_to_node.get(svc)
            if node:
                affected_node_ids.add(node["id"])

        blast_radius = []
        visited = set(affected_node_ids)
        queue = list(affected_node_ids)
        depth = 0
        while queue and depth < 5:
            depth += 1
            next_q = []
            for nid in queue:
                for caller_id in downstream_map.get(nid, set()):
                    if caller_id not in visited:
                        visited.add(caller_id)
                        next_q.append(caller_id)
                        caller = id_to_node.get(caller_id)
                        if caller:
                            blast_radius.append({
                                "service": caller["name"],
                                "type": caller.get("type", "unknown"),
                                "impact_depth": depth,
                                "status": caller.get("status", "unknown"),
                            })
            queue = next_q

        # Severity scoring
        severity_weights = {"critical": 10, "high": 7, "medium": 4, "low": 2, "info": 1}
        alert_severity_score = sum(severity_weights.get(a.get("severity", "info"), 1) for a in alerts)
        total_affected = len(affected_services) + len(blast_radius)
        has_frontend = any(br.get("type") == "frontend" for br in blast_radius)
        has_database = any(a.get("entity_type") == "database" or "database" in a.get("entity_name", "").lower() for a in alerts)

        # Business impact score 0-100
        impact_score = min(100, int(
            alert_severity_score * 2
            + total_affected * 5
            + (20 if has_frontend else 0)
            + (15 if has_database else 0)
            + len(affected_hosts) * 3
        ))

        if impact_score >= 80:
            impact_level = "critical"
        elif impact_score >= 60:
            impact_level = "high"
        elif impact_score >= 40:
            impact_level = "medium"
        elif impact_score >= 20:
            impact_level = "low"
        else:
            impact_level = "minimal"

        # User-facing assessment
        user_impact = "No direct user impact detected"
        if has_frontend:
            user_impact = f"User-facing services affected. Estimated {total_affected} services in blast radius."
        elif total_affected > 3:
            user_impact = f"Internal service degradation may affect end users. {total_affected} services impacted."

        result = {
            "incident_id": incident_id,
            "impact_score": impact_score,
            "impact_level": impact_level,
            "directly_affected": {
                "services": list(affected_services),
                "hosts": list(affected_hosts),
                "alerts": len(alerts),
            },
            "blast_radius": {
                "total_services": len(blast_radius),
                "services": blast_radius[:20],
                "max_depth": max((br["impact_depth"] for br in blast_radius), default=0),
            },
            "business_impact": {
                "user_facing": has_frontend,
                "database_affected": has_database,
                "user_impact_summary": user_impact,
            },
            "severity_breakdown": {sev: sum(1 for a in alerts if a.get("severity") == sev) for sev in ["critical", "high", "medium", "low"]},
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store analysis
        await db.impact_analyses.update_one(
            {"incident_id": incident_id},
            {"$set": result},
            upsert=True,
        )
        # Update incident
        await db.incidents_engine.update_one(
            {"id": incident_id},
            {"$set": {"impact_analysis": {"score": impact_score, "level": impact_level}, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

        return result

    async def get_blast_radius(self, service_name: str, tenant_id: Optional[str] = None) -> Dict:
        """Calculate blast radius if a service fails."""
        nodes = await db.topology_nodes.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(500)
        edges = await db.topology_edges.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0}).to_list(1000)
        name_to_node = {n["name"]: n for n in nodes}
        id_to_node = {n["id"]: n for n in nodes}

        target_node = name_to_node.get(service_name)
        if not target_node:
            return {"error": f"Service '{service_name}' not found in topology"}

        downstream_map = defaultdict(set)
        for e in edges:
            downstream_map[e["target_id"]].add(e["source_id"])

        impacted = []
        visited = {target_node["id"]}
        queue = [target_node["id"]]
        depth = 0
        while queue and depth < 5:
            depth += 1
            next_q = []
            for nid in queue:
                for caller_id in downstream_map.get(nid, set()):
                    if caller_id not in visited:
                        visited.add(caller_id)
                        next_q.append(caller_id)
                        caller = id_to_node.get(caller_id)
                        if caller:
                            impacted.append({"service": caller["name"], "type": caller.get("type"), "depth": depth})
            queue = next_q

        return {
            "service": service_name,
            "total_impacted": len(impacted),
            "impacted_services": impacted,
            "risk_level": "critical" if len(impacted) >= 5 else "high" if len(impacted) >= 3 else "medium" if len(impacted) >= 1 else "low",
        }

    async def get_system_risk_summary(self, tenant_id: Optional[str] = None) -> Dict:
        """Overall system risk based on topology + active alerts + incidents."""
        active_alerts = await db.alerts_engine.count_documents(
            {"status": {"$in": ["triggered", "acknowledged"]}, **({"tenant_id": tenant_id} if tenant_id else {})}
        )
        active_incidents = await db.incidents_engine.count_documents(
            {"status": {"$nin": ["resolved", "closed"]}, **({"tenant_id": tenant_id} if tenant_id else {})}
        )
        nodes = await db.topology_nodes.find({} if not tenant_id else {"tenant_id": tenant_id}, {"_id": 0, "name": 1, "status": 1}).to_list(500)
        unhealthy = [n for n in nodes if n.get("status") != "healthy"]

        risk_score = min(100, active_alerts * 3 + active_incidents * 10 + len(unhealthy) * 8)
        if risk_score >= 70:
            level = "critical"
        elif risk_score >= 50:
            level = "high"
        elif risk_score >= 30:
            level = "medium"
        else:
            level = "low"

        return {
            "risk_score": risk_score,
            "risk_level": level,
            "active_alerts": active_alerts,
            "active_incidents": active_incidents,
            "total_services": len(nodes),
            "unhealthy_services": len(unhealthy),
            "unhealthy_list": [n["name"] for n in unhealthy],
        }


impact_analysis_engine = ImpactAnalysisEngine()
