"""
FalconOps AI - RBAC & Audit Logs Service
Enterprise role-based access control with granular permissions and comprehensive audit trail
"""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# ======================== PERMISSION DEFINITIONS ========================

PERMISSIONS = {
    "dashboard.view": "View dashboards and NOC overview",
    "monitors.view": "View monitors and their status",
    "monitors.manage": "Create, edit, delete monitors",
    "alerts.view": "View alerts and incidents",
    "alerts.manage": "Acknowledge, resolve alerts",
    "health_rules.view": "View health rules",
    "health_rules.manage": "Create, edit, delete health rules",
    "security.view": "View security events and threats",
    "security.manage": "Resolve threats, manage security settings",
    "security.simulate": "Run attack simulations",
    "remediation.view": "View remediation history",
    "remediation.execute": "Execute remediation actions",
    "remediation.approve_destructive": "Approve DESTRUCTIVE-tier actions (RASED rollback/failover) — "
                                        "a higher bar than remediation.execute's GUARDED-tier default",
    "ueba.view": "View user behavior analytics",
    "impact.analyze": "Run impact analysis",
    "integrations.view": "View integration catalog",
    "integrations.manage": "Configure and manage integrations",
    "reports.view": "View and download reports",
    "reports.manage": "Create and schedule reports",
    "users.view": "View user list",
    "users.manage": "Create, edit, deactivate users",
    "rbac.manage": "Manage roles and permissions",
    "audit.view": "View audit logs",
    "topology.view": "View service topology",
    "topology.manage": "Manage topology nodes",
    "copilot.use": "Use AI Copilot",
    "settings.manage": "Manage platform settings",
    # Agent Builder / Agentic Workflow Builder (AI Operations)
    "agent.read": "View agent definitions and the agent catalog",
    "agent.create": "Create new agent definitions and draft versions",
    "agent.edit": "Edit agent draft versions",
    "agent.publish": "Publish, rollback and archive agent versions",
    "tool.read": "View the tool catalog",
    "tool.create": "Create new tool catalog entries",
    "tool.edit": "Edit, disable and version tool catalog entries",
    "workflow.read": "View workflow definitions, executions and observability",
    "workflow.create": "Create workflows, drafts, clones and imports",
    "workflow.edit": "Edit workflow draft versions",
    "workflow.publish": "Publish, rollback and archive workflow versions",
    "workflow.execute": "Run, dry-run, test-run and cancel workflow executions; decide non-destructive approvals",
    "workflow.delete": "Delete workflow definitions",
}

# ======================== DEFAULT ROLES ========================

DEFAULT_ROLES = {
    "admin": {
        "name": "Administrator",
        "description": "Full access to all platform features",
        "permissions": list(PERMISSIONS.keys()),
        "is_system": True,
    },
    "security_analyst": {
        "name": "Security Analyst",
        "description": "Full security access, read-only for operations",
        "permissions": [
            "dashboard.view", "monitors.view", "alerts.view",
            "security.view", "security.manage", "security.simulate",
            "ueba.view", "impact.analyze", "remediation.view",
            "reports.view", "audit.view", "copilot.use",
            "health_rules.view", "topology.view",
            "agent.read", "tool.read", "workflow.read",
        ],
        "is_system": True,
    },
    "devops": {
        "name": "DevOps Engineer",
        "description": "Operations management with monitoring and remediation access",
        "permissions": [
            "dashboard.view", "monitors.view", "monitors.manage",
            "alerts.view", "alerts.manage", "health_rules.view", "health_rules.manage",
            "security.view", "remediation.view", "remediation.execute",
            "impact.analyze", "reports.view", "reports.manage",
            "topology.view", "topology.manage", "copilot.use",
            "integrations.view",
            # Agent/workflow authoring and running — not publish/delete, which stay admin-only
            # (mirrors remediation.approve_destructive staying admin-only, same reasoning:
            # publishing gates what runs unattended in production).
            "agent.read", "agent.create", "agent.edit",
            "tool.read",
            "workflow.read", "workflow.create", "workflow.edit", "workflow.execute",
        ],
        "is_system": True,
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access across the platform",
        "permissions": [
            "dashboard.view", "monitors.view", "alerts.view",
            "security.view", "ueba.view", "reports.view",
            "health_rules.view", "topology.view", "audit.view",
            "agent.read", "tool.read", "workflow.read",
        ],
        "is_system": True,
    },
}


