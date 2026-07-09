"""
FalconOps AI - Log Ingestion & Analysis Service
AI-powered log monitoring, parsing, anomaly detection, and RCA
"""
import os
import re
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
import statistics

from dotenv import load_dotenv
load_dotenv()

from ..core.database import db

logger = logging.getLogger(__name__)


# ======================== LOG PATTERNS ========================

LOG_PATTERNS = [
    # Standard log format: LEVEL SERVICE MESSAGE
    {"name": "standard", "pattern": r"^(ERROR|WARN|INFO|DEBUG|CRITICAL|FATAL)\s+(\S+)\s+(.*)$"},
    # Timestamp format: [TIMESTAMP] LEVEL SERVICE MESSAGE
    {"name": "timestamped", "pattern": r"^\[([^\]]+)\]\s+(ERROR|WARN|INFO|DEBUG|CRITICAL|FATAL)\s+(\S+)\s+(.*)$"},
    # JSON-like format
    {"name": "json_like", "pattern": r'\{"level":\s*"([^"]+)".*"service":\s*"([^"]+)".*"message":\s*"([^"]+)"'},
    # Apache/Nginx style
    {"name": "apache", "pattern": r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"([^"]+)"\s+(\d+)\s+(\d+)'},
    # Kubernetes style
    {"name": "kubernetes", "pattern": r'^(\S+)\s+(\S+)\s+(\S+)\s+(.*)$'},
]

# Known error patterns for classification
ERROR_PATTERNS = {
    "database": ["database", "db", "sql", "mysql", "postgres", "mongodb", "connection pool", "query timeout"],
    "network": ["network", "timeout", "connection refused", "unreachable", "dns", "socket", "ssl", "tls"],
    "memory": ["memory", "heap", "oom", "out of memory", "gc", "garbage collection", "memory leak"],
    "cpu": ["cpu", "thread", "deadlock", "high load", "process"],
    "disk": ["disk", "storage", "io", "file system", "no space"],
    "authentication": ["auth", "login", "password", "token", "jwt", "unauthorized", "forbidden", "403", "401"],
    "application": ["null pointer", "exception", "error", "crash", "stack trace", "bug"],
    "api": ["api", "rest", "http", "request", "response", "500", "502", "503", "504"],
}

SEVERITY_MAP = {
    "FATAL": "critical",
    "CRITICAL": "critical",
    "ERROR": "critical",
    "WARN": "warning",
    "WARNING": "warning",
    "INFO": "info",
    "DEBUG": "info",
}


# ======================== LOG PARSING ========================

def parse_log(raw_log: str) -> Dict[str, Any]:
    """Parse a raw log line into structured format"""
    for pattern_info in LOG_PATTERNS:
        match = re.match(pattern_info["pattern"], raw_log, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if pattern_info["name"] == "standard":
                return {
                    "severity": SEVERITY_MAP.get(groups[0].upper(), "info"),
                    "level": groups[0].upper(),
                    "service": groups[1],
                    "message": groups[2],
                    "pattern_type": "standard"
                }
            elif pattern_info["name"] == "timestamped":
                return {
                    "timestamp": groups[0],
                    "severity": SEVERITY_MAP.get(groups[1].upper(), "info"),
                    "level": groups[1].upper(),
                    "service": groups[2],
                    "message": groups[3],
                    "pattern_type": "timestamped"
                }
            elif pattern_info["name"] == "json_like":
                return {
                    "severity": SEVERITY_MAP.get(groups[0].upper(), "info"),
                    "level": groups[0].upper(),
                    "service": groups[1],
                    "message": groups[2],
                    "pattern_type": "json"
                }
    
    # Default parsing - try to extract severity from keywords
    severity = "info"
    level = "INFO"
    for sev in ["FATAL", "CRITICAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"]:
        if sev in raw_log.upper():
            level = sev
            severity = SEVERITY_MAP.get(sev, "info")
            break
    
    return {
        "severity": severity,
        "level": level,
        "service": "unknown",
        "message": raw_log,
        "pattern_type": "unknown"
    }


def classify_log_category(message: str) -> str:
    """Classify log message into a category"""
    message_lower = message.lower()
    
    for category, keywords in ERROR_PATTERNS.items():
        if any(keyword in message_lower for keyword in keywords):
            return category
    
    return "general"


def extract_error_signature(message: str) -> str:
    """Extract a normalized error signature for deduplication"""
    # Remove timestamps, IDs, numbers
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}', '[TIMESTAMP]', message)
    normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '[UUID]', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\b\d+\b', '[NUM]', normalized)
    normalized = re.sub(r'\b0x[0-9a-f]+\b', '[HEX]', normalized, flags=re.IGNORECASE)
    
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ======================== ANOMALY DETECTION ========================

