"""
FalconOps AI - Enterprise Metrics Observability Platform
Time-Series Metrics Service with Redis Streams Pipeline
"""
import uuid
import asyncio
import json
import logging
import numpy as np
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple, Union
from scipy import stats
import os
import redis.asyncio as redis
from ..core.database import db

logger = logging.getLogger(__name__)

# Redis connection (optional - falls back to MongoDB if unavailable)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
METRICS_STREAM = "falcon:metrics:stream"
METRICS_CONSUMER_GROUP = "falcon:metrics:processors"

# VictoriaMetrics (real TSDB — optional dual-write target + preferred read path for
# query_metrics(); MongoDB remains the system of record and the fallback if VM is
# unreachable or hasn't been deployed).
VM_URL = os.environ.get("VICTORIA_METRICS_URL", "http://localhost:8428")
_VM_AGG_TO_FUNC = {
    "avg": "avg_over_time",
    "sum": "sum_over_time",
    "min": "min_over_time",
    "max": "max_over_time",
    "count": "count_over_time",
    "stddev": "stddev_over_time",
    # MetricsQL rate() is a true per-second rate, unlike the naive (last-first)/count
    # the MongoDB fallback path below uses for "rate" — a real improvement, not a
    # behavior-preserving port.
    "rate": "rate",
}
_VM_QUANTILES = {"p50": 0.5, "p90": 0.9, "p95": 0.95, "p99": 0.99}

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


_indexes_ready = False

# Raw high-cardinality metric points have little standalone value after this long —
# aggregated views (dashboards, capacity predictions) are computed on read from
# whatever's still in the window, so this doesn't remove any rollup/summary data,
# only the raw points backing it. Configurable since real retention needs vary by
# deployment; unlike alerts/incidents (kept indefinitely — see indexes below), this
# is genuinely safe to auto-expire.
METRICS_RETENTION_DAYS = int(os.environ.get("METRICS_RETENTION_DAYS", "90"))


def _metrics_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=METRICS_RETENTION_DAYS)


