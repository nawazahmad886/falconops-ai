"""
FalconOps AI - Kubernetes Auto-Healing Service
Generates K8s remediation commands, approval workflows, execution logging
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# ======================== PLAYBOOK DEFINITIONS ========================

PLAYBOOKS = {
    "restart_pod": {
        "id": "restart_pod",
        "name": "Restart Pod",
        "description": "Restarts a specific pod by deleting it (K8s will recreate)",
        "risk_level": "low",
        "auto_approve": True,
        "commands": [
            "kubectl delete pod {pod_name} -n {namespace}",
            "kubectl wait --for=condition=ready pod -l app={app_label} -n {namespace} --timeout=120s",
        ],
    },
    "scale_deployment": {
        "id": "scale_deployment",
        "name": "Scale Deployment",
        "description": "Scales a deployment up or down",
        "risk_level": "low",
        "auto_approve": True,
        "commands": [
            "kubectl scale deployment {deployment} --replicas={replicas} -n {namespace}",
            "kubectl rollout status deployment/{deployment} -n {namespace} --timeout=180s",
        ],
    },
    "rollback_deployment": {
        "id": "rollback_deployment",
        "name": "Rollback Deployment",
        "description": "Rolls back to previous deployment revision",
        "risk_level": "medium",
        "auto_approve": False,
        "commands": [
            "kubectl rollout undo deployment/{deployment} -n {namespace}",
            "kubectl rollout status deployment/{deployment} -n {namespace} --timeout=180s",
        ],
    },
    "drain_node": {
        "id": "drain_node",
        "name": "Drain Node",
        "description": "Cordons and drains a node for maintenance",
        "risk_level": "high",
        "auto_approve": False,
        "commands": [
            "kubectl cordon {node_name}",
            "kubectl drain {node_name} --ignore-daemonsets --delete-emptydir-data --timeout=300s",
        ],
    },
    "restart_deployment": {
        "id": "restart_deployment",
        "name": "Rolling Restart",
        "description": "Performs a rolling restart of all pods in a deployment",
        "risk_level": "medium",
        "auto_approve": False,
        "commands": [
            "kubectl rollout restart deployment/{deployment} -n {namespace}",
            "kubectl rollout status deployment/{deployment} -n {namespace} --timeout=300s",
        ],
    },
    "hpa_adjust": {
        "id": "hpa_adjust",
        "name": "Adjust HPA",
        "description": "Adjusts Horizontal Pod Autoscaler min/max replicas",
        "risk_level": "low",
        "auto_approve": True,
        "commands": [
            "kubectl patch hpa {hpa_name} -n {namespace} -p '{{\"spec\":{{\"minReplicas\":{min_replicas},\"maxReplicas\":{max_replicas}}}}}'",
        ],
    },
}


def get_playbooks() -> List[Dict]:
    return list(PLAYBOOKS.values())


def generate_commands(playbook_id: str, params: Dict) -> Dict:
    pb = PLAYBOOKS.get(playbook_id)
    if not pb:
        return {"error": f"Unknown playbook: {playbook_id}"}

    commands = []
    for cmd_template in pb["commands"]:
        try:
            cmd = cmd_template.format(**params)
        except KeyError as e:
            cmd = f"# Missing parameter: {e} — {cmd_template}"
        commands.append(cmd)

    return {
        "playbook_id": playbook_id,
        "playbook_name": pb["name"],
        "risk_level": pb["risk_level"],
        "auto_approve": pb["auto_approve"],
        "commands": commands,
        "params_used": params,
    }


async def create_execution(playbook_id: str, params: Dict, requested_by: str, auto_approved: bool = False) -> Dict:
    pb = PLAYBOOKS.get(playbook_id)
    if not pb:
        return {"error": "Unknown playbook"}

    gen = generate_commands(playbook_id, params)

    doc = {
        "id": str(uuid.uuid4()),
        "playbook_id": playbook_id,
        "playbook_name": pb["name"],
        "risk_level": pb["risk_level"],
        "commands": gen["commands"],
        "params": params,
        "requested_by": requested_by,
        "status": "approved" if (pb["auto_approve"] or auto_approved) else "pending_approval",
        "approved_by": "auto" if pb["auto_approve"] else None,
        "execution_log": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "executed_at": None,
        "completed_at": None,
    }

    # Simulate execution for auto-approved low-risk actions
    if doc["status"] == "approved":
        doc["status"] = "executed"
        doc["executed_at"] = datetime.now(timezone.utc).isoformat()
        doc["execution_log"] = [
            {"step": i + 1, "command": cmd, "status": "simulated_success", "output": "[Simulated] Command executed successfully"}
            for i, cmd in enumerate(gen["commands"])
        ]
        doc["completed_at"] = datetime.now(timezone.utc).isoformat()

    await db.k8s_executions.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def approve_execution(execution_id: str, approved_by: str) -> Dict:
    ex = await db.k8s_executions.find_one({"id": execution_id}, {"_id": 0})
    if not ex:
        return {"error": "Not found"}
    if ex["status"] != "pending_approval":
        return {"error": f"Cannot approve: status is {ex['status']}"}

    log = [
        {"step": i + 1, "command": cmd, "status": "simulated_success", "output": "[Simulated] Command executed"}
        for i, cmd in enumerate(ex.get("commands", []))
    ]

    await db.k8s_executions.update_one({"id": execution_id}, {"$set": {
        "status": "executed",
        "approved_by": approved_by,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_log": log,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"id": execution_id, "status": "executed"}


async def reject_execution(execution_id: str, rejected_by: str) -> Dict:
    await db.k8s_executions.update_one({"id": execution_id}, {"$set": {
        "status": "rejected", "approved_by": rejected_by,
    }})
    return {"id": execution_id, "status": "rejected"}


async def get_executions(status: str = None, limit: int = 30) -> List[Dict]:
    query = {}
    if status:
        query["status"] = status
    return await db.k8s_executions.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


async def get_k8s_stats() -> Dict:
    total = await db.k8s_executions.count_documents({})
    pending = await db.k8s_executions.count_documents({"status": "pending_approval"})
    executed = await db.k8s_executions.count_documents({"status": "executed"})
    rejected = await db.k8s_executions.count_documents({"status": "rejected"})
    return {"total": total, "pending_approval": pending, "executed": executed, "rejected": rejected}