class LogAnomalyDetector:
    """Simple anomaly detection for log patterns"""
    
    def __init__(self, history_hours: int = 24):
        self.history_hours = history_hours
    
    async def detect_anomalies(self, logs: List[Dict]) -> List[Dict]:
        """Detect anomalies in recent logs"""
        anomalies = []
        
        # Get baseline from history
        baseline = await self._get_baseline()
        
        # Analyze current logs
        current_stats = self._analyze_logs(logs)
        
        # Compare with baseline
        for service, stats in current_stats.items():
            baseline_stats = baseline.get(service, {})
            
            # Check error rate spike
            if stats.get("error_rate", 0) > 0:
                baseline_error_rate = baseline_stats.get("error_rate", 0.1)
                if stats["error_rate"] > baseline_error_rate * 3:  # 3x spike
                    anomalies.append({
                        "type": "error_rate_spike",
                        "service": service,
                        "current_rate": stats["error_rate"],
                        "baseline_rate": baseline_error_rate,
                        "severity": "critical" if stats["error_rate"] > 0.5 else "warning",
                        "description": f"Error rate spike detected: {stats['error_rate']:.1%} vs baseline {baseline_error_rate:.1%}"
                    })
            
            # Check volume spike
            if stats.get("count", 0) > 0:
                baseline_count = baseline_stats.get("avg_count", 10)
                if stats["count"] > baseline_count * 5:  # 5x spike
                    anomalies.append({
                        "type": "log_volume_spike",
                        "service": service,
                        "current_count": stats["count"],
                        "baseline_count": baseline_count,
                        "severity": "warning",
                        "description": f"Log volume spike: {stats['count']} logs vs baseline {baseline_count:.0f}"
                    })
            
            # Check new error patterns
            for pattern in stats.get("error_patterns", []):
                if pattern not in baseline_stats.get("known_patterns", []):
                    anomalies.append({
                        "type": "new_error_pattern",
                        "service": service,
                        "pattern": pattern,
                        "severity": "warning",
                        "description": f"New error pattern detected: {pattern[:100]}"
                    })
        
        return anomalies
    
    async def _get_baseline(self) -> Dict[str, Dict]:
        """Get baseline statistics from historical data"""
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=self.history_hours)
        
        try:
            historical_logs = await db.logs.find({
                "timestamp": {"$gte": time_threshold.isoformat()}
            }, {"_id": 0}).to_list(10000)
            
            return self._analyze_logs(historical_logs, is_baseline=True)
        except Exception as e:
            logger.error(f"Failed to get baseline: {e}")
            return {}
    
    def _analyze_logs(self, logs: List[Dict], is_baseline: bool = False) -> Dict[str, Dict]:
        """Analyze logs and extract statistics"""
        service_stats = defaultdict(lambda: {
            "count": 0,
            "error_count": 0,
            "error_patterns": set(),
            "categories": Counter()
        })
        
        for log in logs:
            service = log.get("service", "unknown")
            stats = service_stats[service]
            stats["count"] += 1
            
            if log.get("severity") in ["critical", "error"]:
                stats["error_count"] += 1
                stats["error_patterns"].add(log.get("message", "")[:100])
            
            stats["categories"][log.get("category", "general")] += 1
        
        # Calculate rates
        result = {}
        for service, stats in service_stats.items():
            result[service] = {
                "count": stats["count"],
                "error_count": stats["error_count"],
                "error_rate": stats["error_count"] / max(stats["count"], 1),
                "error_patterns": list(stats["error_patterns"])[:20],
                "categories": dict(stats["categories"])
            }
            
            if is_baseline:
                # For baseline, calculate averages
                result[service]["avg_count"] = stats["count"] / max(self.history_hours, 1)
                result[service]["known_patterns"] = list(stats["error_patterns"])
        
        return result


