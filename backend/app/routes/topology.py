"""
FalconOps AI - Network Topology Routes
Service dependency mapping and visualization
"""
import asyncio
import logging
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import (
    ServiceDependency, ServiceDependencyCreate,
    TopologyNode, TopologyEdge, NetworkTopologyResponse, TracerouteResponse, TracerouteHop
)
from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services import network_path_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topology", tags=["Topology"])

TRACEROUTE_RATE_LIMIT = (5, 60)  # 5 traces / minute per user


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
    """Real network path analysis: ICMP TTL traceroute (per-hop packet loss/jitter,
    reverse DNS, GeoIP/ASN/proxy enrichment) plus DNS/TCP/TLS timing to the actual
    destination, with routing-loop/route-change/likely-blocked detection."""
    from ..services.rate_limiter_service import is_rate_limited

    if await is_rate_limited(f"traceroute:{current_user['id']}", *TRACEROUTE_RATE_LIMIT):
        raise HTTPException(status_code=429, detail="Too many traceroute requests. Please try again shortly.")

    tid = _tid(current_user)
    query = {"id": monitor_id}
    if tid:
        query["tenant_id"] = tid
    monitor = await db.monitors.find_one(query, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    raw_target = monitor["target"]
    scheme_hint = "https" if raw_target.startswith("https://") else "http"
    hostname = raw_target.replace("https://", "").replace("http://", "").split("/")[0]
    monitor_port = monitor.get("port")
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        target_ip = await asyncio.to_thread(socket.gethostbyname, hostname)
    except socket.gaierror:
        return TracerouteResponse(
            monitor_id=monitor_id,
            target=hostname,
            total_hops=0,
            destination_reached=False,
            failure_hop=1,
            hops=[],
            analysis={"error": "DNS resolution failed"},
            executed_at=now_iso,
        )

    trace_result, endpoint_result = await asyncio.gather(
        network_path_service.run_traceroute(target_ip),
        network_path_service.measure_endpoint(hostname, target_ip, monitor_port, scheme_hint),
    )

    if trace_result["probe_method"] == "unavailable":
        return TracerouteResponse(
            monitor_id=monitor_id,
            target=hostname,
            total_hops=0,
            destination_reached=endpoint_result["tcp_reachable"],
            failure_hop=None,
            hops=[],
            analysis={
                "status": "degraded",
                "issue": "ICMP raw-socket probing unavailable in this environment (missing CAP_NET_RAW)",
                "recommendation": "Add cap_add: [NET_RAW] to the backend service and rebuild — see docker-compose.yml",
            },
            executed_at=now_iso,
            probe_method="unavailable",
            dns_resolution_ms=endpoint_result["dns_resolution_ms"],
            tcp_connect_ms=endpoint_result["tcp_connect_ms"],
            tls_handshake_ms=endpoint_result["tls_handshake_ms"],
            target_port=endpoint_result["target_port"],
            tcp_reachable=endpoint_result["tcp_reachable"],
        )

    raw_hops = trace_result["hops"]
    await network_path_service.enrich_hops(raw_hops)

    hops: List[TracerouteHop] = []
    for h in raw_hops:
        is_dest = bool(h.get("reached_destination"))
        status = "success" if h.get("responder_ip") else "timeout"
        hops.append(TracerouteHop(
            hop_number=h["hop_number"],
            hostname=h.get("hostname") or h.get("responder_ip"),
            ip_address=h.get("responder_ip"),
            latency_ms=h.get("avg_rtt_ms"),
            status=status,
            is_destination=is_dest,
            location=h.get("location") or None,
            rtt_samples_ms=h.get("rtt_samples_ms"),
            packet_loss_pct=h.get("packet_loss_pct"),
            jitter_ms=h.get("jitter_ms"),
            asn=h.get("asn"),
            isp=h.get("isp"),
            org=h.get("org"),
            is_proxy_or_vpn=h.get("is_proxy_or_vpn"),
            is_hosting=h.get("is_hosting"),
        ))

    loss_values = [h.packet_loss_pct for h in hops if h.packet_loss_pct is not None]
    jitter_values = [h.jitter_ms for h in hops if h.jitter_ms is not None]
    avg_loss = round(sum(loss_values) / len(loss_values), 1) if loss_values else None
    avg_jitter = round(sum(jitter_values) / len(jitter_values), 2) if jitter_values else None

    hop_ips = [h.ip_address for h in hops]
    routing_loop = network_path_service.detect_routing_loop(hop_ips)

    previous_hop_ips = None
    route_changed = None
    try:
        await _ensure_history_indexes()
        prev_doc = await db.traceroute_history.find_one(
            {"monitor_id": monitor_id}, {"_id": 0}, sort=[("executed_at", -1)]
        )
        if prev_doc:
            previous_hop_ips = prev_doc.get("hop_ips")
            route_changed = network_path_service.detect_route_change(hop_ips, previous_hop_ips)
        await db.traceroute_history.insert_one({
            "id": str(uuid.uuid4()),
            "monitor_id": monitor_id,
            "tenant_id": tid,
            "target": hostname,
            "target_ip": target_ip,
            "hop_ips": hop_ips,
            "destination_reached": trace_result["destination_reached"],
            "executed_at": now_iso,
        })
    except Exception as e:
        logger.debug(f"traceroute_history read/write skipped: {e}")

    blocked_likely = network_path_service.detect_blocked_likely(
        raw_hops, trace_result["destination_reached"], endpoint_result["tcp_reachable"]
    )

    if routing_loop:
        analysis = {"status": "unhealthy", "issue": "Routing loop detected",
                    "warning": f"IP {routing_loop['looped_ip']} seen again at hop {routing_loop['repeat_hop']} "
                               f"(first seen at hop {routing_loop['first_hop']})"}
    elif blocked_likely:
        analysis = {"status": "unhealthy", "issue": "Path likely blocked by a firewall/WAF",
                    "warning": "Hops stopped responding and the service port is also unreachable",
                    "failure_point": f"hop {trace_result.get('failure_hop')}" if trace_result.get("failure_hop") else None}
    elif not trace_result["destination_reached"]:
        analysis = {"status": "unhealthy", "issue": "Destination not reached",
                    "failure_point": f"hop {trace_result.get('failure_hop')}" if trace_result.get("failure_hop") else None}
    elif (avg_loss or 0) > 0 or route_changed:
        msg = []
        if avg_loss:
            msg.append(f"{avg_loss}% average packet loss across hops")
        if route_changed:
            msg.append("network path changed since the previous trace")
        analysis = {"status": "connected_with_warnings", "warning": "; ".join(msg)}
    else:
        analysis = {"status": "healthy", "message": "Network path is healthy",
                    "avg_latency": round(sum(h.latency_ms for h in hops if h.latency_ms is not None) / max(len([h for h in hops if h.latency_ms is not None]), 1), 2) if hops else None}

    return TracerouteResponse(
        monitor_id=monitor_id,
        target=hostname,
        total_hops=len(hops),
        destination_reached=trace_result["destination_reached"],
        failure_hop=trace_result.get("failure_hop"),
        hops=hops,
        analysis=analysis,
        executed_at=now_iso,
        probe_method=trace_result["probe_method"],
        dns_resolution_ms=endpoint_result["dns_resolution_ms"],
        tcp_connect_ms=endpoint_result["tcp_connect_ms"],
        tls_handshake_ms=endpoint_result["tls_handshake_ms"],
        target_port=endpoint_result["target_port"],
        tcp_reachable=endpoint_result["tcp_reachable"],
        avg_packet_loss_pct=avg_loss,
        avg_jitter_ms=avg_jitter,
        routing_loop_detected=bool(routing_loop),
        routing_loop_detail=routing_loop,
        route_changed=route_changed,
        previous_hop_ips=previous_hop_ips,
        blocked_likely=blocked_likely,
    )


_history_index_ready = False


async def _ensure_history_indexes():
    global _history_index_ready
    if _history_index_ready:
        return
    try:
        await db.traceroute_history.create_index([("monitor_id", 1), ("executed_at", -1)], name="mon_time")
        await db.traceroute_history.create_index("executed_at", expireAfterSeconds=90 * 24 * 3600, name="history_ttl")
        _history_index_ready = True
    except Exception as e:
        logger.debug(f"traceroute_history index create skipped: {e}")
