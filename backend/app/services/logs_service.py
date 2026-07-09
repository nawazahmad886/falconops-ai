"""
FalconOps AI - Logs Service
Log ingestion, storage, and searching for observability
"""
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from ..core.database import db

# Log levels
LOG_LEVELS = [
    {"id": "trace", "name": "Trace", "severity": 0, "color": "gray"},
    {"id": "debug", "name": "Debug", "severity": 1, "color": "blue"},
    {"id": "info", "name": "Info", "severity": 2, "color": "green"},
    {"id": "warn", "name": "Warning", "severity": 3, "color": "yellow"},
    {"id": "error", "name": "Error", "severity": 4, "color": "orange"},
    {"id": "fatal", "name": "Fatal", "severity": 5, "color": "red"},
]

# Log sources
LOG_SOURCES = [
    "application",
    "system",
    "access",
    "error",
    "security",
    "audit",
    "container",
    "network"
]


class LogsService:
    """Service for managing log ingestion and searching"""
    
    async def ingest_log(
        self,
        message: str,
        level: str = "info",
        source: str = "application",
        service: Optional[str] = None,
        host: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest a single log entry"""
        log_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        
        # Extract structured fields from message
        extracted = self._extract_fields(message)
        
        log_doc = {
            "id": log_id,
            "message": message,
            "level": level.lower(),
            "source": source,
            "service": service,
            "host": host,
            "trace_id": trace_id,
            "span_id": span_id,
            "timestamp": ts,
            "metadata": metadata or {},
            "extracted_fields": extracted,
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.logs.insert_one(log_doc)
        return {k: v for k, v in log_doc.items() if k != "_id"}
    
    async def ingest_batch(
        self,
        logs: List[Dict],
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Ingest multiple log entries at once"""
        docs = []
        now = datetime.now(timezone.utc).isoformat()
        
        for log in logs:
            message = log.get("message", "")
            extracted = self._extract_fields(message)
            
            doc = {
                "id": str(uuid.uuid4()),
                "message": message,
                "level": log.get("level", "info").lower(),
                "source": log.get("source", "application"),
                "service": log.get("service"),
                "host": log.get("host"),
                "trace_id": log.get("trace_id"),
                "span_id": log.get("span_id"),
                "timestamp": log.get("timestamp", now),
                "metadata": log.get("metadata", {}),
                "extracted_fields": extracted,
                "tenant_id": tenant_id,
                "created_at": now
            }
            docs.append(doc)
        
        if docs:
            await db.logs.insert_many(docs)
        
        return {
            "ingested": len(docs),
            "timestamp": now
        }
    
    def _extract_fields(self, message: str) -> Dict:
        """Extract structured fields from log message"""
        extracted = {}
        
        # Extract IP addresses
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ips = re.findall(ip_pattern, message)
        if ips:
            extracted["ip_addresses"] = ips
        
        # Extract HTTP status codes
        status_pattern = r'(?:status|code)[=:\s]*(\d{3})'
        status_codes = re.findall(status_pattern, message, re.IGNORECASE)
        if status_codes:
            extracted["http_status"] = status_codes
        
        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message)
        if urls:
            extracted["urls"] = urls
        
        # Extract error types
        error_pattern = r'(?:Error|Exception|Failure|Failed):\s*([^\n]+)'
        errors = re.findall(error_pattern, message, re.IGNORECASE)
        if errors:
            extracted["error_messages"] = errors
        
        # Extract durations (e.g., "123ms", "2.5s")
        duration_pattern = r'(\d+(?:\.\d+)?)\s*(?:ms|s|seconds?|milliseconds?)'
        durations = re.findall(duration_pattern, message, re.IGNORECASE)
        if durations:
            extracted["durations"] = durations
        
        return extracted
    
    async def search_logs(
        self,
        query: Optional[str] = None,
        level: Optional[str] = None,
        levels: Optional[List[str]] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        host: Optional[str] = None,
        trace_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_order: str = "desc"
    ) -> Dict:
        """Search logs with various filters"""
        mongo_query = {}
        
        if tenant_id:
            mongo_query["tenant_id"] = tenant_id
        
        # Text search in message
        if query:
            mongo_query["message"] = {"$regex": query, "$options": "i"}
        
        # Level filter
        if level:
            mongo_query["level"] = level.lower()
        elif levels:
            mongo_query["level"] = {"$in": [l.lower() for l in levels]}
        
        if source:
            mongo_query["source"] = source
        if service:
            mongo_query["service"] = service
        if host:
            mongo_query["host"] = host
        if trace_id:
            mongo_query["trace_id"] = trace_id
        
        # Time range
        if start_time or end_time:
            mongo_query["timestamp"] = {}
            if start_time:
                mongo_query["timestamp"]["$gte"] = start_time
            if end_time:
                mongo_query["timestamp"]["$lte"] = end_time
        
        # Execute query
        sort_dir = -1 if sort_order == "desc" else 1
        total = await db.logs.count_documents(mongo_query)
        
        logs = await db.logs.find(
            mongo_query, {"_id": 0}
        ).sort("timestamp", sort_dir).skip(offset).limit(limit).to_list(limit)
        
        return {
            "logs": logs,
            "total": total,
            "offset": offset,
            "limit": limit,
            "query": query,
            "filters": {
                "level": level,
                "source": source,
                "service": service,
                "host": host
            }
        }
    
    async def get_log_by_id(self, log_id: str) -> Optional[Dict]:
        """Get a single log entry by ID"""
        log = await db.logs.find_one({"id": log_id}, {"_id": 0})
        return log
    
    async def get_logs_by_trace(
        self,
        trace_id: str,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all logs for a specific trace"""
        query = {"trace_id": trace_id}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        logs = await db.logs.find(
            query, {"_id": 0}
        ).sort("timestamp", 1).to_list(1000)
        
        return logs
    
    async def get_log_stats(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Get log statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        if not end_time:
            end_time = datetime.now(timezone.utc).isoformat()
        
        query["timestamp"] = {"$gte": start_time, "$lte": end_time}
        
        total_logs = await db.logs.count_documents(query)
        
        # Count by level
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$level", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_level = await db.logs.aggregate(pipeline).to_list(20)
        
        # Count by service
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$service", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        by_service = await db.logs.aggregate(pipeline).to_list(10)
        
        # Count by source
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_source = await db.logs.aggregate(pipeline).to_list(20)
        
        # Error rate
        error_query = {**query, "level": {"$in": ["error", "fatal"]}}
        error_count = await db.logs.count_documents(error_query)
        
        return {
            "total_logs": total_logs,
            "time_range": {"start": start_time, "end": end_time},
            "by_level": [{"level": r["_id"], "count": r["count"]} for r in by_level],
            "by_service": [{"service": r["_id"], "count": r["count"]} for r in by_service],
            "by_source": [{"source": r["_id"], "count": r["count"]} for r in by_source],
            "error_count": error_count,
            "error_rate": (error_count / total_logs * 100) if total_logs > 0 else 0
        }
    
    async def get_error_logs(
        self,
        service: Optional[str] = None,
        start_time: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get recent error logs"""
        query = {"level": {"$in": ["error", "fatal"]}}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        if service:
            query["service"] = service
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        
        logs = await db.logs.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return logs
    
    async def get_log_volume_over_time(
        self,
        interval: str = "1h",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get log volume aggregated over time intervals"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        if not start_time:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        if not end_time:
            end_time = datetime.now(timezone.utc).isoformat()
        
        query["timestamp"] = {"$gte": start_time, "$lte": end_time}
        
        # Simple bucketing by hour
        pipeline = [
            {"$match": query},
            {"$addFields": {
                "hour": {"$substr": ["$timestamp", 0, 13]}  # Extract YYYY-MM-DDTHH
            }},
            {"$group": {
                "_id": "$hour",
                "count": {"$sum": 1},
                "error_count": {
                    "$sum": {"$cond": [{"$in": ["$level", ["error", "fatal"]]}, 1, 0]}
                }
            }},
            {"$sort": {"_id": 1}}
        ]
        
        results = await db.logs.aggregate(pipeline).to_list(100)
        
        return [{
            "timestamp": f"{r['_id']}:00:00.000Z",
            "count": r["count"],
            "error_count": r["error_count"]
        } for r in results]
    
    async def delete_old_logs(
        self,
        days: int = 30,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Delete logs older than specified days"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"timestamp": {"$lt": cutoff}}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        result = await db.logs.delete_many(query)
        
        return {
            "deleted_count": result.deleted_count,
            "cutoff_date": cutoff
        }


# Singleton instance
logs_service = LogsService()
