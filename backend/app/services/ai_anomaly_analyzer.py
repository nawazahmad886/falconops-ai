"""
FalconOps AI - AI Anomaly Analysis Engine
Uses LLM for intelligent root cause analysis
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from ..core.database import db

# Try to import Emergent LLM integration
try:
    from emergentintegrations.llm import LlmChat
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: emergentintegrations not available for AI analysis")


class AIAnomalyAnalyzer:
    """AI-powered anomaly analysis with root cause detection"""
    
    def __init__(self):
        self.llm = None
        if LLM_AVAILABLE:
            try:
                self.llm = LlmChat(
                    provider="anthropic",
                    model="claude-sonnet-4-20250514"
                )
            except Exception as e:
                print(f"LLM initialization error: {e}")
    
    async def analyze_anomaly(
        self,
        anomaly_data: Dict,
        include_correlated_metrics: bool = True,
        include_logs: bool = True,
        include_topology: bool = True,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Analyze an anomaly and provide root cause insights"""
        
        # Gather context
        context = await self._gather_context(
            anomaly_data,
            include_correlated_metrics,
            include_logs,
            include_topology,
            tenant_id
        )
        
        if not self.llm:
            # Fallback to rule-based analysis
            return self._rule_based_analysis(anomaly_data, context)
        
        # Build prompt for LLM analysis
        prompt = self._build_analysis_prompt(anomaly_data, context)
        
        try:
            response = await asyncio.to_thread(
                self.llm.generate,
                prompt,
                system_prompt="""You are an expert AIOps analyst at a NOC. 
                Analyze the provided metric anomaly and correlated data to determine:
                1. The most likely root cause
                2. Impact assessment
                3. Recommended remediation steps
                Be concise and actionable. Focus on the technical details."""
            )
            
            return {
                "anomaly_id": anomaly_data.get("id"),
                "metric_name": anomaly_data.get("name"),
                "analysis_type": "ai_powered",
                "root_cause": self._extract_root_cause(response),
                "impact": self._extract_impact(response),
                "recommendations": self._extract_recommendations(response),
                "full_analysis": response,
                "context_used": {
                    "correlated_metrics": len(context.get("correlated_metrics", [])),
                    "logs": len(context.get("logs", [])),
                    "topology": bool(context.get("topology"))
                },
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            print(f"AI analysis error: {e}")
            return self._rule_based_analysis(anomaly_data, context)
    
    async def _gather_context(
        self,
        anomaly_data: Dict,
        include_metrics: bool,
        include_logs: bool,
        include_topology: bool,
        tenant_id: Optional[str]
    ) -> Dict:
        """Gather correlated context for analysis"""
        context = {}
        
        timestamp = anomaly_data.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        # Parse timestamp
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except:
            ts = datetime.now(timezone.utc)
        
        # Time window around anomaly (5 minutes before, 1 minute after)
        start_time = (ts - timedelta(minutes=5)).isoformat()
        end_time = (ts + timedelta(minutes=1)).isoformat()
        
        tags = anomaly_data.get("tags", {})
        host = tags.get("host")
        service = tags.get("service")
        
        # Get correlated metrics
        if include_metrics and host:
            query = {
                "tags.host": host,
                "timestamp": {"$gte": start_time, "$lte": end_time}
            }
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            correlated = await db.metrics_timeseries.find(
                query, {"_id": 0, "name": 1, "value": 1, "timestamp": 1, "anomaly": 1}
            ).sort("timestamp", -1).limit(50).to_list(50)
            
            context["correlated_metrics"] = correlated
        
        # Get related logs
        if include_logs and (host or service):
            log_query = {
                "timestamp": {"$gte": start_time, "$lte": end_time},
                "level": {"$in": ["error", "warn", "fatal"]}
            }
            if host:
                log_query["host"] = host
            if service:
                log_query["service"] = service
            if tenant_id:
                log_query["tenant_id"] = tenant_id
            
            logs = await db.logs.find(
                log_query, {"_id": 0, "message": 1, "level": 1, "timestamp": 1, "service": 1}
            ).sort("timestamp", -1).limit(20).to_list(20)
            
            context["logs"] = logs
        
        # Get topology information
        if include_topology and service:
            service_node = await db.topology_nodes.find_one(
                {"name": service}, {"_id": 0}
            )
            if service_node:
                # Get connected services
                connections = await db.topology_edges.find(
                    {"$or": [
                        {"source_id": service_node.get("id")},
                        {"target_id": service_node.get("id")}
                    ]},
                    {"_id": 0}
                ).to_list(20)
                
                context["topology"] = {
                    "service": service_node,
                    "connections": connections
                }
        
        return context
    
    def _build_analysis_prompt(self, anomaly_data: Dict, context: Dict) -> str:
        """Build prompt for LLM analysis"""
        prompt_parts = []
        
        # Anomaly details
        prompt_parts.append(f"""
ANOMALY DETECTED:
- Metric: {anomaly_data.get('name')}
- Value: {anomaly_data.get('value')}
- Z-Score: {anomaly_data.get('anomaly', {}).get('z_score', 'N/A')}
- Severity: {anomaly_data.get('anomaly', {}).get('severity', 'unknown')}
- Baseline Mean: {anomaly_data.get('anomaly', {}).get('baseline_mean', 'N/A')}
- Baseline StdDev: {anomaly_data.get('anomaly', {}).get('baseline_stddev', 'N/A')}
- Host: {anomaly_data.get('tags', {}).get('host', 'unknown')}
- Service: {anomaly_data.get('tags', {}).get('service', 'unknown')}
- Timestamp: {anomaly_data.get('timestamp')}
""")
        
        # Correlated metrics
        if context.get("correlated_metrics"):
            metrics_summary = []
            for m in context["correlated_metrics"][:10]:
                anomaly_flag = "⚠️ ANOMALY" if m.get("anomaly", {}).get("is_anomaly") else ""
                metrics_summary.append(f"  - {m['name']}: {m['value']} {anomaly_flag}")
            
            prompt_parts.append(f"""
CORRELATED METRICS (same host, same time window):
{chr(10).join(metrics_summary)}
""")
        
        # Related logs
        if context.get("logs"):
            logs_summary = []
            for log in context["logs"][:10]:
                logs_summary.append(f"  [{log.get('level', 'INFO').upper()}] {log.get('message', '')[:100]}")
            
            prompt_parts.append(f"""
RELATED ERROR/WARNING LOGS:
{chr(10).join(logs_summary)}
""")
        
        # Topology
        if context.get("topology"):
            topo = context["topology"]
            service_info = topo.get("service", {})
            connections = topo.get("connections", [])
            
            prompt_parts.append(f"""
SERVICE TOPOLOGY:
- Service: {service_info.get('name')}
- Type: {service_info.get('type')}
- Status: {service_info.get('status')}
- Connected Services: {len(connections)}
""")
        
        prompt_parts.append("""
Based on this data, provide:
1. ROOT CAUSE: What is the most likely cause of this anomaly?
2. IMPACT: What services or users might be affected?
3. RECOMMENDATIONS: What specific actions should be taken to resolve this?
""")
        
        return "\n".join(prompt_parts)
    
    def _extract_root_cause(self, response: str) -> str:
        """Extract root cause from LLM response"""
        lines = response.split("\n")
        for i, line in enumerate(lines):
            if "ROOT CAUSE" in line.upper() or "CAUSE" in line.upper():
                # Get next few lines
                cause_lines = []
                for j in range(i, min(i + 5, len(lines))):
                    if lines[j].strip() and "IMPACT" not in lines[j].upper() and "RECOMMEND" not in lines[j].upper():
                        cause_lines.append(lines[j].strip())
                return " ".join(cause_lines)[:500]
        return response[:300]
    
    def _extract_impact(self, response: str) -> str:
        """Extract impact assessment from LLM response"""
        lines = response.split("\n")
        for i, line in enumerate(lines):
            if "IMPACT" in line.upper():
                impact_lines = []
                for j in range(i, min(i + 5, len(lines))):
                    if lines[j].strip() and "RECOMMEND" not in lines[j].upper():
                        impact_lines.append(lines[j].strip())
                return " ".join(impact_lines)[:500]
        return "Impact assessment not available"
    
    def _extract_recommendations(self, response: str) -> List[str]:
        """Extract recommendations from LLM response"""
        recommendations = []
        lines = response.split("\n")
        in_recommendations = False
        
        for line in lines:
            if "RECOMMEND" in line.upper():
                in_recommendations = True
                continue
            
            if in_recommendations and line.strip():
                # Clean up the line
                clean_line = line.strip().lstrip("-").lstrip("•").lstrip("*").strip()
                if clean_line and len(clean_line) > 10:
                    recommendations.append(clean_line)
                
                if len(recommendations) >= 5:
                    break
        
        return recommendations if recommendations else ["Review the anomaly manually", "Check system logs for more details"]
    
    def _rule_based_analysis(self, anomaly_data: Dict, context: Dict) -> Dict:
        """Fallback rule-based analysis when LLM is unavailable"""
        metric_name = anomaly_data.get("name", "")
        value = anomaly_data.get("value", 0)
        z_score = anomaly_data.get("anomaly", {}).get("z_score", 0)
        
        # Rule-based root cause detection
        root_cause = "Unknown cause"
        impact = "Potential service degradation"
        recommendations = []
        
        # CPU metrics
        if "cpu" in metric_name.lower():
            if value > 90:
                root_cause = "CPU saturation detected - likely due to high processing load or runaway process"
                impact = "Service response times may be degraded, potential request timeouts"
                recommendations = [
                    "Identify high-CPU processes using 'top' or 'htop'",
                    "Check for runaway processes or infinite loops",
                    "Consider scaling horizontally if load is legitimate",
                    "Review recent deployments for resource-intensive changes"
                ]
        
        # Memory metrics
        elif "memory" in metric_name.lower():
            if value > 90:
                root_cause = "Memory exhaustion - possible memory leak or insufficient allocation"
                impact = "Risk of OOM kills, service crashes, or swap thrashing"
                recommendations = [
                    "Check for memory leaks in application",
                    "Review memory limits and allocations",
                    "Restart affected services if immediate relief needed",
                    "Analyze heap dumps if available"
                ]
        
        # Disk metrics
        elif "disk" in metric_name.lower():
            if value > 85:
                root_cause = "Disk space running low - log accumulation or data growth"
                impact = "Service failures when disk is full, data loss risk"
                recommendations = [
                    "Clean up old logs and temporary files",
                    "Expand disk capacity or add storage",
                    "Implement log rotation policies",
                    "Archive old data to cold storage"
                ]
        
        # Response time metrics
        elif "response_time" in metric_name.lower() or "latency" in metric_name.lower():
            root_cause = "Elevated response times - possible backend bottleneck or network issues"
            impact = "Poor user experience, potential timeout errors"
            recommendations = [
                "Check database query performance",
                "Review network latency between services",
                "Look for resource contention",
                "Check for dependency service issues"
            ]
        
        # Error rate metrics
        elif "error" in metric_name.lower():
            root_cause = "Increased error rate - application or dependency failures"
            impact = "User-facing errors, data inconsistency risks"
            recommendations = [
                "Check application logs for error details",
                "Verify dependent service health",
                "Review recent code deployments",
                "Check database connection pool status"
            ]
        
        # Generic high value anomaly
        elif z_score > 3:
            root_cause = f"Significant deviation from baseline (Z-score: {z_score:.2f})"
            impact = "Potential service impact depending on metric type"
            recommendations = [
                "Investigate correlated metrics for patterns",
                "Check for recent configuration changes",
                "Review system and application logs"
            ]
        
        # Check correlated errors in logs
        error_logs = [l for l in context.get("logs", []) if l.get("level") in ["error", "fatal"]]
        if error_logs:
            root_cause += f" | Related errors found: {len(error_logs)} error logs in time window"
            recommendations.insert(0, f"Review {len(error_logs)} error logs from the same time period")
        
        return {
            "anomaly_id": anomaly_data.get("id"),
            "metric_name": metric_name,
            "analysis_type": "rule_based",
            "root_cause": root_cause,
            "impact": impact,
            "recommendations": recommendations[:5],
            "context_used": {
                "correlated_metrics": len(context.get("correlated_metrics", [])),
                "logs": len(context.get("logs", [])),
                "topology": bool(context.get("topology"))
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def correlate_anomalies(
        self,
        anomalies: List[Dict],
        time_window_minutes: int = 5,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Find correlations between multiple anomalies"""
        if len(anomalies) < 2:
            return []
        
        correlations = []
        processed = set()
        
        for i, a1 in enumerate(anomalies):
            for j, a2 in enumerate(anomalies[i+1:], i+1):
                pair_key = f"{min(i,j)}-{max(i,j)}"
                if pair_key in processed:
                    continue
                processed.add(pair_key)
                
                # Check time proximity
                try:
                    t1 = datetime.fromisoformat(a1.get("timestamp", "").replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(a2.get("timestamp", "").replace("Z", "+00:00"))
                    time_diff = abs((t2 - t1).total_seconds())
                    
                    if time_diff > time_window_minutes * 60:
                        continue
                except:
                    continue
                
                # Check host/service correlation
                host_match = a1.get("tags", {}).get("host") == a2.get("tags", {}).get("host")
                service_match = a1.get("tags", {}).get("service") == a2.get("tags", {}).get("service")
                
                if host_match or service_match:
                    correlations.append({
                        "anomaly_1": {
                            "metric": a1.get("name"),
                            "value": a1.get("value"),
                            "severity": a1.get("anomaly", {}).get("severity")
                        },
                        "anomaly_2": {
                            "metric": a2.get("name"),
                            "value": a2.get("value"),
                            "severity": a2.get("anomaly", {}).get("severity")
                        },
                        "correlation_type": "host" if host_match else "service",
                        "correlation_key": a1.get("tags", {}).get("host") or a1.get("tags", {}).get("service"),
                        "time_diff_seconds": time_diff,
                        "correlation_strength": "strong" if host_match and service_match else "moderate"
                    })
        
        return correlations


# Singleton instance
ai_anomaly_analyzer = AIAnomalyAnalyzer()