async def init_default_roles():
    """Initialize default roles in DB if they don't exist"""
    for role_id, role_data in DEFAULT_ROLES.items():
        existing = await db.roles.find_one({"role_id": role_id})
        if not existing:
            await db.roles.insert_one({
                "role_id": role_id,
                "name": role_data["name"],
                "description": role_data["description"],
                "permissions": role_data["permissions"],
                "is_system": role_data["is_system"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })


async def get_all_roles() -> List[Dict]:
    """Get all roles with their permissions"""
    roles = await db.roles.find({}, {"_id": 0}).to_list(50)
    return roles


async def get_role(role_id: str) -> Optional[Dict]:
    return await db.roles.find_one({"role_id": role_id}, {"_id": 0})


async def create_role(role_id: str, name: str, description: str, permissions: List[str]) -> Dict:
    valid_perms = [p for p in permissions if p in PERMISSIONS]
    doc = {
        "role_id": role_id,
        "name": name,
        "description": description,
        "permissions": valid_perms,
        "is_system": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.roles.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_role(role_id: str, permissions: List[str]) -> Dict:
    existing = await db.roles.find_one({"role_id": role_id})
    if not existing:
        return {"error": "Role not found"}
    if existing.get("is_system") and role_id == "admin":
        return {"error": "Cannot modify admin role permissions"}
    valid_perms = [p for p in permissions if p in PERMISSIONS]
    await db.roles.update_one({"role_id": role_id}, {"$set": {"permissions": valid_perms, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": f"Role {role_id} updated", "permissions": valid_perms}


async def delete_role(role_id: str) -> Dict:
    existing = await db.roles.find_one({"role_id": role_id})
    if not existing:
        return {"error": "Role not found"}
    if existing.get("is_system"):
        return {"error": "Cannot delete system role"}
    await db.roles.delete_one({"role_id": role_id})
    return {"message": f"Role {role_id} deleted"}


async def check_permission(user: Dict, permission: str) -> bool:
    """Check if a user has a specific permission"""
    role_id = user.get("role", "viewer")
    role = await db.roles.find_one({"role_id": role_id}, {"_id": 0})
    if not role:
        role = DEFAULT_ROLES.get(role_id)
    if not role:
        return False
    return permission in role.get("permissions", [])


def get_all_permissions() -> List[Dict]:
    return [{"key": k, "description": v} for k, v in PERMISSIONS.items()]


# ======================== AUDIT LOG SERVICE ========================

async def log_audit(user: Dict, action: str, resource: str, detail: str = "", status: str = "success", ip: str = "") -> None:
    """Log an audit event"""
    try:
        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "user_email": user.get("email", "system"),
            "user_role": user.get("role", "unknown"),
            "action": action,
            "resource": resource,
            "detail": detail[:500],
            "status": status,
            "ip_address": ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


async def get_audit_logs(hours: int = 24, user_email: str = None, action: str = None, resource: str = None, limit: int = 100, offset: int = 0) -> Dict:
    """Query audit logs with filters"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query = {"timestamp": {"$gte": cutoff}}
    if user_email:
        query["user_email"] = {"$regex": re.escape(user_email), "$options": "i"}
    if action:
        query["action"] = action
    if resource:
        query["resource"] = resource

    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
    total = await db.audit_logs.count_documents(query)
    return {"logs": logs, "total": total}


async def get_audit_stats(hours: int = 24) -> Dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total = await db.audit_logs.count_documents({"timestamp": {"$gte": cutoff}})

    user_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$user_email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10},
    ]
    top_users = await db.audit_logs.aggregate(user_pipeline).to_list(10)

    action_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10},
    ]
    top_actions = await db.audit_logs.aggregate(action_pipeline).to_list(10)

    return {
        "total_events": total,
        "top_users": [{"user": u["_id"], "count": u["count"]} for u in top_users],
        "top_actions": [{"action": a["_id"], "count": a["count"]} for a in top_actions],
    }
