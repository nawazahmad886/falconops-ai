"""
FalconOps AI - Enterprise Alert Engine
Alert lifecycle management with severity levels and state transitions
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from ..core.database import db


async def _evaluate_workflow_triggers(alert: Dict):
    """Best-effort 'problem trigger' workflow evaluation — fires any workflow whose
    trigger.problem_filter matches this alert. Never allowed to affect alert creation
    itself, same as _auto_investigate below."""
    try:
        from . import workflow_trigger_service
        await workflow_trigger_service.evaluate_problem_triggers(alert)
    except Exception:
        pass


async def _auto_investigate(alert: Dict):
    """Best-effort autonomous investigation hand-off for a critical/high alert — wraps
    it in its own incident (reusing IncidentEngine.create_incident_from_alerts) and
    hands off to the orchestrator. Never allowed to affect alert creation itself."""
    try:
        from .incident_engine import incident_engine
        from . import autonomous_ops_orchestrator as orchestrator
        incident = await incident_engine.create_incident_from_alerts(
            alert_ids=[alert["id"]],
            correlation_reason="auto_critical_alert",
            tenant_id=alert.get("tenant_id"),
            created_by="system:autonomous_ops",
        )
        await orchestrator.investigate_and_recommend(
            incident["id"], alert, tenant_id=alert.get("tenant_id")
        )
    except Exception:
        pass


async def _broadcast_alert_event(event_type: str, alert: Dict):
    """Best-effort live push to the Problems console (see problems_broadcaster.py) —
    never allowed to affect alert lifecycle operations themselves."""
    try:
        from .problems_broadcaster import broadcast_problem_event
        await broadcast_problem_event(
            event_type=event_type,
            problem_id=f"ae:{alert['id']}",
            severity=alert.get("severity"),
            status=alert.get("status"),
            title=alert.get("title"),
            source="alert_engine",
        )
    except Exception:
        pass


class AlertStatus(str, Enum):
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Severity priorities for sorting
SEVERITY_PRIORITY = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "info": 5
}


class AlertEngine:
    """Enterprise Alert Engine with full lifecycle management"""
    
    async def create_alert(
        self,
        title: str,
        description: str,
        severity: str,
        source: str,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None,
        rule_id: Optional[str] = None,
        tags: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
        auto_resolve_minutes: Optional[int] = None
    ) -> Dict:
        """Create a new alert"""
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for duplicate active alerts (same entity + metric)
        existing = await db.alerts_engine.find_one({
            "entity_id": entity_id,
            "metric_name": metric_name,
            "status": {"$in": [AlertStatus.TRIGGERED.value, AlertStatus.ACKNOWLEDGED.value]}
        })
        
        if existing:
            # Update existing alert count instead of creating duplicate
            await db.alerts_engine.update_one(
                {"id": existing["id"]},
                {
                    "$set": {"last_occurrence": now, "metric_value": metric_value},
                    "$inc": {"occurrence_count": 1}
                }
            )
            return {**existing, "deduplicated": True, "_id": None}
        
        alert_doc = {
            "id": alert_id,
            "title": title,
            "description": description,
            "severity": severity,
            "status": AlertStatus.TRIGGERED.value,
            "source": source,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "threshold": threshold,
            "rule_id": rule_id,
            "tags": tags or {},
            "tenant_id": tenant_id,
            "occurrence_count": 1,
            "created_at": now,
            "updated_at": now,
            "last_occurrence": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "resolved_at": None,
            "resolved_by": None,
            "closed_at": None,
            "closed_by": None,
            "resolution_notes": None,
            "incident_id": None,
            "assigned_to": None,
            "assignment_group": None,
            "auto_resolve_at": (datetime.now(timezone.utc) + timedelta(minutes=auto_resolve_minutes)).isoformat() if auto_resolve_minutes else None,
            "escalation_level": 0,
            "notification_sent": False
        }
        
        await db.alerts_engine.insert_one(alert_doc)

        # Update alert statistics
        await self._update_stats(severity, "created")

        clean_alert = {k: v for k, v in alert_doc.items() if k != "_id"}

        # Publish to the real event bus (Kafka if connected, MongoDB fallback
        # otherwise) — kafka_consumers.py's handler fans this out to the SOC live
        # feed and a durable event_log record.
        try:
            from .kafka_pipeline import producer
            await producer.send("alerts", clean_alert)
        except Exception:
            pass

        # Problem-trigger workflows: evaluated for every alert regardless of severity —
        # each workflow's own trigger.problem_filter decides whether it's a match.
        asyncio.create_task(_evaluate_workflow_triggers(clean_alert))

        # Autonomous investigation for high-severity standalone alerts: wrap it in its
        # own incident and hand off to the orchestrator (fire-and-forget — must never
        # block or fail alert creation itself). Lower-severity alerts are left for the
        # normal correlation engines to group before investigating.
        if severity in ("critical", "high"):
            asyncio.create_task(_auto_investigate(clean_alert))

        asyncio.create_task(_broadcast_alert_event("problem.created", clean_alert))

        return clean_alert
    
    async def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        user_email: str,
        notes: Optional[str] = None
    ) -> Optional[Dict]:
        """Acknowledge an alert"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id, "status": AlertStatus.TRIGGERED.value},
            {
                "$set": {
                    "status": AlertStatus.ACKNOWLEDGED.value,
                    "acknowledged_at": now,
                    "acknowledged_by": user_email,
                    "updated_at": now
                }
            },
            return_document=True
        )
        
        if result:
            await self._update_stats(result["severity"], "acknowledged")
            clean = {k: v for k, v in result.items() if k != "_id"}
            asyncio.create_task(_broadcast_alert_event("problem.updated", clean))
            return clean
        return None
    
    async def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        user_email: str,
        resolution_notes: Optional[str] = None
    ) -> Optional[Dict]:
        """Resolve an alert"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id, "status": {"$in": [AlertStatus.TRIGGERED.value, AlertStatus.ACKNOWLEDGED.value]}},
            {
                "$set": {
                    "status": AlertStatus.RESOLVED.value,
                    "resolved_at": now,
                    "resolved_by": user_email,
                    "resolution_notes": resolution_notes,
                    "updated_at": now
                }
            },
            return_document=True
        )
        
        if result:
            await self._update_stats(result["severity"], "resolved")
            # Calculate MTTR
            await self._calculate_mttr(result)
            clean = {k: v for k, v in result.items() if k != "_id"}
            asyncio.create_task(_broadcast_alert_event("problem.updated", clean))
            return clean
        return None
    
    async def close_alert(
        self,
        alert_id: str,
        user_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """Close a resolved alert"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id, "status": AlertStatus.RESOLVED.value},
            {
                "$set": {
                    "status": AlertStatus.CLOSED.value,
                    "closed_at": now,
                    "closed_by": user_email,
                    "updated_at": now
                }
            },
            return_document=True
        )
        
        if result:
            await self._update_stats(result["severity"], "closed")
            clean = {k: v for k, v in result.items() if k != "_id"}
            asyncio.create_task(_broadcast_alert_event("problem.updated", clean))
            return clean
        return None
    
    async def auto_resolve_stale_alerts(self) -> int:
        """Auto-resolve alerts that have passed their auto_resolve_at time"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.alerts_engine.update_many(
            {
                "status": {"$in": [AlertStatus.TRIGGERED.value, AlertStatus.ACKNOWLEDGED.value]},
                "auto_resolve_at": {"$lt": now, "$ne": None}
            },
            {
                "$set": {
                    "status": AlertStatus.RESOLVED.value,
                    "resolved_at": now,
                    "resolved_by": "system:auto_resolve",
                    "resolution_notes": "Auto-resolved due to timeout",
                    "updated_at": now
                }
            }
        )
        
        return result.modified_count
    
    async def escalate_alert(self, alert_id: str) -> Optional[Dict]:
        """Escalate an alert to the next level"""
        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id},
            {
                "$inc": {"escalation_level": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            },
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def assign_alert(
        self,
        alert_id: str,
        assigned_to: Optional[str],
        assignment_group: Optional[str],
        user_email: str,
    ) -> Optional[Dict]:
        """Assign an alert to a user and/or team — new in the Problems console;
        no assignment concept existed on this collection before."""
        now = datetime.now(timezone.utc).isoformat()

        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id},
            {
                "$set": {
                    "assigned_to": assigned_to,
                    "assignment_group": assignment_group,
                    "updated_at": now,
                }
            },
            return_document=True
        )

        if result:
            clean = {k: v for k, v in result.items() if k != "_id"}
            asyncio.create_task(_broadcast_alert_event("problem.assigned", clean))
            return clean
        return None

    async def link_to_incident(
        self,
        alert_id: str,
        incident_id: str
    ) -> Optional[Dict]:
        """Link an alert to an incident"""
        result = await db.alerts_engine.find_one_and_update(
            {"id": alert_id},
            {
                "$set": {
                    "incident_id": incident_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def get_alert(self, alert_id: str) -> Optional[Dict]:
        """Get a single alert by ID"""
        alert = await db.alerts_engine.find_one({"id": alert_id}, {"_id": 0})
        return alert
    
    async def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict:
        """Get alerts with filtering"""
        query = {}
        
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id
        if source:
            query["source"] = source
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        if start_time or end_time:
            query["created_at"] = {}
            if start_time:
                query["created_at"]["$gte"] = start_time
            if end_time:
                query["created_at"]["$lte"] = end_time
        
        total = await db.alerts_engine.count_documents(query)
        sort_dir = -1 if sort_order == "desc" else 1
        
        alerts = await db.alerts_engine.find(
            query, {"_id": 0}
        ).sort(sort_by, sort_dir).skip(offset).limit(limit).to_list(limit)
        
        return {
            "alerts": alerts,
            "total": total,
            "offset": offset,
            "limit": limit
        }
    
    async def get_active_alerts(self, tenant_id: Optional[str] = None) -> List[Dict]:
        """Get all active (triggered + acknowledged) alerts"""
        query = {"status": {"$in": [AlertStatus.TRIGGERED.value, AlertStatus.ACKNOWLEDGED.value]}}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        alerts = await db.alerts_engine.find(
            query, {"_id": 0}
        ).sort([
            ("severity", 1),  # Sort by severity priority
            ("created_at", -1)
        ]).to_list(500)
        
        # Sort by severity priority
        alerts.sort(key=lambda x: SEVERITY_PRIORITY.get(x.get("severity", "info"), 5))
        
        return alerts
    
    async def get_alert_stats(self, tenant_id: Optional[str] = None) -> Dict:
        """Get alert statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        # Count by status
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        by_status = await db.alerts_engine.aggregate(pipeline).to_list(10)
        
        # Count by severity
        pipeline = [
            {"$match": {**query, "status": {"$in": ["triggered", "acknowledged"]}}},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
        ]
        by_severity = await db.alerts_engine.aggregate(pipeline).to_list(10)
        
        # Active alerts count
        active_count = await db.alerts_engine.count_documents({
            **query,
            "status": {"$in": ["triggered", "acknowledged"]}
        })
        
        # Get MTTR from stats collection
        mttr_doc = await db.alert_stats.find_one({"type": "mttr"})
        avg_mttr = mttr_doc.get("avg_mttr_minutes", 0) if mttr_doc else 0
        
        return {
            "by_status": {r["_id"]: r["count"] for r in by_status},
            "by_severity": {r["_id"]: r["count"] for r in by_severity},
            "active_alerts": active_count,
            "avg_mttr_minutes": round(avg_mttr, 2)
        }
    
    async def _update_stats(self, severity: str, action: str):
        """Update alert statistics"""
        await db.alert_stats.update_one(
            {"type": "daily", "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
            {
                "$inc": {
                    f"{action}_total": 1,
                    f"{action}_{severity}": 1
                }
            },
            upsert=True
        )
    
    async def _calculate_mttr(self, alert: Dict):
        """Calculate and update MTTR (Mean Time to Resolution)"""
        if not alert.get("created_at") or not alert.get("resolved_at"):
            return
        
        created = datetime.fromisoformat(alert["created_at"].replace("Z", "+00:00"))
        resolved = datetime.fromisoformat(alert["resolved_at"].replace("Z", "+00:00"))
        resolution_time = (resolved - created).total_seconds() / 60  # in minutes
        
        # Update running MTTR average
        await db.alert_stats.update_one(
            {"type": "mttr"},
            {
                "$inc": {"total_resolution_time": resolution_time, "resolved_count": 1}
            },
            upsert=True
        )
        
        # Recalculate average
        stats = await db.alert_stats.find_one({"type": "mttr"})
        if stats and stats.get("resolved_count", 0) > 0:
            avg_mttr = stats["total_resolution_time"] / stats["resolved_count"]
            await db.alert_stats.update_one(
                {"type": "mttr"},
                {"$set": {"avg_mttr_minutes": avg_mttr}}
            )


# Singleton instance
alert_engine = AlertEngine()
