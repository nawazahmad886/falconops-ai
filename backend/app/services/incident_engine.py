"""
FalconOps AI - Incident Management Engine
Correlate alerts into incidents with RCA support
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from ..core.database import db


class IncidentStatus(str, Enum):
    ACTIVE = "active"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(str, Enum):
    SEV1 = "sev1"  # Critical - Major outage
    SEV2 = "sev2"  # High - Partial outage
    SEV3 = "sev3"  # Medium - Degraded performance
    SEV4 = "sev4"  # Low - Minor issue
    SEV5 = "sev5"  # Info - No impact


# Map alert severities to incident severities
ALERT_TO_INCIDENT_SEVERITY = {
    "critical": "sev1",
    "high": "sev2",
    "medium": "sev3",
    "low": "sev4",
    "info": "sev5"
}


class IncidentEngine:
    """Enterprise Incident Management with alert correlation"""
    
    async def create_incident(
        self,
        title: str,
        description: str,
        severity: str,
        affected_services: List[str] = None,
        affected_hosts: List[str] = None,
        initial_alert_ids: List[str] = None,
        source: str = "manual",
        tenant_id: Optional[str] = None,
        created_by: str = "system"
    ) -> Dict:
        """Create a new incident"""
        incident_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        incident_doc = {
            "id": incident_id,
            "title": title,
            "description": description,
            "severity": severity,
            "status": IncidentStatus.ACTIVE.value,
            "source": source,
            "affected_services": affected_services or [],
            "affected_hosts": affected_hosts or [],
            "alert_ids": initial_alert_ids or [],
            "alert_count": len(initial_alert_ids or []),
            "tenant_id": tenant_id,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "resolved_at": None,
            "resolved_by": None,
            "closed_at": None,
            "closed_by": None,
            "root_cause": None,
            "root_cause_analysis": None,
            "resolution_steps": [],
            "timeline": [
                {
                    "timestamp": now,
                    "action": "created",
                    "user": created_by,
                    "details": f"Incident created: {title}"
                }
            ],
            "assignee": None,
            "team": None,
            "priority_score": self._calculate_priority_score(severity, len(affected_services or [])),
            "sla_breach_at": self._calculate_sla_breach(severity),
            "is_sla_breached": False,
            "communication_channel": None,
            "postmortem_id": None
        }
        
        await db.incidents_engine.insert_one(incident_doc)
        
        # Link alerts to this incident
        if initial_alert_ids:
            await db.alerts_engine.update_many(
                {"id": {"$in": initial_alert_ids}},
                {"$set": {"incident_id": incident_id}}
            )
        
        return {k: v for k, v in incident_doc.items() if k != "_id"}
    
    async def create_incident_from_alerts(
        self,
        alert_ids: List[str],
        correlation_reason: str = "manual",
        tenant_id: Optional[str] = None,
        created_by: str = "system"
    ) -> Dict:
        """Create an incident from multiple correlated alerts"""
        # Fetch the alerts
        alerts = await db.alerts_engine.find(
            {"id": {"$in": alert_ids}},
            {"_id": 0}
        ).to_list(100)
        
        if not alerts:
            raise ValueError("No alerts found")
        
        # Determine severity (highest among alerts)
        severities = {"critical": 1, "high": 2, "medium": 3, "low": 4, "info": 5}
        highest_severity = min(alerts, key=lambda x: severities.get(x.get("severity", "info"), 5))
        incident_severity = ALERT_TO_INCIDENT_SEVERITY.get(highest_severity["severity"], "sev3")
        
        # Collect affected entities
        affected_services = list(set([a.get("entity_name") for a in alerts if a.get("entity_type") == "service"]))
        affected_hosts = list(set([a.get("tags", {}).get("host") for a in alerts if a.get("tags", {}).get("host")]))
        
        # Generate title
        if len(alerts) == 1:
            title = alerts[0].get("title", "Alert Incident")
        else:
            title = f"Multiple alerts ({len(alerts)}) - {alerts[0].get('entity_name', 'Unknown')}"
        
        # Generate description
        metrics_involved = list(set([a.get("metric_name") for a in alerts if a.get("metric_name")]))
        description = f"Correlated incident with {len(alerts)} alerts. " \
                      f"Metrics: {', '.join(metrics_involved[:5])}. " \
                      f"Correlation: {correlation_reason}"
        
        return await self.create_incident(
            title=title,
            description=description,
            severity=incident_severity,
            affected_services=affected_services,
            affected_hosts=affected_hosts,
            initial_alert_ids=alert_ids,
            source=f"correlation:{correlation_reason}",
            tenant_id=tenant_id,
            created_by=created_by
        )
    
    async def auto_correlate_alerts(
        self,
        time_window_minutes: int = 5,
        min_alerts: int = 2,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Automatically correlate alerts into incidents"""
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=time_window_minutes)).isoformat()
        
        # Find uncorrelated active alerts
        query = {
            "status": {"$in": ["triggered", "acknowledged"]},
            "incident_id": None,
            "created_at": {"$gte": start_time}
        }
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        alerts = await db.alerts_engine.find(query, {"_id": 0}).to_list(500)
        
        if len(alerts) < min_alerts:
            return []
        
        # Group by host
        host_groups = {}
        for alert in alerts:
            host = alert.get("tags", {}).get("host") or alert.get("entity_id")
            if host not in host_groups:
                host_groups[host] = []
            host_groups[host].append(alert)
        
        # Group by service
        service_groups = {}
        for alert in alerts:
            service = alert.get("entity_name")
            if service and service not in service_groups:
                service_groups[service] = []
            if service:
                service_groups[service].append(alert)
        
        created_incidents = []
        
        # Create incidents for host correlations
        for host, host_alerts in host_groups.items():
            if len(host_alerts) >= min_alerts:
                alert_ids = [a["id"] for a in host_alerts]
                try:
                    incident = await self.create_incident_from_alerts(
                        alert_ids=alert_ids,
                        correlation_reason=f"same_host:{host}",
                        tenant_id=tenant_id,
                        created_by="system:auto_correlate"
                    )
                    created_incidents.append(incident)
                except Exception as e:
                    print(f"Correlation error: {e}")
        
        # Create incidents for service correlations (if not already correlated)
        for service, service_alerts in service_groups.items():
            # Filter out already correlated alerts
            uncorrelated = [a for a in service_alerts if not any(
                a["id"] in inc.get("alert_ids", []) for inc in created_incidents
            )]
            
            if len(uncorrelated) >= min_alerts:
                alert_ids = [a["id"] for a in uncorrelated]
                try:
                    incident = await self.create_incident_from_alerts(
                        alert_ids=alert_ids,
                        correlation_reason=f"same_service:{service}",
                        tenant_id=tenant_id,
                        created_by="system:auto_correlate"
                    )
                    created_incidents.append(incident)
                except Exception as e:
                    print(f"Correlation error: {e}")
        
        return created_incidents
    
    async def add_alert_to_incident(
        self,
        incident_id: str,
        alert_id: str,
        user: str = "system"
    ) -> Optional[Dict]:
        """Add an alert to an existing incident"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.incidents_engine.find_one_and_update(
            {"id": incident_id},
            {
                "$addToSet": {"alert_ids": alert_id},
                "$inc": {"alert_count": 1},
                "$push": {
                    "timeline": {
                        "timestamp": now,
                        "action": "alert_added",
                        "user": user,
                        "details": f"Alert {alert_id} added to incident"
                    }
                },
                "$set": {"updated_at": now}
            },
            return_document=True
        )
        
        if result:
            # Link alert to incident
            await db.alerts_engine.update_one(
                {"id": alert_id},
                {"$set": {"incident_id": incident_id}}
            )
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def update_status(
        self,
        incident_id: str,
        new_status: str,
        user: str,
        notes: Optional[str] = None
    ) -> Optional[Dict]:
        """Update incident status"""
        now = datetime.now(timezone.utc).isoformat()
        
        updates = {
            "status": new_status,
            "updated_at": now
        }
        
        if new_status == IncidentStatus.RESOLVED.value:
            updates["resolved_at"] = now
            updates["resolved_by"] = user
        elif new_status == IncidentStatus.CLOSED.value:
            updates["closed_at"] = now
            updates["closed_by"] = user
        
        timeline_entry = {
            "timestamp": now,
            "action": f"status_changed_to_{new_status}",
            "user": user,
            "details": notes or f"Status changed to {new_status}"
        }
        
        result = await db.incidents_engine.find_one_and_update(
            {"id": incident_id},
            {
                "$set": updates,
                "$push": {"timeline": timeline_entry}
            },
            return_document=True
        )
        
        if result:
            # If resolved, also resolve all linked alerts
            if new_status == IncidentStatus.RESOLVED.value:
                await db.alerts_engine.update_many(
                    {"incident_id": incident_id, "status": {"$in": ["triggered", "acknowledged"]}},
                    {
                        "$set": {
                            "status": "resolved",
                            "resolved_at": now,
                            "resolved_by": user,
                            "resolution_notes": f"Resolved via incident {incident_id}"
                        }
                    }
                )
            
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def set_root_cause(
        self,
        incident_id: str,
        root_cause: str,
        root_cause_analysis: Dict,
        user: str
    ) -> Optional[Dict]:
        """Set root cause analysis for an incident"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.incidents_engine.find_one_and_update(
            {"id": incident_id},
            {
                "$set": {
                    "root_cause": root_cause,
                    "root_cause_analysis": root_cause_analysis,
                    "status": IncidentStatus.IDENTIFIED.value,
                    "updated_at": now
                },
                "$push": {
                    "timeline": {
                        "timestamp": now,
                        "action": "root_cause_identified",
                        "user": user,
                        "details": f"Root cause: {root_cause[:100]}"
                    }
                }
            },
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def add_resolution_step(
        self,
        incident_id: str,
        step: str,
        user: str
    ) -> Optional[Dict]:
        """Add a resolution step to the incident"""
        now = datetime.now(timezone.utc).isoformat()
        
        step_entry = {
            "timestamp": now,
            "step": step,
            "user": user
        }
        
        result = await db.incidents_engine.find_one_and_update(
            {"id": incident_id},
            {
                "$push": {
                    "resolution_steps": step_entry,
                    "timeline": {
                        "timestamp": now,
                        "action": "resolution_step_added",
                        "user": user,
                        "details": step[:100]
                    }
                },
                "$set": {"updated_at": now}
            },
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def get_incident(self, incident_id: str) -> Optional[Dict]:
        """Get a single incident with its alerts"""
        incident = await db.incidents_engine.find_one({"id": incident_id}, {"_id": 0})
        
        if incident and incident.get("alert_ids"):
            alerts = await db.alerts_engine.find(
                {"id": {"$in": incident["alert_ids"]}},
                {"_id": 0}
            ).to_list(100)
            incident["alerts"] = alerts
        
        return incident
    
    async def get_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """Get incidents with filtering"""
        query = {}
        
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        total = await db.incidents_engine.count_documents(query)
        
        incidents = await db.incidents_engine.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
        
        return {
            "incidents": incidents,
            "total": total,
            "offset": offset,
            "limit": limit
        }
    
    async def get_active_incidents(self, tenant_id: Optional[str] = None) -> List[Dict]:
        """Get all active incidents"""
        query = {"status": {"$nin": [IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value]}}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        incidents = await db.incidents_engine.find(
            query, {"_id": 0}
        ).sort("priority_score", -1).to_list(100)
        
        return incidents
    
    async def get_incident_stats(self, tenant_id: Optional[str] = None) -> Dict:
        """Get incident statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        # Count by status
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        by_status = await db.incidents_engine.aggregate(pipeline).to_list(10)
        
        # Count by severity
        pipeline = [
            {"$match": {**query, "status": {"$nin": ["resolved", "closed"]}}},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
        ]
        by_severity = await db.incidents_engine.aggregate(pipeline).to_list(10)
        
        # Active incidents
        active_count = await db.incidents_engine.count_documents({
            **query,
            "status": {"$nin": ["resolved", "closed"]}
        })
        
        # MTTR for incidents
        pipeline = [
            {"$match": {**query, "resolved_at": {"$ne": None}}},
            {"$project": {
                "resolution_time": {
                    "$divide": [
                        {"$subtract": [{"$toDate": "$resolved_at"}, {"$toDate": "$created_at"}]},
                        60000  # to minutes
                    ]
                }
            }},
            {"$group": {"_id": None, "avg_mttr": {"$avg": "$resolution_time"}}}
        ]
        mttr_result = await db.incidents_engine.aggregate(pipeline).to_list(1)
        avg_mttr = mttr_result[0]["avg_mttr"] if mttr_result else 0
        
        return {
            "by_status": {r["_id"]: r["count"] for r in by_status},
            "by_severity": {r["_id"]: r["count"] for r in by_severity},
            "active_incidents": active_count,
            "avg_mttr_minutes": round(avg_mttr, 2)
        }
    
    def _calculate_priority_score(self, severity: str, affected_count: int) -> int:
        """Calculate priority score based on severity and affected services"""
        severity_scores = {"sev1": 100, "sev2": 80, "sev3": 60, "sev4": 40, "sev5": 20}
        base_score = severity_scores.get(severity, 50)
        return base_score + (affected_count * 5)
    
    def _calculate_sla_breach(self, severity: str) -> Optional[str]:
        """Calculate SLA breach time based on severity"""
        sla_minutes = {
            "sev1": 15,   # Critical: 15 min response
            "sev2": 30,   # High: 30 min response
            "sev3": 60,   # Medium: 1 hour response
            "sev4": 240,  # Low: 4 hour response
            "sev5": None  # Info: No SLA
        }
        
        minutes = sla_minutes.get(severity)
        if minutes:
            return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
        return None


# Singleton instance
incident_engine = IncidentEngine()