async def _ensure_indexes() -> None:
    """db.metrics_timeseries had zero indexes anywhere in the running app (only in a
    generated on-prem install script nothing ever executes) — every query_metrics/
    predict_capacity/get_anomalies call was a full collection scan. Same lazy
    ensure-once-on-first-real-call pattern as ai_monitoring_service/
    resource_explorer_service."""
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        # Covers predict_capacity/predict_all_hosts's {name, tags.host, timestamp range}
        # and query_metrics/get_top_metrics's {name, timestamp range} (a prefix of this
        # same index) in one index.
        await db.metrics_timeseries.create_index(
            [("name", 1), ("tags.host", 1), ("timestamp", 1)],
            name="metrics_name_host_ts")
        await db.metrics_timeseries.create_index(
            [("tenant_id", 1), ("name", 1), ("timestamp", 1)],
            name="metrics_tenant_name_ts")
        await db.metrics_timeseries.create_index(
            [("anomaly.is_anomaly", 1), ("timestamp", -1)],
            name="metrics_anomaly_ts")
        # TTL index — requires a real BSON Date field, which "timestamp" is not (it's
        # stored as an ISO string throughout this file, matched by existing query code
        # that compares it lexically). expires_at is a separate Date-typed field set at
        # insert time purely for this, same pattern ai_monitoring_service uses.
        await db.metrics_timeseries.create_index(
            "expires_at", name="metrics_ttl", expireAfterSeconds=0)
        _indexes_ready = True
    except Exception as e:
        logger.warning("metrics_timeseries index creation skipped: %s", e)


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
            except Exception as e:
                self.redis_pool = None
                # Previously swallowed silently — main.py logged "Metrics stream
                # processor started" regardless, so a Redis outage produced zero
                # signal anywhere that ingestion had actually stopped. See
                # self_monitor.py's background_jobs task-liveness check, which
                # now surfaces process_stream() exiting early because of this.
                logger.warning(
                    "MetricsTimeSeriesService: Redis unreachable at %s (%s) — "
                    "metrics ingestion falls back to direct MongoDB writes; the "
                    "stream-based process_stream() background task will not run.",
                    REDIS_URL, e,
                )
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
            logger.warning("Redis stream initialization failed (non-fatal, falls back to direct MongoDB writes): %s", e)
    
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
        await _ensure_indexes()
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
        await _ensure_indexes()
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
                    "processed_at": now,
                    "expires_at": _metrics_expires_at(),
                })
            if docs:
                await db.metrics_timeseries.insert_many(docs)
                await self._vm_write_batch(docs)
                queued = len(docs)

        return {"queued": queued, "timestamp": now}

    async def _store_metric(self, metric_data: Dict):
        """Store metric directly in MongoDB (system of record) and best-effort
        dual-write to VictoriaMetrics (real TSDB backing query_metrics())."""
        metric_data["processed_at"] = datetime.now(timezone.utc).isoformat()
        metric_data["expires_at"] = _metrics_expires_at()
        await db.metrics_timeseries.insert_one(metric_data)
        await self._vm_write_batch([metric_data])

    async def _vm_write_batch(self, docs: List[Dict]):
        """Best-effort dual-write of metric points to VictoriaMetrics's JSON line
        import endpoint. Never raises — a VictoriaMetrics outage (or it simply not
        being deployed) must never break ingestion; MongoDB above is already the
        durable write regardless of whether this succeeds."""
        if not docs:
            return
        try:
            lines = []
            for metric_data in docs:
                value = metric_data.get("value")
                name = metric_data.get("name")
                if value is None or not name:
                    continue
                ts_raw = metric_data.get("timestamp")
                try:
                    dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")) if ts_raw else datetime.now(timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                labels = {"__name__": name}
                for k, v in (metric_data.get("tags") or {}).items():
                    labels[str(k)] = str(v)
                lines.append(json.dumps({
                    "metric": labels,
                    "values": [float(value)],
                    "timestamps": [int(dt.timestamp() * 1000)],
                }))
            if not lines:
                return
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{VM_URL}/api/v1/import", content="\n".join(lines))
        except Exception as e:
            print(f"VictoriaMetrics write error (non-fatal, MongoDB remains source of truth): {e}")

    # ==================== STREAM PROCESSING ====================
    
    async def process_stream(self, batch_size: int = 100, block_ms: int = 1000):
        """Process metrics from Redis stream (worker function). Returns almost
        immediately (a "successfully" completed asyncio.Task, not a crash) when
        Redis is unreachable — self_monitor.py's background-jobs check treats an
        early-completed task for this scheduler as a real failure signal, since
        this coroutine is only ever meant to return once cancelled at shutdown."""
        r = await self.get_redis()
        if r is None:
            logger.warning(
                "MetricsTimeSeriesService.process_stream: exiting immediately, "
                "no Redis connection — metrics ingested via ingest_metric/ingest_batch "
                "still land in MongoDB directly, but stream-based anomaly detection "
                "on ingested points will not run."
            )
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
                            metric_data["expires_at"] = _metrics_expires_at()

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
                    await self._vm_write_batch(docs)

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
        """Query metrics with aggregation and time bucketing.

        Tries VictoriaMetrics first (native time-bucketed aggregation instead of
        scanning raw Mongo docs into Python) and falls back to the original MongoDB
        scan+bucket path unchanged on any failure, empty result, or when tenant_id is
        set (VictoriaMetrics has no per-tenant label convention yet, so tenant-scoped
        queries always use the MongoDB path, which already supports it).
        """
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        if not end_time:
            end_time = datetime.now(timezone.utc).isoformat()

        bucket_seconds = TIME_BUCKETS.get(bucket, 300)

        if not tenant_id:
            vm_series = await self._vm_query_range(metric_name, tags, aggregation, bucket_seconds, start_time, end_time)
            if vm_series:
                return {
                    "metric_name": metric_name,
                    "aggregation": aggregation,
                    "bucket": bucket,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_points": sum(p["count"] for p in vm_series),
                    "series": vm_series,
                    "source": "victoria_metrics",
                }

        # ── Fallback: original MongoDB scan+bucket path ──
        query = {"name": metric_name}
        if tenant_id:
            query["tenant_id"] = tenant_id
        if tags:
            for key, value in tags.items():
                query[f"tags.{key}"] = value
        query["timestamp"] = {"$gte": start_time, "$lte": end_time}

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

        bucketed_data = self._bucket_metrics(raw_metrics, bucket_seconds, aggregation)

        return {
            "metric_name": metric_name,
            "aggregation": aggregation,
            "bucket": bucket,
            "start_time": start_time,
            "end_time": end_time,
            "data_points": len(raw_metrics),
            "series": bucketed_data,
            "source": "mongodb",
        }

    def _vm_selector(self, metric_name: str, tags: Optional[Dict[str, str]]) -> str:
        """Build a MetricsQL series selector, e.g. metric_name{host="web-1"}."""
        if not tags:
            return metric_name
        filters = []
        for k, v in tags.items():
            val = str(v).replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'{k}="{val}"')
        return f'{metric_name}{{{",".join(filters)}}}'

    async def _vm_raw_query_range(
        self, selector: str, aggregation: str, bucket_seconds: int, start_time: str, end_time: str
    ) -> Optional[Dict[str, float]]:
        """Run one MetricsQL query_range call. Returns {iso_timestamp: value}, or None
        on any failure, non-200 response, or when more than one series matches (the
        caller can't meaningfully merge multiple series for a single-metric query, so
        it bails out to the MongoDB fallback rather than guess)."""
        if aggregation in _VM_QUANTILES:
            query = f'quantile_over_time({_VM_QUANTILES[aggregation]}, {selector}[{bucket_seconds}s])'
        else:
            func = _VM_AGG_TO_FUNC.get(aggregation, "avg_over_time")
            query = f'{func}({selector}[{bucket_seconds}s])'

        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{VM_URL}/api/v1/query_range", params={
                    "query": query,
                    "start": int(start_dt.timestamp()),
                    "end": int(end_dt.timestamp()),
                    "step": f"{bucket_seconds}s",
                })
            if resp.status_code != 200:
                return None
            result = resp.json().get("data", {}).get("result", [])
            if len(result) != 1:
                return None
            out = {}
            for ts, val in result[0].get("values", []):
                try:
                    out[datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()] = float(val)
                except (TypeError, ValueError):
                    continue
            return out or None
        except Exception as e:
            print(f"VictoriaMetrics query error (falling back to MongoDB): {e}")
            return None

    async def _vm_query_range(
        self, metric_name: str, tags: Optional[Dict[str, str]], aggregation: str,
        bucket_seconds: int, start_time: str, end_time: str
    ) -> Optional[List[Dict]]:
        """Query VictoriaMetrics for a bucketed series, including real per-bucket
        sample counts (via a second count_over_time query) so the response shape
        matches the MongoDB path's series exactly. Returns None if VictoriaMetrics is
        unreachable or has no matching data, so the caller falls back cleanly."""
        selector = self._vm_selector(metric_name, tags)
        values = await self._vm_raw_query_range(selector, aggregation, bucket_seconds, start_time, end_time)
        if values is None:
            return None
        if aggregation == "count":
            counts = values
        else:
            counts = await self._vm_raw_query_range(selector, "count", bucket_seconds, start_time, end_time) or {}

        series = [
            {"timestamp": ts, "value": round(value, 4), "count": int(counts.get(ts, 1))}
            for ts, value in values.items()
        ]
        series.sort(key=lambda p: p["timestamp"])
        return series or None

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
        group_by: Union[str, List[str]] = "host",
        aggregation: str = "avg",
        limit: int = 10,
        start_time: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get top N metrics grouped by a tag dimension, or a compound key when
        group_by is a list (e.g. ["host", "gpu_index"] to identify one physical
        GPU across multiple hosts — a single tag can't disambiguate that alone).
        Backward compatible: a plain string keeps the original flat {group_by: value, ...} shape."""
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        query = {
            "name": metric_name,
            "timestamp": {"$gte": start_time}
        }
        if tenant_id:
            query["tenant_id"] = tenant_id

        group_fields = [group_by] if isinstance(group_by, str) else list(group_by)
        id_expr = (
            f"$tags.{group_fields[0]}" if len(group_fields) == 1
            else {g: f"$tags.{g}" for g in group_fields}
        )

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": id_expr,
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

        out = []
        for r in results:
            row: Dict[str, Any] = {}
            if len(group_fields) == 1:
                row[group_fields[0]] = r["_id"] or "unknown"
            else:
                row.update({g: (r["_id"] or {}).get(g) for g in group_fields})
            row.update({
                "avg": round(r["avg_value"], 2),
                "max": round(r["max_value"], 2),
                "min": round(r["min_value"], 2),
                "count": r["count"],
                "last_value": round(r["last_value"], 2),
                "last_timestamp": r["last_timestamp"],
            })
            out.append(row)
        return out
    
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
