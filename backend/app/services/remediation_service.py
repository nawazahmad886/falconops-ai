"""
FalconOps AI - Auto-Remediation Engine
Automatic and manual remediation actions triggered by RCA findings, health violations, and security threats
"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


# ======================== ACTION LIBRARY ========================

ACTION_LIBRARY = {
    "restart_service": {
        "name": "Restart Service",
        "description": "Restart a target service or container",
        "category": "compute",
        "risk_level": "medium",
        "auto_eligible": True,
        "params": ["service_name", "host"],
        "script_template": "systemctl restart {service_name}",
    },
    "block_ip": {
        "name": "Block IP Address",
        "description": "Add IP to firewall deny list to block malicious traffic",
        "category": "security",
        "risk_level": "low",
        "auto_eligible": True,
        "params": ["ip_address"],
        "script_template": "iptables -A INPUT -s {ip_address} -j DROP",
    },
    "scale_pods": {
        "name": "Scale Kubernetes Pods",
        "description": "Increase replica count for a deployment",
        "category": "compute",
        "risk_level": "medium",
        "auto_eligible": True,
        "params": ["deployment", "replicas", "namespace"],
        "script_template": "kubectl scale deployment/{deployment} --replicas={replicas} -n {namespace}",
    },
    "disable_user": {
        "name": "Disable User Account",
        "description": "Lock a user account suspected of compromise",
        "category": "security",
        "risk_level": "high",
        "auto_eligible": False,
        "params": ["username"],
        "script_template": "usermod -L {username}",
    },
    "flush_cache": {
        "name": "Flush Cache",
        "description": "Clear Redis or application cache to resolve stale data issues",
        "category": "performance",
        "risk_level": "low",
        "auto_eligible": True,
        "params": ["cache_type"],
        "script_template": "redis-cli FLUSHDB",
    },
    "rotate_credentials": {
        "name": "Rotate Credentials",
        "description": "Force credential rotation for compromised accounts",
        "category": "security",
        "risk_level": "high",
        "auto_eligible": False,
        "params": ["account_type", "account_id"],
        "script_template": "falconops rotate-creds --type {account_type} --id {account_id}",
    },
    "increase_disk": {
        "name": "Increase Disk Space",
        "description": "Expand disk volume or clean up temporary files",
        "category": "infrastructure",
        "risk_level": "medium",
        "auto_eligible": True,
        "params": ["host", "mount_point"],
        "script_template": "find /tmp -type f -mtime +7 -delete && df -h {mount_point}",
    },
    "kill_process": {
        "name": "Kill Runaway Process",
        "description": "Terminate a process consuming excessive resources",
        "category": "compute",
        "risk_level": "medium",
        "auto_eligible": True,
        "params": ["host", "process_name"],
        "script_template": "pkill -f {process_name}",
    },
}

# ======================== RCA -> REMEDIATION MAPPING ========================

RCA_REMEDIATION_MAP = {
    "high_cpu": ["restart_service", "kill_process", "scale_pods"],
    "high_memory": ["restart_service", "flush_cache", "scale_pods"],
    "disk_full": ["increase_disk"],
    "brute_force": ["block_ip", "disable_user"],
    "privilege_escalation": ["disable_user", "rotate_credentials"],
    "data_exfiltration": ["disable_user", "block_ip"],
    "connection_leak": ["restart_service", "flush_cache"],
    "service_down": ["restart_service", "scale_pods"],
    "cache_stale": ["flush_cache", "restart_service"],
    "credential_compromise": ["rotate_credentials", "disable_user", "block_ip"],
    "port_scan": ["block_ip"],
    "impossible_travel": ["disable_user"],
    "malicious_ip": ["block_ip"],
}

THREAT_REMEDIATION_MAP = {
    "brute_force": "block_ip",
    "credential_stuffing": "block_ip",
    "privilege_escalation": "disable_user",
    "data_exfiltration": "disable_user",
    "malicious_ip": "block_ip",
    "impossible_travel": "disable_user",
}


# ======================== CORE ENGINE ========================

async def suggest_remediation(root_cause: str, context: Dict = None) -> List[Dict]:
    """Given an RCA root cause, suggest appropriate remediation actions"""
    actions = RCA_REMEDIATION_MAP.get(root_cause, [])
    suggestions = []
    for action_id in actions:
        action = ACTION_LIBRARY.get(action_id)
        if action:
            suggestion = {
                "action_id": action_id,
                "name": action["name"],
                "description": action["description"],
                "risk_level": action["risk_level"],
                "auto_eligible": action["auto_eligible"],
                "category": action["category"],
                "params": action["params"],
                "script_preview": action["script_template"],
                "root_cause": root_cause,
            }
            # Pre-fill params from context
            if context:
                filled_params = {}
                for p in action["params"]:
                    if p in context:
                        filled_params[p] = context[p]
                    elif p == "ip_address" and "source_ip" in context:
                        filled_params[p] = context["source_ip"]
                    elif p == "username" and "user" in context:
                        filled_params[p] = context["user"]
                    elif p == "service_name" and "service" in context:
                        filled_params[p] = context["service"]
                    elif p == "host" and "host" in context:
                        filled_params[p] = context["host"]
                suggestion["pre_filled_params"] = filled_params
            suggestions.append(suggestion)
    return suggestions


async def execute_remediation(action_id: str, params: Dict, trigger: str = "manual", triggered_by: str = "system") -> Dict:
    """Execute a remediation action (simulated in sandbox mode)"""
    action = ACTION_LIBRARY.get(action_id)
    if not action:
        return {"error": f"Unknown action: {action_id}"}

    record = {
        "id": str(uuid.uuid4()),
        "action_id": action_id,
        "action_name": action["name"],
        "category": action["category"],
        "risk_level": action["risk_level"],
        "params": params,
        "trigger": trigger,
        "triggered_by": triggered_by,
        "status": "executing",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Generate the resolved script
    script = action["script_template"]
    for k, v in params.items():
        script = script.replace(f"{{{k}}}", str(v))
    record["resolved_script"] = script

    # Simulate execution (in production, this would call actual systems)
    await asyncio.sleep(0.5)

    record["status"] = "completed"
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    record["result"] = f"Action '{action['name']}' executed successfully (sandbox mode)"

    await db.remediation_history.insert_one(record)
    record.pop("_id", None)

    # Dispatch notification about remediation
    try:
        from .connector_dispatcher import dispatch_event
        await dispatch_event("remediation", {
            "id": record["id"],
            "type": "auto_remediation",
            "title": f"Remediation Executed: {action['name']}",
            "message": f"Action: {script}. Trigger: {trigger}. By: {triggered_by}",
            "severity": "info",
            "timestamp": record["completed_at"],
            "source": "FalconOps Remediation Engine",
        }, min_severity="info")
    except Exception as e:
        logger.warning(f"Failed to dispatch remediation notification: {e}")

    return record


async def auto_remediate_threat(threat: Dict) -> Optional[Dict]:
    """Automatically remediate a known threat type if eligible"""
    threat_type = threat.get("type", "")
    action_id = THREAT_REMEDIATION_MAP.get(threat_type)
    if not action_id:
        return None

    action = ACTION_LIBRARY.get(action_id)
    if not action or not action.get("auto_eligible"):
        return None

    params = {}
    if action_id == "block_ip":
        ip = threat.get("source_ip")
        if not ip or ip == "unknown":
            return None
        params["ip_address"] = ip
    elif action_id == "disable_user":
        user = threat.get("user")
        if not user or user == "unknown":
            return None
        params["username"] = user

    return await execute_remediation(action_id, params, trigger="auto", triggered_by="threat_engine")


async def get_action_library() -> List[Dict]:
    """Get all available remediation actions"""
    return [
        {"id": k, **{mk: mv for mk, mv in v.items() if mk != "script_template"}, "script_preview": v["script_template"]}
        for k, v in ACTION_LIBRARY.items()
    ]


async def get_remediation_history(limit: int = 50) -> List[Dict]:
    """Get recent remediation execution history"""
    return await db.remediation_history.find({}, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)


async def get_remediation_stats() -> Dict:
    """Get remediation stats"""
    total = await db.remediation_history.count_documents({})
    auto = await db.remediation_history.count_documents({"trigger": "auto"})
    manual = await db.remediation_history.count_documents({"trigger": "manual"})
    completed = await db.remediation_history.count_documents({"status": "completed"})
    failed = await db.remediation_history.count_documents({"status": "failed"})

    # By category
    cat_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_category = await db.remediation_history.aggregate(cat_pipeline).to_list(10)

    # By action
    act_pipeline = [
        {"$group": {"_id": "$action_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    by_action = await db.remediation_history.aggregate(act_pipeline).to_list(10)

    return {
        "total_executions": total,
        "auto_triggered": auto,
        "manual_triggered": manual,
        "completed": completed,
        "failed": failed,
        "by_category": [{"category": c["_id"], "count": c["count"]} for c in by_category],
        "by_action": [{"action": a["_id"], "count": a["count"]} for a in by_action],
    }
