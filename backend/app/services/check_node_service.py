"""
FalconOps AI - Distributed Check Node Service
Manages external check nodes that run uptime checks from different regions
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


async def register_node(name: str, region: str, ip: str, version: str = "1.0.0", capabilities: list = None) -> Dict:
    existing = await db.check_nodes.find_one({"ip": ip, "region": region}, {"_id": 0})
    if existing:
        await db.check_nodes.update_one({"id": existing["id"]}, {"$set": {
            "name": name, "version": version, "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "status": "online", "capabilities": capabilities or ["http", "https"],
        }})
        existing.update({"name": name, "status": "online"})
        return existing

    doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "region": region,
        "ip": ip,
        "version": version,
        "status": "online",
        "capabilities": capabilities or ["http", "https"],
        "checks_performed": 0,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.check_nodes.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def heartbeat(node_id: str, metrics: dict = None) -> Dict:
    await db.check_nodes.update_one({"id": node_id}, {"$set": {
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "status": "online",
        "node_metrics": metrics or {},
    }})
    return {"status": "ok"}


async def get_nodes(region: str = None) -> List[Dict]:
    query = {}
    if region:
        query["region"] = region
    nodes = await db.check_nodes.find(query, {"_id": 0}).sort("registered_at", -1).to_list(200)
    now = datetime.now(timezone.utc)
    for n in nodes:
        hb = n.get("last_heartbeat", "")
        if hb:
            try:
                hb_time = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                age = (now - hb_time).total_seconds()
                n["status"] = "online" if age < 120 else "stale" if age < 600 else "offline"
            except Exception:
                n["status"] = "offline"
    return nodes


async def get_node(node_id: str) -> Optional[Dict]:
    return await db.check_nodes.find_one({"id": node_id}, {"_id": 0})


async def delete_node(node_id: str) -> bool:
    r = await db.check_nodes.delete_one({"id": node_id})
    return r.deleted_count > 0


async def get_node_monitors(node_id: str) -> List[Dict]:
    """Get monitors assigned to this node's region"""
    node = await get_node(node_id)
    if not node:
        return []
    region = node.get("region", "us-east")
    monitors = await db.uptime_monitors.find(
        {"enabled": True, "regions": region}, {"_id": 0}
    ).to_list(200)
    return monitors


async def submit_check_result(node_id: str, result: Dict) -> Dict:
    """Accept check result from external node"""
    result["node_id"] = node_id
    result.setdefault("id", str(uuid.uuid4()))
    result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    await db.uptime_checks.insert_one(result)
    result.pop("_id", None)
    await db.check_nodes.update_one({"id": node_id}, {"$inc": {"checks_performed": 1}})
    return {"status": "ok", "check_id": result["id"]}


async def get_node_stats() -> Dict:
    nodes = await get_nodes()
    total = len(nodes)
    online = sum(1 for n in nodes if n.get("status") == "online")
    regions = {}
    for n in nodes:
        r = n.get("region", "unknown")
        if r not in regions:
            regions[r] = {"total": 0, "online": 0}
        regions[r]["total"] += 1
        if n.get("status") == "online":
            regions[r]["online"] += 1
    total_checks = sum(n.get("checks_performed", 0) for n in nodes)
    return {
        "total_nodes": total,
        "online": online,
        "offline": total - online,
        "total_checks": total_checks,
        "by_region": regions,
    }
