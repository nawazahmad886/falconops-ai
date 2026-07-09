"""
FalconOps AI - Network Topology Routes
Service dependency mapping and visualization
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import (
    ServiceDependency, ServiceDependencyCreate, 
    TopologyNode, TopologyEdge, NetworkTopologyResponse, TracerouteResponse
)
from ..utils.auth import require_auth, require_write_access, get_current_user

router = APIRouter(prefix="/api/topology", tags=["Topology"])


def _tid(user):
    return user.get("tenant_id") if user else None


@router.get("", response_model=NetworkTopologyResponse)
async def get_network_topology(
    environment: Optional[str] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get complete network topology with nodes, edges, and health analysis"""
    tid = _tid(current_user)
    query = {"enabled": True}
    if tid:
        query["tenant_id"] = tid
    if environment:
        query["environment"] = environment
    
    monitors = await db.monitors.find(query, {"_id": 0}).to_list(500)
    dep_q = {"tenant_id": tid} if tid else {}
    dependencies = await db.service_dependencies.find(dep_q, {"_id": 0}).to_list(1000)
    
    dep_map = {}
    dependent_map = {}
    for dep in dependencies:
        source = dep["source_monitor_id"]
        target = dep["target_monitor_id"]
        if source not in dep_map:
            dep_map[source] = []
        dep_map[source].append(target)
        if target not in dependent_map:
            dependent_map[target] = []
        dependent_map[target].append(source)
    
    nodes = []
    for m in monitors:
        mid = m["id"]
        
        status = m.get("status", "unknown")
        if status == "up":
            health = 100
        elif status == "degraded":
            health = 70
        elif status == "timeout":
            health = 30
        else:
            health = 0
        
        nodes.append(TopologyNode(
            id=mid,
            name=m["name"],
            type=m["monitor_type"],
            target=m["target"],
            status=status,
            health_score=health,
            latency_ms=m.get("last_latency_ms"),
            environment=m.get("environment"),
            dependencies=dep_map.get(mid, []),
            dependents=dependent_map.get(mid, [])
        ))
    
    edges = []
    for dep in dependencies:
        source_monitor = next((m for m in monitors if m["id"] == dep["source_monitor_id"]), None)
        target_monitor = next((m for m in monitors if m["id"] == dep["target_monitor_id"]), None)
        
        if source_monitor and target_monitor:
            source_status = source_monitor.get("status", "unknown")
            target_status = target_monitor.get("status", "unknown")
            
            if source_status == "up" and target_status == "up":
                edge_status = "healthy"
            elif source_status in ["down", "timeout"] or target_status in ["down", "timeout"]:
                edge_status = "critical"
            else:
                edge_status = "degraded"
            
            edges.append(TopologyEdge(
                source=dep["source_monitor_id"],
                target=dep["target_monitor_id"],
                dependency_type=dep.get("dependency_type", "depends_on"),
                status=edge_status,
                latency_impact=target_monitor.get("last_latency_ms")
            ))
    
    down_monitors = [m for m in monitors if m.get("status") in ["down", "timeout"]]
    cascade_risks = []
    for dm in down_monitors:
        dependents = dependent_map.get(dm["id"], [])
        if len(dependents) > 0:
            cascade_risks.append({
                "source_monitor": dm["name"],
                "source_id": dm["id"],
                "affected_services": len(dependents),
                "dependent_ids": dependents,
                "severity": "critical" if len(dependents) >= 3 else "warning"
            })
    
    health_summary = {
        "total_services": len(monitors),
        "healthy": sum(1 for m in monitors if m.get("status") == "up"),
        "degraded": sum(1 for m in monitors if m.get("status") == "degraded"),
        "down": sum(1 for m in monitors if m.get("status") in ["down", "timeout"]),
        "total_dependencies": len(dependencies),
        "cascade_risk_count": len(cascade_risks)
    }
    
    return NetworkTopologyResponse(
        nodes=nodes,
        edges=edges,
        health_summary=health_summary,
        critical_paths=[],
        cascade_risks=cascade_risks
    )


@router.get("/dependencies")
async def get_dependencies(current_user: Optional[dict] = Depends(get_current_user)):
    """Get all service dependencies"""
    deps = await db.service_dependencies.find({}, {"_id": 0}).to_list(1000)
    return deps


