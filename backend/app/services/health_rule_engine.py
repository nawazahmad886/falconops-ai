"""
FalconOps AI - Health Rule Engine
Evaluate metrics against health rules and trigger alerts
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from ..core.database import db

# Health Rule Categories
RULE_CATEGORIES = [
    {"id": "infrastructure", "name": "Infrastructure", "icon": "server"},
    {"id": "application", "name": "Application", "icon": "cpu"},
    {"id": "database", "name": "Database", "icon": "database"},
    {"id": "network", "name": "Network", "icon": "network"},
    {"id": "security", "name": "Security", "icon": "shield"},
    {"id": "custom", "name": "Custom", "icon": "settings"}
]

# Metric Types
METRIC_TYPES = [
    # Infrastructure
    {"id": "cpu_usage", "name": "CPU Usage", "unit": "%", "category": "infrastructure"},
    {"id": "memory_usage", "name": "Memory Usage", "unit": "%", "category": "infrastructure"},
    {"id": "disk_usage", "name": "Disk Usage", "unit": "%", "category": "infrastructure"},
    {"id": "availability", "name": "Availability", "unit": "%", "category": "infrastructure"},
    {"id": "load_average", "name": "Load Average", "unit": "", "category": "infrastructure"},
    # Network
    {"id": "network_in", "name": "Network In", "unit": "MB/s", "category": "network"},
    {"id": "network_out", "name": "Network Out", "unit": "MB/s", "category": "network"},
    {"id": "packet_loss", "name": "Packet Loss", "unit": "%", "category": "network"},
    # Application
    {"id": "response_time", "name": "Response Time", "unit": "ms", "category": "application"},
    {"id": "error_rate", "name": "Error Rate", "unit": "%", "category": "application"},
    {"id": "request_rate", "name": "Request Rate", "unit": "req/s", "category": "application"},
    {"id": "throughput", "name": "Throughput", "unit": "ops/s", "category": "application"},
    {"id": "apdex_score", "name": "Apdex Score", "unit": "", "category": "application"},
    # Database
    {"id": "active_sessions", "name": "Active Sessions", "unit": "", "category": "database"},
    {"id": "connection_count", "name": "Connection Count", "unit": "", "category": "database"},
    {"id": "connection_utilization", "name": "Connection Utilization", "unit": "%", "category": "database"},
    {"id": "cache_hit_ratio", "name": "Cache Hit Ratio", "unit": "%", "category": "database"},
    {"id": "query_time", "name": "Query Time", "unit": "ms", "category": "database"},
    {"id": "deadlocks", "name": "Deadlocks", "unit": "", "category": "database"},
    {"id": "replication_lag", "name": "Replication Lag", "unit": "s", "category": "database"},
    {"id": "slow_query_count", "name": "Slow Query Count", "unit": "", "category": "database"},
    {"id": "database_size", "name": "Database Size", "unit": "MB", "category": "database"},
    {"id": "tps", "name": "Transactions/sec", "unit": "tps", "category": "database"},
]

# Operators
OPERATORS = [
    {"id": "greater_than", "name": "Greater than", "symbol": ">"},
    {"id": "less_than", "name": "Less than", "symbol": "<"},
    {"id": "equals", "name": "Equals", "symbol": "="},
    {"id": "not_equals", "name": "Not equals", "symbol": "!="},
    {"id": "greater_than_or_equal", "name": "Greater than or equal", "symbol": ">="},
    {"id": "less_than_or_equal", "name": "Less than or equal", "symbol": "<="},
    {"id": "between", "name": "Between", "symbol": "BETWEEN"},
    {"id": "not_between", "name": "Not between", "symbol": "NOT BETWEEN"},
]

# Default Health Rules Templates
DEFAULT_RULE_TEMPLATES = [
    {
        "id": "high_cpu",
        "name": "High CPU Usage",
        "description": "Alert when CPU usage exceeds threshold",
        "metric": "cpu_usage",
        "operator": "greater_than",
        "threshold": 85,
        "duration": 300,  # 5 minutes
        "severity": "warning",
        "category": "infrastructure"
    },
    {
        "id": "critical_cpu",
        "name": "Critical CPU Usage",
        "description": "Critical alert when CPU is critically high",
        "metric": "cpu_usage",
        "operator": "greater_than",
        "threshold": 95,
        "duration": 120,  # 2 minutes
        "severity": "critical",
        "category": "infrastructure"
    },
    {
        "id": "high_memory",
        "name": "High Memory Usage",
        "description": "Alert when memory usage exceeds threshold",
        "metric": "memory_usage",
        "operator": "greater_than",
        "threshold": 90,
        "duration": 300,
        "severity": "warning",
        "category": "infrastructure"
    },
    {
        "id": "disk_space_low",
        "name": "Low Disk Space",
        "description": "Alert when disk usage is high",
        "metric": "disk_usage",
        "operator": "greater_than",
        "threshold": 85,
        "duration": 0,  # Immediate
        "severity": "warning",
        "category": "infrastructure"
    },
    {
        "id": "disk_space_critical",
        "name": "Critical Disk Space",
        "description": "Critical alert when disk is almost full",
        "metric": "disk_usage",
        "operator": "greater_than",
        "threshold": 95,
        "duration": 0,
        "severity": "critical",
        "category": "infrastructure"
    },
    {
        "id": "slow_response",
        "name": "Slow Response Time",
        "description": "Alert when response time is slow",
        "metric": "response_time",
        "operator": "greater_than",
        "threshold": 2000,  # 2 seconds
        "duration": 180,
        "severity": "warning",
        "category": "application"
    },
    {
        "id": "high_error_rate",
        "name": "High Error Rate",
        "description": "Alert when error rate exceeds threshold",
        "metric": "error_rate",
        "operator": "greater_than",
        "threshold": 5,  # 5%
        "duration": 60,
        "severity": "critical",
        "category": "application"
    },
    {
        "id": "service_unavailable",
        "name": "Service Unavailable",
        "description": "Alert when service availability drops",
        "metric": "availability",
        "operator": "less_than",
        "threshold": 99.9,
        "duration": 60,
        "severity": "critical",
        "category": "infrastructure"
    },
]


class HealthRuleEngine:
    """Engine for evaluating health rules against metrics"""
    
    def __init__(self):
        self.active_violations = {}  # Track ongoing rule violations
    
    async def get_rule_templates(self) -> List[Dict]:
        """Get predefined health rule templates"""
        return DEFAULT_RULE_TEMPLATES
    
    async def get_rule_categories(self) -> List[Dict]:
        """Get available rule categories"""
        return RULE_CATEGORIES
    
    async def get_metric_types(self) -> List[Dict]:
        """Get available metric types"""
        return METRIC_TYPES
    
    async def get_operators(self) -> List[Dict]:
        """Get available operators"""
        return OPERATORS
    
    async def create_rule(
        self,
        name: str,
        metric: str,
        operator: str,
        threshold: float,
        threshold_max: Optional[float] = None,
        duration: int = 300,
        severity: str = "warning",
        category: str = "custom",
        component_type: str = "infrastructure",
        description: str = "",
        service_filter: Optional[str] = None,
        host_filter: Optional[str] = None,
        enabled: bool = True,
        conditions: Optional[list] = None,
        action: str = "alert",
        tenant_id: Optional[str] = None,
        created_by: str = "system"
    ) -> Dict:
        """Create a new health rule"""
        rule_id = str(uuid.uuid4())
        
        rule_doc = {
            "id": rule_id,
            "name": name,
            "description": description,
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "threshold_max": threshold_max,
            "duration": duration,
            "severity": severity,
            "category": category,
            "component_type": component_type,
            "service_filter": service_filter,
            "host_filter": host_filter,
            "enabled": enabled,
            "conditions": conditions or [],
            "action": action,
            "tenant_id": tenant_id,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "last_evaluated": None,
            "violations_count": 0,
            "alerts_triggered": 0
        }
        
        await db.health_rules.insert_one(rule_doc)
        return {k: v for k, v in rule_doc.items() if k != "_id"}
    
    async def update_rule(self, rule_id: str, updates: Dict) -> Optional[Dict]:
        """Update an existing health rule"""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.health_rules.find_one_and_update(
            {"id": rule_id},
            {"$set": updates},
            return_document=True
        )
        
        if result:
            return {k: v for k, v in result.items() if k != "_id"}
        return None
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a health rule"""
        result = await db.health_rules.delete_one({"id": rule_id})
        return result.deleted_count > 0
    
    async def get_rules(
        self,
        category: Optional[str] = None,
        enabled_only: bool = False,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all health rules with optional filters"""
        query = {}
        if category:
            query["category"] = category
        if enabled_only:
            query["enabled"] = True
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        rules = await db.health_rules.find(query, {"_id": 0}).to_list(500)
        return rules
    
    async def get_rule(self, rule_id: str) -> Optional[Dict]:
        """Get a single health rule by ID"""
        rule = await db.health_rules.find_one({"id": rule_id}, {"_id": 0})
        return rule
    
    def evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate a single condition"""
        if operator == "greater_than":
            return value > threshold
        elif operator == "less_than":
            return value < threshold
        elif operator == "equals":
            return value == threshold
        elif operator == "not_equals":
            return value != threshold
        elif operator == "greater_than_or_equal":
            return value >= threshold
        elif operator == "less_than_or_equal":
            return value <= threshold
        return False
    
    async def evaluate_rule(
        self,
        rule: Dict,
        metric_value: float,
        service: Optional[str] = None,
        host: Optional[str] = None
    ) -> Dict:
        """Evaluate a single rule against a metric value"""
        result = {
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "metric": rule["metric"],
            "current_value": metric_value,
            "threshold": rule["threshold"],
            "operator": rule["operator"],
            "violated": False,
            "severity": rule["severity"],
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Check service/host filters
        if rule.get("service_filter") and service != rule["service_filter"]:
            result["skipped"] = True
            result["skip_reason"] = "Service filter mismatch"
            return result
        
        if rule.get("host_filter") and host != rule["host_filter"]:
            result["skipped"] = True
            result["skip_reason"] = "Host filter mismatch"
            return result
        
        # Evaluate the condition
        violated = self.evaluate_condition(metric_value, rule["operator"], rule["threshold"])
        result["violated"] = violated
        
        # Track violation for duration check
        violation_key = f"{rule['id']}_{service or 'all'}_{host or 'all'}"
        
        if violated:
            if violation_key not in self.active_violations:
                self.active_violations[violation_key] = datetime.now(timezone.utc)
            
            # Check if violation duration is exceeded
            violation_start = self.active_violations[violation_key]
            violation_duration = (datetime.now(timezone.utc) - violation_start).total_seconds()
            
            if violation_duration >= rule["duration"]:
                result["alert_triggered"] = True
                result["violation_duration"] = violation_duration
        else:
            # Clear violation if condition is no longer met
            if violation_key in self.active_violations:
                del self.active_violations[violation_key]
        
        # Update rule's last evaluated time
        await db.health_rules.update_one(
            {"id": rule["id"]},
            {
                "$set": {"last_evaluated": result["evaluated_at"]},
                "$inc": {"violations_count": 1 if violated else 0}
            }
        )
        
        return result
    
    async def evaluate_metrics(
        self,
        metrics: Dict[str, float],
        service: Optional[str] = None,
        host: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Evaluate all enabled rules against a set of metrics"""
        rules = await self.get_rules(enabled_only=True, tenant_id=tenant_id)
        
        results = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "host": host,
            "rules_evaluated": 0,
            "violations": [],
            "alerts_to_trigger": []
        }
        
        for rule in rules:
            metric_name = rule["metric"]
            if metric_name in metrics:
                metric_value = metrics[metric_name]
                evaluation = await self.evaluate_rule(rule, metric_value, service, host)
                results["rules_evaluated"] += 1
                
                if evaluation.get("violated"):
                    results["violations"].append(evaluation)
                    
                    if evaluation.get("alert_triggered"):
                        results["alerts_to_trigger"].append({
                            "rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "metric": metric_name,
                            "value": metric_value,
                            "threshold": rule["threshold"],
                            "severity": rule["severity"],
                            "service": service,
                            "host": host
                        })
        
        return results
    
    async def trigger_alert_from_violation(
        self,
        violation: Dict,
        service: Optional[str] = None,
        host: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Create an alert from a rule violation"""
        alert_id = str(uuid.uuid4())
        
        alert_doc = {
            "id": alert_id,
            "title": f"{violation['rule_name']} - {violation['metric']} threshold exceeded",
            "description": f"Value {violation['value']} exceeded threshold {violation['threshold']}",
            "severity": violation["severity"],
            "source": "health_rule_engine",
            "service": service,
            "host": host,
            "status": "open",
            "rule_id": violation["rule_id"],
            "metric": violation["metric"],
            "current_value": violation["value"],
            "threshold": violation["threshold"],
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.alerts.insert_one(alert_doc)
        
        # Update rule's alert count
        await db.health_rules.update_one(
            {"id": violation["rule_id"]},
            {"$inc": {"alerts_triggered": 1}}
        )
        
        return {k: v for k, v in alert_doc.items() if k != "_id"}
    
    async def get_rule_stats(self, tenant_id: Optional[str] = None) -> Dict:
        """Get health rule statistics"""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        total_rules = await db.health_rules.count_documents(query)
        enabled_rules = await db.health_rules.count_documents({**query, "enabled": True})
        
        # Rules by category
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$project": {"category": "$_id", "count": 1, "_id": 0}}
        ]
        by_category = await db.health_rules.aggregate(pipeline).to_list(20)
        
        # Rules by severity
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
            {"$project": {"severity": "$_id", "count": 1, "_id": 0}}
        ]
        by_severity = await db.health_rules.aggregate(pipeline).to_list(10)
        
        # Top violators
        top_violators = await db.health_rules.find(
            query, {"_id": 0, "id": 1, "name": 1, "violations_count": 1}
        ).sort("violations_count", -1).limit(5).to_list(5)
        
        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "by_category": by_category,
            "by_severity": by_severity,
            "top_violators": top_violators,
            "active_violations": len(self.active_violations)
        }


# Singleton instance
health_rule_engine = HealthRuleEngine()
