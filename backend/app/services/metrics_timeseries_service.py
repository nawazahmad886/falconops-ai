"""
FalconOps AI - Enterprise Metrics Observability Platform
Time-Series Metrics Service with Redis Streams Pipeline
"""
import uuid
import asyncio
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from scipy import stats
import os
import redis.asyncio as redis
from ..core.database import db

# Redis connection (optional - falls back to MongoDB if unavailable)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
METRICS_STREAM = "falcon:metrics:stream"
METRICS_CONSUMER_GROUP = "falcon:metrics:processors"

# Metric categories
METRIC_CATEGORIES = {
    "infrastructure": ["cpu_usage", "memory_usage", "disk_usage", "disk_io_read", "disk_io_write", 
                       "network_in", "network_out", "load_average", "process_count", "uptime"],
    "application": ["response_time", "request_rate", "error_rate", "throughput", "latency_p50", 
                    "latency_p95", "latency_p99", "active_connections", "queue_depth", "cache_hit_rate"],
    "database": ["query_time", "connection_count", "transactions_per_sec", "deadlocks", 
                 "buffer_hit_ratio", "replication_lag", "table_size", "index_size"],
    "kubernetes": ["pod_cpu", "pod_memory", "container_restarts", "deployment_replicas", 
                   "node_allocatable_cpu", "node_allocatable_memory", "pvc_usage"],
    "custom": []
}

# Aggregation types
AGGREGATIONS = ["avg", "sum", "min", "max", "count", "p50", "p90", "p95", "p99", "stddev", "rate"]

# Time bucketing
TIME_BUCKETS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400
}