@router.post("/dependencies")
async def create_dependency(dep: ServiceDependencyCreate, current_user: dict = Depends(require_write_access)):
    """Create a service dependency"""
    source = await db.monitors.find_one({"id": dep.source_monitor_id})
    target = await db.monitors.find_one({"id": dep.target_monitor_id})
    
    if not source or not target:
        raise HTTPException(status_code=404, detail="Source or target monitor not found")
    
    existing = await db.service_dependencies.find_one({
        "source_monitor_id": dep.source_monitor_id,
        "target_monitor_id": dep.target_monitor_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")
    
    dep_doc = {
        "id": str(uuid.uuid4()),
        "source_monitor_id": dep.source_monitor_id,
        "target_monitor_id": dep.target_monitor_id,
        "dependency_type": dep.dependency_type,
        "description": dep.description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.service_dependencies.insert_one(dep_doc)
    return {k: v for k, v in dep_doc.items() if k != "_id"}


@router.delete("/dependencies/{dep_id}")
async def delete_dependency(dep_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a service dependency"""
    result = await db.service_dependencies.delete_one({"id": dep_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dependency not found")
    return {"message": "Dependency deleted"}


@router.get("/impact/{monitor_id}")
async def get_impact_analysis(monitor_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Analyze the potential impact if a service goes down"""
    monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    dependencies = await db.service_dependencies.find({}, {"_id": 0}).to_list(1000)
    
    def find_dependents(mid, visited=None):
        if visited is None:
            visited = set()
        if mid in visited:
            return []
        visited.add(mid)
        
        direct = [d["source_monitor_id"] for d in dependencies if d["target_monitor_id"] == mid]
        all_deps = list(direct)
        
        for dep_id in direct:
            all_deps.extend(find_dependents(dep_id, visited))
        
        return all_deps
    
    affected_ids = find_dependents(monitor_id)
    affected_monitors = await db.monitors.find({"id": {"$in": affected_ids}}, {"_id": 0}).to_list(100)
    
    return {
        "monitor": monitor,
        "direct_dependents": len([d for d in dependencies if d["target_monitor_id"] == monitor_id]),
        "total_cascade_impact": len(affected_ids),
        "affected_services": [{"id": m["id"], "name": m["name"], "status": m.get("status")} for m in affected_monitors],
        "severity": "critical" if len(affected_ids) >= 5 else "warning" if len(affected_ids) >= 2 else "low"
    }


@router.post("/{monitor_id}/traceroute", response_model=TracerouteResponse)
async def perform_traceroute(monitor_id: str, current_user: dict = Depends(require_auth)):
    """Perform traceroute to a monitor target (simulated)"""
    import socket
    import random
    
    monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    target = monitor["target"].replace("https://", "").replace("http://", "").split("/")[0]
    
    try:
        target_ip = socket.gethostbyname(target)
    except socket.gaierror:
        return TracerouteResponse(
            monitor_id=monitor_id,
            target=target,
            total_hops=0,
            destination_reached=False,
            failure_hop=1,
            hops=[],
            analysis={"error": "DNS resolution failed"},
            executed_at=datetime.now(timezone.utc).isoformat()
        )
    
    hops = []
    num_hops = random.randint(8, 15)
    
    for i in range(1, num_hops + 1):
        is_dest = (i == num_hops)
        hops.append({
            "hop_number": i,
            "hostname": target if is_dest else f"router-{i}.network.local",
            "ip_address": target_ip if is_dest else f"10.{random.randint(0,255)}.{random.randint(0,255)}.{i}",
            "latency_ms": round(random.uniform(1, 50) * i / 2, 2),
            "status": "success",
            "is_destination": is_dest,
            "location": "Destination" if is_dest else f"Hop {i}"
        })
    
    return TracerouteResponse(
        monitor_id=monitor_id,
        target=target,
        total_hops=num_hops,
        destination_reached=True,
        failure_hop=None,
        hops=hops,
        analysis={"status": "healthy", "avg_latency": round(sum(h["latency_ms"] for h in hops) / len(hops), 2)},
        executed_at=datetime.now(timezone.utc).isoformat()
    )
