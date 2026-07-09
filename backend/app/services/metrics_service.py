"""
FalconOps AI - Metrics Service
Metrics ingestion, storage, and querying for monitoring
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from ..core.database import db

# Metric aggregation types
AGGREGATIONS = ["avg", "min", "max", "sum", "count", "p50", "p90", "p95", "p99"]

# Metric resolutions (rollup intervals)
RESOLUTIONS = [
    {"id": "1m", "label": "1 minute", "seconds": 60},
    {"id": "5m", "label": "5 minutes", "seconds": 300},
    {"id": "15m", "label": "15 minutes", "seconds": 900},
    {"id": "1h", "label": "1 hour", "seconds": 3600},
    {"id": "6h", "label": "6 hours", "seconds": 21600},
    {"id": "1d", "label": "1 day", "seconds": 86400},
]


class MetricsService:
    """Service for managing metrics ingestion and querying"""
    
    async def ingest_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
        service: Optional[str] = None,
        host: Optional[str] = None,
        timestamp: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest a single metric data point"""
        metric_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        
        metric_doc = {
            "id": metric_id,
            "name": name,
            "value": value,
            "unit": unit,
            "tags": tags or {},
            "service": service,
            "host": host,
            "timestamp": ts,
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.metrics.insert_one(metric_doc)
        return {k: v for k, v in metric_doc.items() if k != "_id"}
    
    async def ingest_batch(
        self,
        metrics: List[Dict],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest multiple metrics at once"""
        docs = []
        now = datetime.now(timezone.utc).isoformat()
        
        for metric in metrics:
            doc = {
                "id": str(uuid.uuid4()),
                "name": metric.get("name"),
                "value": metric.get("value"),
                "unit": metric.get("unit", ""),
                "tags": metric.get("tags", {}),
                "service": metric.get("service"),
                "host": metric.get("host"),
                "timestamp": metric.get("timestamp", now),
                "tenant_id": tenant_id,
                "created_at": now
            }
            docs.append(doc)
        
        if docs:
            await db.metrics.insert_many(docs)
        
        return {
            "ingested": len(docs),
            "timestamp": now
        }
    
    async def query_metrics(
        self,
        name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        service: Optional[str] = None,
        host: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        aggregation: str = "avg",
        resolution: str = "5m",
        tenant_id: Optional[str] = None,
        limit: int = 1000
    ) -> Dict:
        """Query metrics with optional aggregation"""
        query = {"name": name}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        if service:
            query["service"] = service
        if host:
            query["host"] = host
        if tags:
            for key, value in tags.items():
                query[f"tags.{key}"] = value
        
        # Time range
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        if not end_time:
            end_time = datetime.now(timezone.utc).isoformat()
        
        query["timestamp"] = {"$gte": start_time, "$lte": end_time}
        
        # Fetch raw data
        raw_metrics = await db.metrics.find(
            query, {"_id": 0, "value": 1, "timestamp": 1, "service": 1, "host": 1}
        ).sort("timestamp", 1).limit(limit).to_list(limit)
        
        # Aggregate if needed
        if aggregation != "raw" and raw_metrics:
            aggregated = self._aggregate_metrics(raw_metrics, aggregation)
            return {
                "name": name,
                "aggregation": aggregation,
                "resolution": resolution,
                "start_time": start_time,
                "end_time": end_time,
                "data_points": len(raw_metrics),
                "value": aggregated,
                "service": service,
                "host": host
            }
        
        return {
            "name": name,
            "aggregation": "raw",
            "start_time": start_time,
            "end_time": end_time,
            "data_points": len(raw_metrics),
            "metrics": raw_metrics,
            "service": service,
            "host": host
        }
    
    def _aggregate_metrics(self, metrics: List[Dict], aggregation: str) -> float:
        """Perform aggregation on metrics"""
        if not metrics:
            return 0.0
        
        values = [m["value"] for m in metrics if m.get("value") is not None]
        
        if not values:
            return 0.0
        
        if aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "min":
            return min(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "sum":
            return sum(values)
        elif aggregation == "count":
            return len(values)
        elif aggregation == "p50":
            return self._percentile(values, 50)
        elif aggregation == "p90":
            return self._percentile(values, 90)
        elif aggregation == "p95":
            return self._percentile(values, 95)
        elif aggregation == "p99":
            return self._percentile(values, 99)
        
        return sum(values) / len(values)
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    async def get_latest_metrics(
        self,
        service: Optional[str] = None,
        host: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get the latest metrics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        if service:
            query["service"] = service
        if host:
            query["host"] = host
        
        # Get unique metric names first
        pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$name",
                "latest_value": {"$first": "$value"},
                "latest_timestamp": {"$first": "$timestamp"},
                "service": {"$first": "$service"},
                "host": {"$first": "$host"},
                "unit": {"$first": "$unit"}
            }},
            {"$limit": limit}
        ]
        
        results = await db.metrics.aggregate(pipeline).to_list(limit)
        
        return [{
            "name": r["_id"],
            "value": r["latest_value"],
            "timestamp": r["latest_timestamp"],
            "service": r["service"],
            "host": r["host"],
            "unit": r["unit"]
        } for r in results]
    
    async def get_metric_names(
        self,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[str]:
        """Get all unique metric names"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        if service:
            query["service"] = service
        
        names = await db.metrics.distinct("name", query)
        return names
    
    async def get_metric_stats(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Get metrics statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        total_metrics = await db.metrics.count_documents(query)
        
        # Count by service
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$service", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        by_service = await db.metrics.aggregate(pipeline).to_list(10)
        
        # Count by metric name
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        by_name = await db.metrics.aggregate(pipeline).to_list(10)
        
        # Recent ingestion rate (last hour)
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent_count = await db.metrics.count_documents({
            **query,
            "created_at": {"$gte": hour_ago}
        })
        
        return {
            "total_data_points": total_metrics,
            "ingestion_rate_per_hour": recent_count,
            "by_service": [{"service": r["_id"], "count": r["count"]} for r in by_service],
            "by_metric_name": [{"name": r["_id"], "count": r["count"]} for r in by_name],
            "unique_metrics": len(await self.get_metric_names(tenant_id=tenant_id))
        }
    
    async def delete_old_metrics(
        self,
        days: int = 30,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Delete metrics older than specified days"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"timestamp": {"$lt": cutoff}}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        result = await db.metrics.delete_many(query)
        
        return {
            "deleted_count": result.deleted_count,
            "cutoff_date": cutoff
        }


# Singleton instance
metrics_service = MetricsService()