class MetricsTimeSeriesService:
    """Enterprise-grade time-series metrics service"""
    
    def __init__(self):
        self.redis_pool = None
        self._baseline_cache = {}  # Cache for baseline calculations
    
    async def get_redis(self) -> Optional[redis.Redis]:
        """Get Redis connection (returns None if unavailable)"""
        if self.redis_pool is None:
            try:
                self.redis_pool = redis.from_url(REDIS_URL, decode_responses=True)
                await self.redis_pool.ping()
            except Exception:
                self.redis_pool = None
                return None
        return self.redis_pool
    
    async def initialize_stream(self):
        """Initialize Redis stream and consumer group"""
        try:
            r = await self.get_redis()
            if r is None:
                return
            # Create consumer group if not exists
            try:
                await r.xgroup_create(METRICS_STREAM, METRICS_CONSUMER_GROUP, id="0", mkstream=True)
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        except Exception as e:
            print(f"Redis stream initialization (non-fatal): {e}")
    
    # ==================== INGESTION ====================
    
    async def ingest_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        unit: str = "",
        metric_type: str = "gauge",
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest a single metric into the stream"""
        metric_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        
        metric_data = {
            "id": metric_id,
            "name": metric_name,
            "value": value,
            "timestamp": ts,
            "tags": tags or {},
            "unit": unit,
            "type": metric_type,  # gauge, counter, histogram
            "tenant_id": tenant_id
        }
        
        # Push to Redis stream for async processing
        try:
            r = await self.get_redis()
            if r:
                await r.xadd(METRICS_STREAM, {"data": json.dumps(metric_data)})
            else:
                await self._store_metric(metric_data)
        except Exception as e:
            print(f"Redis stream error: {e}")
            # Fallback: direct insert
            await self._store_metric(metric_data)
        
        return {"id": metric_id, "status": "queued", "timestamp": ts}
    
    async def ingest_batch(
        self,
        metrics: List[Dict],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest multiple metrics at once"""
        now = datetime.now(timezone.utc).isoformat()
        queued = 0
        
        try:
            r = await self.get_redis()
            if r:
                pipe = r.pipeline()
                
                for metric in metrics:
                    metric_data = {
                        "id": str(uuid.uuid4()),
                        "name": metric.get("name"),
                        "value": metric.get("value"),
                        "timestamp": metric.get("timestamp", now),
                        "tags": metric.get("tags", {}),
                        "unit": metric.get("unit", ""),
                        "type": metric.get("type", "gauge"),
                        "tenant_id": tenant_id
                    }
                    pipe.xadd(METRICS_STREAM, {"data": json.dumps(metric_data)})
                    queued += 1
                
                await pipe.execute()
            else:
                raise Exception("Redis unavailable")
        except Exception as e:
            print(f"Batch ingestion error: {e}")
            # Fallback: direct batch insert
            docs = []
            for metric in metrics:
                docs.append({
                    "id": str(uuid.uuid4()),
                    "name": metric.get("name"),
                    "value": metric.get("value"),
                    "timestamp": metric.get("timestamp", now),
                    "tags": metric.get("tags", {}),
                    "unit": metric.get("unit", ""),
                    "type": metric.get("type", "gauge"),
                    "tenant_id": tenant_id,
                    "processed_at": now
                })
            if docs:
                await db.metrics_timeseries.insert_many(docs)
                queued = len(docs)
        
        return {"queued": queued, "timestamp": now}
    
    async def _store_metric(self, metric_data: Dict):
        """Store metric directly in MongoDB"""
        metric_data["processed_at"] = datetime.now(timezone.utc).isoformat()
        await db.metrics_timeseries.insert_one(metric_data)
    
    # ==================== STREAM PROCESSING ====================
    
    async def process_stream(self, batch_size: int = 100, block_ms: int = 1000):
        """Process metrics from Redis stream (worker function)"""
        r = await self.get_redis()
        if r is None:
            return
        consumer_name = f"processor-{uuid.uuid4().hex[:8]}"
        
        while True:
            try:
                # Read from stream
                messages = await r.xreadgroup(
                    METRICS_CONSUMER_GROUP,
                    consumer_name,
                    {METRICS_STREAM: ">"},
                    count=batch_size,
                    block=block_ms
                )
                
                if not messages:
                    continue
                
                docs = []
                msg_ids = []
                
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        try:
                            metric_data = json.loads(data.get("data", "{}"))
                            metric_data["processed_at"] = datetime.now(timezone.utc).isoformat()
                            
                            # Run anomaly detection
                            anomaly_result = await self.detect_anomaly(
                                metric_data["name"],
                                metric_data["value"],
                                metric_data.get("tags", {}),
                                metric_data.get("tenant_id")
                            )
                            metric_data["anomaly"] = anomaly_result
                            
                            docs.append(metric_data)
                            msg_ids.append(msg_id)
                        except Exception as e:
                            print(f"Message processing error: {e}")
                
                # Batch insert to MongoDB
                if docs:
                    await db.metrics_timeseries.insert_many(docs)
                
                # Acknowledge messages
                if msg_ids:
                    await r.xack(METRICS_STREAM, METRICS_CONSUMER_GROUP, *msg_ids)
                
            except Exception as e:
                print(f"Stream processing error: {e}")
                await asyncio.sleep(1)
    
    # ==================== QUERY ENGINE ====================
    
    async def query_metrics(
        self,
        metric_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        aggregation: str = "avg",
        bucket: str = "5m",
        tenant_id: Optional[str] = None,
        limit: int = 10000
    ) -> Dict:
        """Query metrics with aggregation and time bucketing"""
        # Build query
        query = {"name": metric_name}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        
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
        raw_metrics = await db.metrics_timeseries.find(
            query, {"_id": 0, "value": 1, "timestamp": 1, "tags": 1, "anomaly": 1}
        ).sort("timestamp", 1).limit(limit).to_list(limit)
        
        if not raw_metrics:
            return {
                "metric_name": metric_name,
                "aggregation": aggregation,
                "bucket": bucket,
                "data_points": 0,
                "series": []
            }
        
        # Time bucket aggregation
        bucket_seconds = TIME_BUCKETS.get(bucket, 300)
        bucketed_data = self._bucket_metrics(raw_metrics, bucket_seconds, aggregation)
        
        return {
            "metric_name": metric_name,
            "aggregation": aggregation,
            "bucket": bucket,
            "start_time": start_time,
            "end_time": end_time,
            "data_points": len(raw_metrics),
            "series": bucketed_data
        }
    
    def _bucket_metrics(self, metrics: List[Dict], bucket_seconds: int, aggregation: str) -> List[Dict]:
        """Bucket metrics by time interval and aggregate"""
        if not metrics:
            return []
        
        buckets = {}
        
        for m in metrics:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            bucket_ts = ts.replace(second=0, microsecond=0)
            bucket_ts = bucket_ts - timedelta(seconds=bucket_ts.timestamp() % bucket_seconds)
            bucket_key = bucket_ts.isoformat()
            
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(m["value"])
        
        result = []
        for timestamp, values in sorted(buckets.items()):
            agg_value = self._aggregate_values(values, aggregation)
            result.append({
                "timestamp": timestamp,
                "value": round(agg_value, 4),
                "count": len(values)
            })
        
        return result
    
    def _aggregate_values(self, values: List[float], aggregation: str) -> float:
        """Perform aggregation on values"""
        if not values:
            return 0.0
        
        arr = np.array(values)
        
        if aggregation == "avg":
            return float(np.mean(arr))
        elif aggregation == "sum":
            return float(np.sum(arr))
        elif aggregation == "min":
            return float(np.min(arr))
        elif aggregation == "max":
            return float(np.max(arr))
        elif aggregation == "count":
            return float(len(arr))
        elif aggregation == "p50":
            return float(np.percentile(arr, 50))
        elif aggregation == "p90":
            return float(np.percentile(arr, 90))
        elif aggregation == "p95":
            return float(np.percentile(arr, 95))
        elif aggregation == "p99":
            return float(np.percentile(arr, 99))
        elif aggregation == "stddev":
            return float(np.std(arr))
        elif aggregation == "rate":
            if len(arr) < 2:
                return 0.0
            return float((arr[-1] - arr[0]) / len(arr))
        
        return float(np.mean(arr))
    
    # ==================== CATALOG & DISCOVERY ====================
    
    async def get_metrics_catalog(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Get catalog of available metrics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        # Get unique metric names
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$name",
                "count": {"$sum": 1},
                "last_seen": {"$max": "$timestamp"},
                "unit": {"$first": "$unit"},
                "type": {"$first": "$type"},
                "tags_sample": {"$first": "$tags"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 500}
        ]
        
        metrics_list = await db.metrics_timeseries.aggregate(pipeline).to_list(500)
        
        # Categorize metrics
        categorized = {cat: [] for cat in METRIC_CATEGORIES.keys()}
        
        for m in metrics_list:
            metric_name = m["_id"]
            
            # Filter by search
            if search and search.lower() not in metric_name.lower():
                continue
            
            # Find category
            metric_category = "custom"
            for cat, cat_metrics in METRIC_CATEGORIES.items():
                if metric_name in cat_metrics or any(metric_name.startswith(cm) for cm in cat_metrics):
                    metric_category = cat
                    break
            
            # Filter by category
            if category and metric_category != category:
                continue
            
            categorized[metric_category].append({
                "name": metric_name,
                "count": m["count"],
                "last_seen": m["last_seen"],
                "unit": m.get("unit", ""),
                "type": m.get("type", "gauge"),
                "tags_sample": m.get("tags_sample", {})
            })
        
        return {
            "categories": METRIC_CATEGORIES,
            "metrics": categorized,
            "total_metrics": sum(len(v) for v in categorized.values())
        }
    
    async def get_top_metrics(
        self,
        metric_name: str,
        group_by: str = "host",
        aggregation: str = "avg",
        limit: int = 10,
        start_time: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get top N metrics grouped by a tag dimension"""
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        query = {
            "name": metric_name,
            "timestamp": {"$gte": start_time}
        }
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        group_field = f"$tags.{group_by}"
        
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": group_field,
                "avg_value": {"$avg": "$value"},
                "max_value": {"$max": "$value"},
                "min_value": {"$min": "$value"},
                "count": {"$sum": 1},
                "last_value": {"$last": "$value"},
                "last_timestamp": {"$last": "$timestamp"}
            }},
            {"$sort": {"avg_value" if aggregation == "avg" else "max_value": -1}},
            {"$limit": limit}
        ]
        
        results = await db.metrics_timeseries.aggregate(pipeline).to_list(limit)
        
        return [{
            group_by: r["_id"] or "unknown",
            "avg": round(r["avg_value"], 2),
            "max": round(r["max_value"], 2),
            "min": round(r["min_value"], 2),
            "count": r["count"],
            "last_value": round(r["last_value"], 2),
            "last_timestamp": r["last_timestamp"]
        } for r in results]
    
    # ==================== ANOMALY DETECTION ====================
    
    async def detect_anomaly(
        self,
        metric_name: str,
        value: float,
        tags: Dict[str, str],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Detect anomaly using statistical models"""
        cache_key = f"{metric_name}:{tags.get('host', 'all')}:{tenant_id or 'default'}"
        
        # Get or calculate baseline
        baseline = self._baseline_cache.get(cache_key)
        
        if baseline is None or baseline.get("expires_at", 0) < datetime.now(timezone.utc).timestamp():
            baseline = await self._calculate_baseline(metric_name, tags, tenant_id)
            baseline["expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()
            self._baseline_cache[cache_key] = baseline
        
        if baseline.get("mean") is None:
            return {"is_anomaly": False, "score": 0, "method": "insufficient_data"}
        
        # Calculate Z-score
        z_score = 0
        if baseline["stddev"] > 0:
            z_score = (value - baseline["mean"]) / baseline["stddev"]
        
        # Anomaly thresholds
        is_anomaly = abs(z_score) > 3  # 3 sigma rule
        severity = "normal"
        
        if abs(z_score) > 5:
            severity = "critical"
        elif abs(z_score) > 4:
            severity = "high"
        elif abs(z_score) > 3:
            severity = "medium"
        elif abs(z_score) > 2:
            severity = "low"
        
        # Check percentile bounds
        percentile_anomaly = value > baseline.get("p99", float("inf")) or value < baseline.get("p1", float("-inf"))
        
        return {
            "is_anomaly": is_anomaly or percentile_anomaly,
            "z_score": round(z_score, 2),
            "severity": severity,
            "baseline_mean": round(baseline["mean"], 2),
            "baseline_stddev": round(baseline["stddev"], 2),
            "method": "zscore_percentile"
        }
    
    async def _calculate_baseline(
        self,
        metric_name: str,
        tags: Dict[str, str],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Calculate baseline statistics for a metric"""
        # Get last 24 hours of data
        start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        
        query = {
            "name": metric_name,
            "timestamp": {"$gte": start_time}
        }
        if tenant_id:
            query["tenant_id"] = tenant_id
        if tags.get("host"):
            query["tags.host"] = tags["host"]
        
        values = await db.metrics_timeseries.find(
            query, {"value": 1, "_id": 0}
        ).limit(10000).to_list(10000)
        
        if len(values) < 10:
            return {"mean": None, "stddev": None}
        
        arr = np.array([v["value"] for v in values])
        
        return {
            "mean": float(np.mean(arr)),
            "stddev": float(np.std(arr)),
            "p1": float(np.percentile(arr, 1)),
            "p5": float(np.percentile(arr, 5)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "sample_size": len(arr)
        }
    
    async def get_anomalies(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        metric_name: Optional[str] = None,
        severity: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get detected anomalies"""
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        
        query = {
            "anomaly.is_anomaly": True,
            "timestamp": {"$gte": start_time}
        }
        
        if end_time:
            query["timestamp"]["$lte"] = end_time
        if tenant_id:
            query["tenant_id"] = tenant_id
        if metric_name:
            query["name"] = metric_name
        if severity:
            query["anomaly.severity"] = severity
        
        anomalies = await db.metrics_timeseries.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return anomalies
    
    # ==================== STATISTICS ====================
    
    async def get_stats(self, tenant_id: Optional[str] = None) -> Dict:
        """Get metrics service statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        # Total metrics
        total_metrics = await db.metrics_timeseries.count_documents(query)
        
        # Metrics in last hour
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent_metrics = await db.metrics_timeseries.count_documents({
            **query,
            "timestamp": {"$gte": hour_ago}
        })
        
        # Anomalies in last hour
        anomalies_count = await db.metrics_timeseries.count_documents({
            **query,
            "timestamp": {"$gte": hour_ago},
            "anomaly.is_anomaly": True
        })
        
        # Unique metric names
        unique_metrics = len(await db.metrics_timeseries.distinct("name", query))
        
        # Redis stream info
        stream_info = {"length": 0, "groups": 0}
        try:
            r = await self.get_redis()
            info = await r.xinfo_stream(METRICS_STREAM)
            stream_info["length"] = info.get("length", 0)
            stream_info["groups"] = len(await r.xinfo_groups(METRICS_STREAM))
        except Exception:
            pass
        
        return {
            "total_data_points": total_metrics,
            "metrics_per_hour": recent_metrics,
            "anomalies_per_hour": anomalies_count,
            "unique_metrics": unique_metrics,
            "ingestion_rate": recent_metrics / 3600 if recent_metrics > 0 else 0,
            "anomaly_rate": (anomalies_count / recent_metrics * 100) if recent_metrics > 0 else 0,
            "stream": stream_info
        }


# Singleton instance
metrics_timeseries_service = MetricsTimeSeriesService()