# ======================== LOG DEDUPLICATION ========================

async def deduplicate_logs(logs: List[Dict], time_window_minutes: int = 5) -> Dict[str, Any]:
    """Deduplicate logs and return summary"""
    signature_groups = defaultdict(list)
    
    for log in logs:
        signature = extract_error_signature(log.get("message", ""))
        signature_groups[signature].append(log)
    
    deduplicated = []
    suppressed_count = 0
    
    for signature, group in signature_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Keep first occurrence, count rest as suppressed
            representative = group[0].copy()
            representative["occurrence_count"] = len(group)
            representative["first_seen"] = min(g.get("timestamp", "") for g in group)
            representative["last_seen"] = max(g.get("timestamp", "") for g in group)
            deduplicated.append(representative)
            suppressed_count += len(group) - 1
    
    return {
        "original_count": len(logs),
        "deduplicated_count": len(deduplicated),
        "suppressed_count": suppressed_count,
        "logs": deduplicated
    }


# ======================== LOG CORRELATION ========================

async def correlate_logs(logs: List[Dict], time_window_minutes: int = 5) -> List[Dict]:
    """Correlate related logs into event groups"""
    if not logs:
        return []
    
    # Group by time windows
    time_groups = defaultdict(list)
    for log in logs:
        timestamp_str = log.get("timestamp", datetime.now(timezone.utc).isoformat())
        try:
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = timestamp_str
        except:
            timestamp = datetime.now(timezone.utc)
        
        # Round to time window
        window_key = timestamp.replace(second=0, microsecond=0)
        window_key = window_key.replace(minute=(window_key.minute // time_window_minutes) * time_window_minutes)
        time_groups[window_key.isoformat()].append(log)
    
    # Create correlated events
    correlated_events = []
    for window_key, window_logs in time_groups.items():
        # Group by service within time window
        service_logs = defaultdict(list)
        for log in window_logs:
            service_logs[log.get("service", "unknown")].append(log)
        
        # Check for correlation patterns
        services_affected = list(service_logs.keys())
        error_logs = [l for l in window_logs if l.get("severity") in ["critical", "error"]]
        
        if len(error_logs) >= 2 or len(services_affected) >= 2:
            # Potential correlated event
            categories = [l.get("category", "general") for l in error_logs]
            primary_category = Counter(categories).most_common(1)[0][0] if categories else "general"
            
            correlated_events.append({
                "id": str(uuid.uuid4()),
                "time_window": window_key,
                "services_affected": services_affected,
                "total_logs": len(window_logs),
                "error_count": len(error_logs),
                "primary_category": primary_category,
                "severity": "critical" if len(error_logs) >= 5 else "warning",
                "sample_messages": [l.get("message", "")[:200] for l in error_logs[:5]],
                "correlation_score": min(len(error_logs) / 10, 1.0)
            })
    
    return sorted(correlated_events, key=lambda x: x.get("error_count", 0), reverse=True)


# ======================== LOG STATISTICS ========================

async def get_log_statistics(hours: int = 24) -> Dict[str, Any]:
    """Get comprehensive log statistics"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    try:
        logs = await db.logs.find({
            "timestamp": {"$gte": time_threshold.isoformat()}
        }, {"_id": 0}).to_list(50000)
    except:
        logs = []
    
    if not logs:
        return {
            "total_logs": 0,
            "by_severity": {},
            "by_service": {},
            "by_category": {},
            "error_rate": 0,
            "top_errors": [],
            "timeline": []
        }
    
    # Calculate statistics
    by_severity = Counter(l.get("severity", "info") for l in logs)
    by_service = Counter(l.get("service", "unknown") for l in logs)
    by_category = Counter(l.get("category", "general") for l in logs)
    
    error_count = by_severity.get("critical", 0) + by_severity.get("error", 0)
    error_rate = error_count / len(logs) if logs else 0
    
    # Top error messages
    error_messages = [l.get("message", "") for l in logs if l.get("severity") in ["critical", "error"]]
    top_errors = Counter(error_messages).most_common(10)
    
    # Timeline (hourly buckets)
    timeline = defaultdict(lambda: {"total": 0, "errors": 0})
    for log in logs:
        try:
            ts = datetime.fromisoformat(log.get("timestamp", "").replace("Z", "+00:00"))
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            timeline[hour_key]["total"] += 1
            if log.get("severity") in ["critical", "error"]:
                timeline[hour_key]["errors"] += 1
        except:
            pass
    
    return {
        "total_logs": len(logs),
        "by_severity": dict(by_severity),
        "by_service": dict(by_service.most_common(20)),
        "by_category": dict(by_category),
        "error_rate": error_rate,
        "top_errors": [{"message": m[:200], "count": c} for m, c in top_errors],
        "timeline": [{"hour": k, **v} for k, v in sorted(timeline.items())]
    }


# ======================== SIMULATED LOG GENERATOR ========================

SAMPLE_SERVICES = ["payment-api", "user-service", "auth-service", "order-service", "inventory-api", "notification-service", "gateway-api"]
SAMPLE_MESSAGES = {
    "critical": [
        "Database connection pool exhausted - no available connections",
        "Out of memory error - heap space exceeded",
        "Service crashed with unhandled exception",
        "Disk space critical - less than 5% remaining",
        "SSL certificate expired - all HTTPS requests failing",
        "Authentication service unavailable - all logins blocked",
        "Message queue overflow - messages being dropped",
    ],
    "warning": [
        "High CPU usage detected - 85% utilization",
        "Response time degraded - average latency 2500ms",
        "Memory usage high - approaching threshold",
        "Connection timeout to external API",
        "Rate limit threshold approaching",
        "Database query taking longer than expected",
        "Cache miss rate increasing",
    ],
    "info": [
        "Service started successfully",
        "Health check passed",
        "Configuration reloaded",
        "New deployment completed",
        "Scheduled job completed",
        "User session created",
        "API request processed successfully",
    ]
}

import random

async def generate_sample_logs(count: int = 100) -> List[Dict]:
    """Generate realistic sample logs for demo"""
    logs = []
    now = datetime.now(timezone.utc)
    
    # Weight towards more info logs
    severity_weights = [("critical", 0.1), ("warning", 0.2), ("info", 0.7)]
    
    for i in range(count):
        # Random time within last hour
        timestamp = now - timedelta(minutes=random.randint(0, 60), seconds=random.randint(0, 59))
        
        # Weighted severity selection
        rand = random.random()
        cumulative = 0
        severity = "info"
        for sev, weight in severity_weights:
            cumulative += weight
            if rand <= cumulative:
                severity = sev
                break
        
        service = random.choice(SAMPLE_SERVICES)
        message = random.choice(SAMPLE_MESSAGES.get(severity, SAMPLE_MESSAGES["info"]))
        
        # Add some variation
        if random.random() > 0.7:
            message += f" [request_id={uuid.uuid4().hex[:8]}]"
        
        log = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp.isoformat(),
            "severity": severity,
            "level": severity.upper(),
            "service": service,
            "message": message,
            "category": classify_log_category(message),
            "host": f"node-{random.randint(1, 5)}.prod",
            "source": "application",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        logs.append(log)
    
    return logs
