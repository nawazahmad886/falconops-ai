"""
FalconOps AI - Topology Service
Service dependency mapping and topology visualization
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from ..core.database import db

# Service Types
SERVICE_TYPES = [
    {"id": "frontend", "name": "Frontend", "icon": "globe", "color": "#3B82F6"},
    {"id": "api", "name": "API Gateway", "icon": "network", "color": "#8B5CF6"},
    {"id": "backend", "name": "Backend Service", "icon": "server", "color": "#10B981"},
    {"id": "database", "name": "Database", "icon": "database", "color": "#F59E0B"},
    {"id": "cache", "name": "Cache", "icon": "zap", "color": "#EF4444"},
    {"id": "queue", "name": "Message Queue", "icon": "layers", "color": "#EC4899"},
    {"id": "external", "name": "External Service", "icon": "external-link", "color": "#6B7280"},
    {"id": "storage", "name": "Storage", "icon": "hard-drive", "color": "#14B8A6"},
]

# Connection Types
CONNECTION_TYPES = [
    {"id": "http", "name": "HTTP/REST", "style": "solid"},
    {"id": "grpc", "name": "gRPC", "style": "dashed"},
    {"id": "tcp", "name": "TCP", "style": "solid"},
    {"id": "async", "name": "Async/Queue", "style": "dotted"},
    {"id": "database", "name": "Database", "style": "solid"},
]


class TopologyService:
    """Service for managing service topology and dependencies"""
    
    async def create_service_node(
        self,
        name: str,
        service_type: str,
        environment: str = "production",
        owner: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Register a service node in the topology"""
        service_id = str(uuid.uuid4())
        
        service_doc = {
            "id": service_id,
            "name": name,
            "type": service_type,
            "environment": environment,
            "owner": owner,
            "description": description,
            "tags": tags or [],
            "metadata": metadata or {},
            "status": "healthy",
            "health_score": 100,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.topology_nodes.insert_one(service_doc)
        return {k: v for k, v in service_doc.items() if k != "_id"}
    
    async def update_service_node(
        self,
        service_id: str,
        updates: Dict
    ) -> Optional[Dict]:
        """Update a service node"""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.topology_nodes.find_one_and_update(
            {"id": service_id},
            {"$set": updates},
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def delete_service_node(self, service_id: str) -> bool:
        """Delete a service node and its connections"""
        # Delete the node
        result = await db.topology_nodes.delete_one({"id": service_id})
        
        # Delete associated connections
        await db.topology_edges.delete_many({
            "$or": [
                {"source_id": service_id},
                {"target_id": service_id}
            ]
        })
        
        return result.deleted_count > 0
    
    async def create_connection(
        self,
        source_id: str,
        target_id: str,
        connection_type: str = "http",
        protocol: Optional[str] = None,
        latency_p50: Optional[float] = None,
        latency_p99: Optional[float] = None,
        request_rate: Optional[float] = None,
        error_rate: Optional[float] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Create a connection between two services"""
        connection_id = str(uuid.uuid4())
        
        connection_doc = {
            "id": connection_id,
            "source_id": source_id,
            "target_id": target_id,
            "type": connection_type,
            "protocol": protocol,
            "metrics": {
                "latency_p50": latency_p50,
                "latency_p99": latency_p99,
                "request_rate": request_rate,
                "error_rate": error_rate
            },
            "status": "healthy",
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.topology_edges.insert_one(connection_doc)
        return {k: v for k, v in connection_doc.items() if k != "_id"}
    
    async def update_connection_metrics(
        self,
        connection_id: str,
        latency_p50: Optional[float] = None,
        latency_p99: Optional[float] = None,
        request_rate: Optional[float] = None,
        error_rate: Optional[float] = None
    ) -> Optional[Dict]:
        """Update connection metrics"""
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if latency_p50 is not None:
            updates["metrics.latency_p50"] = latency_p50
        if latency_p99 is not None:
            updates["metrics.latency_p99"] = latency_p99
        if request_rate is not None:
            updates["metrics.request_rate"] = request_rate
        if error_rate is not None:
            updates["metrics.error_rate"] = error_rate
            
        # Update status based on error rate
        if error_rate is not None:
            if error_rate > 10:
                updates["status"] = "critical"
            elif error_rate > 5:
                updates["status"] = "degraded"
            else:
                updates["status"] = "healthy"
        
        result = await db.topology_edges.find_one_and_update(
            {"id": connection_id},
            {"$set": updates},
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection"""
        result = await db.topology_edges.delete_one({"id": connection_id})
        return result.deleted_count > 0
    
    async def get_topology(
        self,
        environment: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Get full topology (nodes and edges)"""
        node_query = {}
        edge_query = {}
        
        if tenant_id:
            node_query["tenant_id"] = tenant_id
            edge_query["tenant_id"] = tenant_id
        
        if environment:
            node_query["environment"] = environment
        
        nodes = await db.topology_nodes.find(node_query, {"_id": 0}).to_list(500)
        edges = await db.topology_edges.find(edge_query, {"_id": 0}).to_list(1000)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "environment": environment
        }
    
    async def get_service_node(self, service_id: str) -> Optional[Dict]:
        """Get a single service node"""
        node = await db.topology_nodes.find_one({"id": service_id}, {"_id": 0})
        return node
    
    async def get_service_by_name(
        self,
        name: str,
        environment: str = "production",
        tenant_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Get a service node by name"""
        query = {"name": name, "environment": environment}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        node = await db.topology_nodes.find_one(query, {"_id": 0})
        return node
    
    async def get_service_dependencies(
        self,
        service_id: str,
        direction: str = "both"
    ) -> Dict:
        """Get dependencies for a specific service"""
        upstream = []
        downstream = []
        
        if direction in ["both", "upstream"]:
            # Services that THIS service depends on
            upstream_edges = await db.topology_edges.find(
                {"source_id": service_id}, {"_id": 0}
            ).to_list(100)
            
            for edge in upstream_edges:
                target = await self.get_service_node(edge["target_id"])
                if target:
                    upstream.append({
                        "service": target,
                        "connection": edge
                    })
        
        if direction in ["both", "downstream"]:
            # Services that depend on THIS service
            downstream_edges = await db.topology_edges.find(
                {"target_id": service_id}, {"_id": 0}
            ).to_list(100)
            
            for edge in downstream_edges:
                source = await self.get_service_node(edge["source_id"])
                if source:
                    downstream.append({
                        "service": source,
                        "connection": edge
                    })
        
        return {
            "service_id": service_id,
            "upstream_dependencies": upstream,
            "downstream_dependents": downstream,
            "total_upstream": len(upstream),
            "total_downstream": len(downstream)
        }
    
    async def get_impacted_services(
        self,
        service_id: str,
        depth: int = 3
    ) -> List[Dict]:
        """Get services that would be impacted if the given service fails"""
        impacted = []
        visited = {service_id}
        queue = [service_id]
        current_depth = 0
        
        while queue and current_depth < depth:
            current_depth += 1
            next_queue = []
            
            for sid in queue:
                # Find services that depend on this one
                downstream_edges = await db.topology_edges.find(
                    {"target_id": sid}, {"_id": 0}
                ).to_list(100)
                
                for edge in downstream_edges:
                    if edge["source_id"] not in visited:
                        visited.add(edge["source_id"])
                        next_queue.append(edge["source_id"])
                        
                        service = await self.get_service_node(edge["source_id"])
                        if service:
                            impacted.append({
                                "service": service,
                                "impact_depth": current_depth,
                                "connection": edge
                            })
            
            queue = next_queue
        
        return impacted
    
    async def update_service_health(
        self,
        service_id: str,
        status: str,
        health_score: int
    ) -> Optional[Dict]:
        """Update service health status"""
        updates = {
            "status": status,
            "health_score": health_score,
            "last_seen": datetime.now(timezone.utc).isoformat()
        }
        
        return await self.update_service_node(service_id, updates)
    
    async def get_topology_stats(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Get topology statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        total_nodes = await db.topology_nodes.count_documents(query)
        total_edges = await db.topology_edges.count_documents(query)
        
        # Count by type
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_type = await db.topology_nodes.aggregate(pipeline).to_list(20)
        
        # Count by status
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_status = await db.topology_nodes.aggregate(pipeline).to_list(10)
        
        # Count by environment
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$environment", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_env = await db.topology_nodes.aggregate(pipeline).to_list(10)
        
        # Unhealthy services
        unhealthy_query = {**query, "status": {"$ne": "healthy"}}
        unhealthy = await db.topology_nodes.find(
            unhealthy_query, {"_id": 0}
        ).limit(10).to_list(10)
        
        return {
            "total_services": total_nodes,
            "total_connections": total_edges,
            "by_type": [{"type": r["_id"], "count": r["count"]} for r in by_type],
            "by_status": [{"status": r["_id"], "count": r["count"]} for r in by_status],
            "by_environment": [{"environment": r["_id"], "count": r["count"]} for r in by_env],
            "unhealthy_services": unhealthy
        }
    
    async def auto_discover_from_traces(
        self,
        trace_data: List[Dict],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Auto-discover topology from distributed traces"""
        discovered_services = set()
        discovered_connections = {}
        
        for trace in trace_data:
            service = trace.get("service")
            parent_service = trace.get("parent_service")
            
            if service:
                discovered_services.add(service)
            if parent_service:
                discovered_services.add(parent_service)
                
                # Track connection
                connection_key = f"{parent_service}->{service}"
                if connection_key not in discovered_connections:
                    discovered_connections[connection_key] = {
                        "source": parent_service,
                        "target": service,
                        "count": 0
                    }
                discovered_connections[connection_key]["count"] += 1
        
        # Create service nodes
        created_nodes = []
        for service_name in discovered_services:
            existing = await self.get_service_by_name(service_name, tenant_id=tenant_id)
            if not existing:
                node = await self.create_service_node(
                    name=service_name,
                    service_type="backend",
                    tenant_id=tenant_id
                )
                created_nodes.append(node)
        
        # Create connections
        created_edges = []
        for conn in discovered_connections.values():
            source = await self.get_service_by_name(conn["source"], tenant_id=tenant_id)
            target = await self.get_service_by_name(conn["target"], tenant_id=tenant_id)
            
            if source and target:
                # Check if connection exists
                existing = await db.topology_edges.find_one({
                    "source_id": source["id"],
                    "target_id": target["id"]
                })
                
                if not existing:
                    edge = await self.create_connection(
                        source_id=source["id"],
                        target_id=target["id"],
                        tenant_id=tenant_id
                    )
                    created_edges.append(edge)
        
        return {
            "discovered_services": list(discovered_services),
            "discovered_connections": list(discovered_connections.keys()),
            "created_nodes": len(created_nodes),
            "created_edges": len(created_edges)
        }


# Service types and connection types for API
def get_service_types() -> List[Dict]:
    return SERVICE_TYPES

def get_connection_types() -> List[Dict]:
    return CONNECTION_TYPES


# Singleton instance
topology_service = TopologyService()
