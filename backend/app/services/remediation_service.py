"""
FalconOps AI - Auto-Remediation Engine
Automatic and manual remediation actions triggered by RCA findings, health violations, and security threats.

IMPORTANT: execute_remediation() is DRY-RUN / PLAN-PREVIEW ONLY. It resolves the real
command that would run and records it, but never invokes a subprocess, SSH session, or
any infrastructure API — there is no live execution path in this module. Records are
stored with status="previewed" and execution_mode="dry_run" to make this explicit to
any caller or UI rendering them.
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
    "clear_logs": {
        "name": "Clear/Truncate Log Files",
        "description": "Truncate log files under a path in place (does not delete them, so an already-open file handle keeps writing) to relieve disk pressure",
        "category": "infrastructure",
        "risk_level": "low",
        "auto_eligible": True,
        "params": ["host", "log_path"],
        "script_template": "find {log_path} -type f -name '*.log' -exec truncate -s 0 {} \\;",
    },
    "restart_top_consumer": {
        "name": "Restart Top CPU/Memory Consumer",
        "description": (
            "Restart the process consuming the most CPU or memory on a host. "
            "process_name must be supplied by the engineer — FalconOps does not yet ingest "
            "per-process CPU/memory telemetry from OneAgent, so this cannot auto-identify "
            "the process on its own; see the Problems console's 'Live Execution Roadmap' note."
        ),
        "category": "performance",
        "risk_level": "medium",
        "auto_eligible": False,
        "params": ["host", "resource_type", "process_name"],
        "script_template": "systemctl restart {process_name}",
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
    """
    Preview a remediation action: resolves the real command that would run and records
    it for review. This is DRY-RUN ONLY — no subprocess, SSH, or infrastructure API call
    is ever made. See module docstring.
    """
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
        "execution_mode": "dry_run",
        "status": "previewing",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Generate the resolved script
    script = action["script_template"]
    for k, v in params.items():
        script = script.replace(f"{{{k}}}", str(v))
    record["resolved_script"] = script

    # Brief delay to mirror what a real execution round-trip would feel like in the UI —
    # nothing is actually run.
    await asyncio.sleep(0.5)

    record["status"] = "previewed"
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    record["result"] = (
        f"[DRY RUN — NOT EXECUTED] '{action['name']}' was not run against real infrastructure. "
        f"Command that would execute: {script}"
    )

    await db.remediation_history.insert_one(record)
    record.pop("_id", None)

    # Dispatch notification about the preview
    try:
        from .connector_dispatcher import dispatch_event
        await dispatch_event("remediation", {
            "id": record["id"],
            "type": "auto_remediation_preview",
            "title": f"Remediation Preview (Not Executed): {action['name']}",
            "message": f"[DRY RUN] Command: {script}. Trigger: {trigger}. By: {triggered_by}",
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


async def get_remediation_history_for_problem(problem_id: str, limit: int = 50) -> List[Dict]:
    """Remediation records triggered from the Problems console carry
    params.problem_id (see problems_routes.py's /remediate route) — it's
    stored verbatim even though it never matches a {problem_id} placeholder
    in any script_template, purely for this lookup."""
    return await db.remediation_history.find(
        {"params.problem_id": problem_id}, {"_id": 0},
    ).sort("started_at", -1).limit(limit).to_list(limit)


async def get_remediation_stats() -> Dict:
    """Get remediation stats. All executions are dry-run previews — see module docstring."""
    total = await db.remediation_history.count_documents({})
    auto = await db.remediation_history.count_documents({"trigger": "auto"})
    manual = await db.remediation_history.count_documents({"trigger": "manual"})
    previewed = await db.remediation_history.count_documents({"status": "previewed"})
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
        "previewed": previewed,
        "failed": failed,
        "execution_mode": "dry_run",
        "by_category": [{"category": c["_id"], "count": c["count"]} for c in by_category],
        "by_action": [{"action": a["_id"], "count": a["count"]} for a in by_action],
    }
