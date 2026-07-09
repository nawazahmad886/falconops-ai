"""
FalconOps AI - Event Analyzer Service
AI-powered analysis of event/alert data from monitoring tools
"""
import os
import io
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import Counter
import pandas as pd

# AI Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


class EventAnalyzer:
    """AI-powered event/alert analyzer"""
    
    # Standard column mappings for different monitoring tools
    COLUMN_MAPPINGS = {
        'timestamp': ['timestamp', 'time', 'date', 'datetime', 'event_time', 'created_at', 'occurred_at', 'alert_time', 'timestamp_-_event_time', 'event_date'],
        'service': ['service', 'service_name', 'application', 'app', 'component', 'source', 'system'],
        'alert': ['alert', 'alert_name', 'message', 'event', 'description', 'title', 'summary', 'error', 'alert_description', 'alert_-_alert_description'],
        'severity': ['severity', 'priority', 'level', 'status', 'criticality', 'alert_level'],
        'host': ['host', 'hostname', 'server', 'node', 'instance', 'pod', 'container', 'ip'],
    }
    
    # Partial match keywords for fuzzy column detection
    COLUMN_KEYWORDS = {
        'timestamp': ['timestamp', 'time', 'date', 'when', 'occurred'],
        'service': ['service', 'application', 'app', 'component'],
        'alert': ['alert', 'description', 'message', 'event', 'error', 'summary'],
        'severity': ['severity', 'priority', 'level', 'criticality'],
        'host': ['host', 'server', 'node', 'instance', 'pod', 'ip_address'],
    }
    
    SEVERITY_MAPPING = {
        'critical': ['critical', 'crit', 'p1', 'emergency', 'fatal', 'severe', '1'],
        'warning': ['warning', 'warn', 'p2', 'major', 'high', '2', '5'],
        'info': ['info', 'information', 'p3', 'minor', 'low', 'notice', '3', '4', '0'],
    }
    
    def __init__(self):
        self.events = []
        self.analysis_id = None
        self.analysis_result = None
    
    def parse_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse uploaded file (Excel or CSV)"""
        try:
            file_ext = filename.lower().split('.')[-1]
            
            if file_ext == 'csv':
                df = pd.read_csv(io.BytesIO(file_content))
            elif file_ext in ['xlsx', 'xls']:
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return {"success": False, "error": f"Unsupported file format: {file_ext}"}
            
            # Clean column names
            df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
            
            # Normalize columns
            normalized_df = self._normalize_columns(df)
            
            # Convert to list of dicts
            self.events = normalized_df.to_dict(orient='records')
            
            # Clean NaN values
            for event in self.events:
                for key, value in event.items():
                    if pd.isna(value):
                        event[key] = None
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        event[key] = str(value)
            
            return {
                "success": True,
                "total_events": len(self.events),
                "columns_detected": list(normalized_df.columns),
                "sample_events": self.events[:5] if len(self.events) > 5 else self.events
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard format with fuzzy matching"""
        column_map = {}
        used_std_cols = set()
        
        for std_col, variations in self.COLUMN_MAPPINGS.items():
            # Phase 1: Exact match
            for col in df.columns:
                col_lower = col.lower().strip()
                if col_lower in variations and std_col not in used_std_cols:
                    column_map[col] = std_col
                    used_std_cols.add(std_col)
                    break
            
            if std_col in used_std_cols:
                continue
            
            # Phase 2: Partial/keyword match
            keywords = self.COLUMN_KEYWORDS.get(std_col, [])
            for col in df.columns:
                if col in column_map:
                    continue
                col_lower = col.lower().strip()
                for kw in keywords:
                    if kw in col_lower:
                        column_map[col] = std_col
                        used_std_cols.add(std_col)
                        break
                if std_col in used_std_cols:
                    break
        
        df = df.rename(columns=column_map)
        return df
    
    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity value to standard format"""
        if not severity:
            return 'info'
        
        severity_lower = str(severity).lower().strip()
        
        for std_sev, variations in self.SEVERITY_MAPPING.items():
            if severity_lower in variations:
                return std_sev
        
        return 'info'
    
    def detect_patterns(self) -> Dict[str, Any]:
        """Detect patterns in events"""
        if not self.events:
            return {"error": "No events loaded"}
        
        # Get all available keys to detect the best field for each category
        all_keys = set()
        for e in self.events[:10]:
            all_keys.update(e.keys())
        
        # Helper to extract field value with fallback
        def get_field(event, primary, fallbacks=None):
            val = event.get(primary)
            if val and str(val).strip():
                return str(val).strip()
            for fb in (fallbacks or []):
                val = event.get(fb)
                if val and str(val).strip():
                    return str(val).strip()
            return None
        
        # Alert frequency - try 'alert' then any description-like field
        alert_fallbacks = [k for k in all_keys if any(w in k.lower() for w in ['alert', 'description', 'message', 'error', 'event'])]
        alerts = []
        for e in self.events:
            a = get_field(e, 'alert', alert_fallbacks)
            if a:
                # Truncate very long alert names for grouping
                alerts.append(a[:100])
        alert_frequency = Counter(alerts).most_common(15)
        
        # Service frequency - try 'service' then application-like fields
        svc_fallbacks = [k for k in all_keys if any(w in k.lower() for w in ['service', 'application', 'app', 'component'])]
        services = []
        for e in self.events:
            s = get_field(e, 'service', svc_fallbacks)
            if s:
                # Clean long compound service names (e.g. "App,Application: SubApp |Alert Name")
                if '|' in s:
                    s = s.split('|')[0].strip()
                if len(s) > 60:
                    s = s[:60]
                services.append(s)
        service_frequency = Counter(services).most_common(15)
        
        # Severity distribution
        severities = [self._normalize_severity(e.get('severity')) for e in self.events]
        severity_distribution = dict(Counter(severities))
        
        # Host frequency
        host_fallbacks = [k for k in all_keys if any(w in k.lower() for w in ['host', 'server', 'node', 'instance', 'pod'])]
        hosts = []
        for e in self.events:
            h = get_field(e, 'host', host_fallbacks)
            if h:
                hosts.append(h)
        host_frequency = Counter(hosts).most_common(10)
        
        # Time-based patterns (try all timestamp-like fields)
        ts_fallbacks = [k for k in all_keys if any(w in k.lower() for w in ['timestamp', 'time', 'date', 'when'])]
        timeline = []
        for event in self.events:
            ts = get_field(event, 'timestamp', ts_fallbacks)
            if ts:
                timeline.append({
                    'timestamp': ts,
                    'alert': get_field(event, 'alert', alert_fallbacks) or 'unknown',
                    'service': get_field(event, 'service', svc_fallbacks) or 'unknown',
                    'severity': self._normalize_severity(event.get('severity'))
                })
        
        return {
            "total_events": len(self.events),
            "unique_alerts": len(set(alerts)),
            "unique_services": len(set(services)),
            "unique_hosts": len(set(hosts)),
            "alert_frequency": [{"alert": a, "count": c} for a, c in alert_frequency],
            "service_frequency": [{"service": s, "count": c} for s, c in service_frequency],
            "host_frequency": [{"host": h, "count": c} for h, c in host_frequency],
            "severity_distribution": severity_distribution,
            "timeline": timeline[:50]  # First 50 events
        }
    
    def cluster_events(self) -> List[Dict[str, Any]]:
        """Cluster related events together"""
        clusters = {}
        
        # Detect field names dynamically
        all_keys = set()
        for e in self.events[:10]:
            all_keys.update(e.keys())
        alert_fields = ['alert'] + [k for k in all_keys if any(w in k.lower() for w in ['alert', 'description', 'message', 'error']) and k != 'alert']
        svc_fields = ['service'] + [k for k in all_keys if any(w in k.lower() for w in ['service', 'application', 'component']) and k != 'service']
        host_fields = ['host'] + [k for k in all_keys if any(w in k.lower() for w in ['host', 'server', 'node', 'instance']) and k != 'host']
        
        def _get(event, fields):
            for f in fields:
                v = event.get(f)
                if v and str(v).strip():
                    return str(v).strip()
            return 'unknown'
        
        for event in self.events:
            svc = _get(event, svc_fields)
            alert = _get(event, alert_fields)
            # Clean long names
            if '|' in svc:
                svc = svc.split('|')[0].strip()
            if len(svc) > 60:
                svc = svc[:60]
            alert_short = alert[:50]
            
            key = f"{svc}:{alert_short}"
            
            if key not in clusters:
                clusters[key] = {
                    "cluster_id": str(uuid.uuid4())[:8],
                    "service": svc,
                    "alert_type": alert[:100],
                    "events": [],
                    "count": 0,
                    "severity": 'info',
                    "hosts": set()
                }
            
            clusters[key]["events"].append(event)
            clusters[key]["count"] += 1
            
            # Track hosts
            host = _get(event, host_fields)
            if host != 'unknown':
                clusters[key]["hosts"].add(host)
            
            # Escalate severity
            event_severity = self._normalize_severity(event.get('severity'))
            if event_severity == 'critical':
                clusters[key]["severity"] = 'critical'
            elif event_severity == 'warning' and clusters[key]["severity"] != 'critical':
                clusters[key]["severity"] = 'warning'
        
        # Convert to list and clean up
        result = []
        for key, cluster in clusters.items():
            cluster["hosts"] = list(cluster["hosts"])
            cluster["events"] = cluster["events"][:5]  # Keep only sample events
            result.append(cluster)
        
        # Sort by count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return result[:20]  # Top 20 clusters
    
    async def ai_analyze(self, include_knowledge_base: bool = True) -> Dict[str, Any]:
        """Perform AI-powered root cause analysis with self-learning"""
        patterns = self.detect_patterns()
        clusters = self.cluster_events()
        
        # Check knowledge base for similar incidents
        kb_suggestion = None
        if include_knowledge_base:
            try:
                from .knowledge_base_service import knowledge_base
                alerts_list = [e.get('alert', '') for e in self.events if e.get('alert')]
                services_list = list(set([e.get('service', '') for e in self.events if e.get('service')]))
                kb_suggestion = await knowledge_base.get_instant_suggestion(alerts_list[:50], services_list)
            except Exception as e:
                print(f"Knowledge base lookup error: {e}")
        
        if not AI_AVAILABLE or not EMERGENT_LLM_KEY:
            result = self._fallback_analysis()
            if kb_suggestion and kb_suggestion.get("found"):
                result["knowledge_base_match"] = kb_suggestion
            return result
        
        # Prepare enhanced event summary for AI
        event_summary = self._prepare_enhanced_event_summary(patterns, clusters)
        
        # Enhanced AI prompt for detailed analysis
        prompt = f"""You are a senior Site Reliability Engineer (SRE) and AI-powered NOC analyst with expertise in:
- Root cause analysis (RCA)
- Incident correlation
- System architecture
- Performance optimization

Analyze the following monitoring event data and provide a COMPREHENSIVE incident report.

## EVENT DATA
{event_summary}

## REQUIRED ANALYSIS FORMAT

### 1. EXECUTIVE SUMMARY
Provide a 2-3 sentence summary of the overall situation.

### 2. ROOT CAUSE ANALYSIS
- **Primary Root Cause**: [Most likely root cause with explanation]
- **Contributing Factors**: [List secondary causes]
- **Evidence**: [Data points supporting this conclusion]
- **Confidence Level**: [High/Medium/Low with percentage]

### 3. IMPACT ASSESSMENT
| Component | Impact Level | Description |
|-----------|-------------|-------------|
[List affected services/systems with impact]

### 4. INCIDENT TIMELINE
Reconstruct the likely sequence of events based on timestamps.

### 5. CORRELATION ANALYSIS
- **Related Events**: Identify how different alerts are connected
- **Cascade Pattern**: If applicable, show how one failure led to others
- **Dependencies**: Service dependencies that amplified the issue

### 6. RECOMMENDED ACTIONS
#### Immediate (Do Now)
1. [Urgent action with specific command/step]
2. [Second urgent action]

#### Short-term (Next 24 hours)
1. [Action item]
2. [Action item]

#### Long-term (Preventive)
1. [Systemic fix]
2. [Process improvement]

### 7. RUNBOOK SUGGESTIONS
Provide specific technical commands or steps for remediation:
```
[Technical commands or procedures]
```

### 8. SIMILAR INCIDENTS
Based on the pattern, mention what similar incidents might look like and how to prevent them.

Be specific, actionable, and technical in your recommendations. Avoid generic advice."""

        try:
            llm = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=str(uuid.uuid4()),
                system_message="You are a senior Site Reliability Engineer (SRE) and AI-powered NOC analyst with expertise in root cause analysis, incident correlation, system architecture, and performance optimization."
            )
            llm = llm.with_model("anthropic", "claude-sonnet-4-20250514")
            
            ai_analysis = await llm.send_message(UserMessage(text=prompt))
            
            # Generate enhanced suggestions with confidence scoring
            suggestions = await self._generate_enhanced_suggestions(patterns, clusters, kb_suggestion)
            
            # Calculate overall confidence
            confidence = self._calculate_analysis_confidence(patterns, clusters, kb_suggestion)
            
            result = {
                "success": True,
                "analysis_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "patterns": patterns,
                "clusters": clusters,
                "ai_analysis": ai_analysis,
                "suggestions": suggestions,
                "summary": self._generate_summary(patterns, clusters),
                "confidence": confidence,
                "analysis_quality": "ai_enhanced"
            }
            
            if kb_suggestion and kb_suggestion.get("found"):
                result["knowledge_base_match"] = kb_suggestion
            
            return result
            
        except Exception as e:
            # Fallback to rule-based analysis
            fallback = self._fallback_analysis()
            fallback["ai_error"] = str(e)
            if kb_suggestion and kb_suggestion.get("found"):
                fallback["knowledge_base_match"] = kb_suggestion
            return fallback
    
    def _prepare_enhanced_event_summary(self, patterns: Dict, clusters: List) -> str:
        """Prepare detailed event summary for enhanced AI analysis"""
        summary_parts = []
        
        # Overview statistics
        summary_parts.append("## STATISTICS OVERVIEW")
        summary_parts.append(f"- Total Events: {patterns['total_events']}")
        summary_parts.append(f"- Unique Alert Types: {patterns['unique_alerts']}")
        summary_parts.append(f"- Affected Services: {patterns['unique_services']}")
        summary_parts.append(f"- Affected Hosts: {patterns['unique_hosts']}")
        
        # Severity breakdown
        summary_parts.append("\n## SEVERITY DISTRIBUTION")
        for sev, count in patterns['severity_distribution'].items():
            pct = round(count / patterns['total_events'] * 100, 1) if patterns['total_events'] > 0 else 0
            summary_parts.append(f"- {sev.upper()}: {count} ({pct}%)")
        
        # Top alerts with details
        summary_parts.append("\n## TOP ALERTS (by frequency)")
        for i, item in enumerate(patterns['alert_frequency'][:10], 1):
            pct = round(item['count'] / patterns['total_events'] * 100, 1) if patterns['total_events'] > 0 else 0
            summary_parts.append(f"{i}. {item['alert']} - {item['count']} occurrences ({pct}%)")
        
        # Services breakdown
        summary_parts.append("\n## SERVICES WITH MOST ALERTS")
        for i, item in enumerate(patterns['service_frequency'][:10], 1):
            summary_parts.append(f"{i}. {item['service']}: {item['count']} alerts")
        
        # Host breakdown
        if patterns.get('host_frequency'):
            summary_parts.append("\n## HOSTS WITH MOST ALERTS")
            for i, item in enumerate(patterns['host_frequency'][:5], 1):
                summary_parts.append(f"{i}. {item['host']}: {item['count']} alerts")
        
        # Event clusters
        summary_parts.append("\n## EVENT CLUSTERS (related events grouped)")
        for i, cluster in enumerate(clusters[:8], 1):
            hosts_str = ", ".join(cluster.get('hosts', [])[:3])
            if len(cluster.get('hosts', [])) > 3:
                hosts_str += f" (+{len(cluster['hosts']) - 3} more)"
            summary_parts.append(f"{i}. [{cluster['severity'].upper()}] {cluster['service']} - {cluster['alert_type']}")
            summary_parts.append(f"   Count: {cluster['count']} | Hosts: {hosts_str}")
        
        # Chronological events (first 20)
        summary_parts.append("\n## CHRONOLOGICAL EVENT LOG (sample)")
        sorted_events = sorted(
            [e for e in self.events if e.get('timestamp')],
            key=lambda x: str(x.get('timestamp', ''))
        )
        for event in sorted_events[:20]:
            ts = event.get('timestamp', 'N/A')
            svc = event.get('service', 'unknown')
            alert = event.get('alert', 'unknown')
            sev = event.get('severity', 'info')
            host = event.get('host', 'N/A')
            summary_parts.append(f"[{ts}] {svc} @ {host} | {alert} ({sev})")
        
        return "\n".join(summary_parts)
    
    async def _generate_enhanced_suggestions(
        self, 
        patterns: Dict, 
        clusters: List,
        kb_suggestion: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Generate enhanced AI-powered suggestions with confidence"""
        suggestions = []
        
        # Add knowledge base suggestion if available
        if kb_suggestion and kb_suggestion.get("found"):
            suggestions.append({
                "priority": "high",
                "category": "learned_pattern",
                "title": "Known Issue Pattern Detected",
                "description": f"This alert pattern matches a previously resolved incident with {kb_suggestion.get('confidence', 0)}% confidence.",
                "action": kb_suggestion.get("resolution", "Review knowledge base entry for resolution steps"),
                "root_cause": kb_suggestion.get("root_cause"),
                "confidence": kb_suggestion.get("confidence", 0),
                "source": "knowledge_base",
                "occurrence_count": kb_suggestion.get("occurrence_count", 0)
            })
        
        # Analyze patterns and generate detailed suggestions
        severity_dist = patterns.get('severity_distribution', {})
        critical_count = severity_dist.get('critical', 0)
        warning_count = severity_dist.get('warning', 0)
        total_events = patterns.get('total_events', 0)
        
        # Critical alerts suggestion
        if critical_count > 0:
            critical_pct = round(critical_count / total_events * 100, 1) if total_events > 0 else 0
            suggestions.append({
                "priority": "critical" if critical_count > 5 else "high",
                "category": "immediate_action",
                "title": f"{critical_count} Critical Alerts Require Immediate Attention",
                "description": f"Critical alerts represent {critical_pct}% of all events. These indicate severe service degradation or outages.",
                "action": "1. Identify the service with most critical alerts\n2. Check service health and logs\n3. Initiate incident response if service is down\n4. Notify on-call team",
                "confidence": 95,
                "metrics": {"critical_count": critical_count, "critical_percentage": critical_pct}
            })
        
        # Repeated alerts (systemic issue detection)
        for alert_item in patterns.get('alert_frequency', [])[:3]:
            if alert_item['count'] >= 5:
                repetition_rate = round(alert_item['count'] / total_events * 100, 1) if total_events > 0 else 0
                suggestions.append({
                    "priority": "high" if alert_item['count'] > 10 else "medium",
                    "category": "systemic_issue",
                    "title": f"Recurring Alert: {alert_item['alert'][:60]}",
                    "description": f"This alert fired {alert_item['count']} times ({repetition_rate}% of total). Repeated alerts often indicate an underlying systemic issue rather than isolated incidents.",
                    "action": f"1. Investigate root cause of '{alert_item['alert'][:40]}...'\n2. Check for resource exhaustion or configuration issues\n3. Review recent deployments or changes\n4. Consider implementing auto-scaling or circuit breakers",
                    "confidence": min(95, 70 + alert_item['count']),
                    "metrics": {"occurrence_count": alert_item['count'], "repetition_rate": repetition_rate}
                })
        
        # Service concentration analysis
        for service_item in patterns.get('service_frequency', [])[:2]:
            concentration_pct = round(service_item['count'] / total_events * 100, 1) if total_events > 0 else 0
            if concentration_pct > 25:
                suggestions.append({
                    "priority": "high",
                    "category": "service_health",
                    "title": f"Service Hotspot: {service_item['service']}",
                    "description": f"{service_item['service']} is generating {concentration_pct}% of all alerts. This service may be the epicenter of the issue or experiencing cascading failures.",
                    "action": f"1. Check {service_item['service']} pod/container health\n2. Review recent deployments to this service\n3. Check upstream and downstream dependencies\n4. Review resource utilization (CPU, memory, connections)",
                    "confidence": min(90, 60 + concentration_pct),
                    "metrics": {"alert_count": service_item['count'], "concentration": concentration_pct}
                })
        
        # Cluster-based suggestions
        critical_clusters = [c for c in clusters if c.get('severity') == 'critical']
        for cluster in critical_clusters[:2]:
            if cluster['count'] >= 3:
                suggestions.append({
                    "priority": "critical",
                    "category": "cluster_analysis",
                    "title": f"Critical Event Cluster: {cluster['service']}",
                    "description": f"{cluster['count']} critical events related to '{cluster['alert_type'][:50]}' on {cluster['service']}. Affected hosts: {', '.join(cluster.get('hosts', [])[:3])}",
                    "action": f"1. SSH to affected hosts and check service status\n2. Review logs: kubectl logs -l app={cluster['service']} --tail=100\n3. Check resource usage: kubectl top pods -l app={cluster['service']}\n4. Consider rolling restart if service is degraded",
                    "confidence": 88,
                    "runbook_hint": f"Service: {cluster['service']}\nAffected Hosts: {', '.join(cluster.get('hosts', []))}"
                })
        
        # Time-based pattern detection
        if patterns.get('timeline'):
            timeline = patterns['timeline']
            if len(timeline) >= 5:
                # Check for burst pattern
                time_window_alerts = len([e for e in timeline[:10]])
                if time_window_alerts >= 5:
                    suggestions.append({
                        "priority": "medium",
                        "category": "pattern_detection",
                        "title": "Alert Burst Detected",
                        "description": f"Multiple alerts ({time_window_alerts}+) occurred in a short time window, suggesting a sudden incident onset. This pattern often indicates a deployment issue or infrastructure failure.",
                        "action": "1. Check for recent deployments or config changes\n2. Review infrastructure alerts (disk, network, CPU)\n3. Check for external dependency failures\n4. Review change management logs",
                        "confidence": 75
                    })
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 4))
        
        return suggestions
    
    def _calculate_analysis_confidence(
        self,
        patterns: Dict,
        clusters: List,
        kb_suggestion: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Calculate overall analysis confidence scores"""
        
        # Base confidence from data quality
        data_quality_score = 0
        total_events = patterns.get('total_events', 0)
        
        if total_events >= 100:
            data_quality_score = 95
        elif total_events >= 50:
            data_quality_score = 85
        elif total_events >= 20:
            data_quality_score = 75
        elif total_events >= 10:
            data_quality_score = 65
        else:
            data_quality_score = 50
        
        # Pattern clarity score
        pattern_score = 0
        if patterns.get('alert_frequency'):
            top_alert = patterns['alert_frequency'][0]
            if top_alert['count'] > total_events * 0.3:
                pattern_score = 90  # Clear dominant pattern
            elif top_alert['count'] > total_events * 0.15:
                pattern_score = 75
            else:
                pattern_score = 60  # Distributed alerts, harder to pinpoint
        
        # Knowledge base boost
        kb_boost = 0
        if kb_suggestion and kb_suggestion.get("found"):
            kb_boost = min(20, kb_suggestion.get("confidence", 0) / 5)
        
        # Calculate overall confidence
        overall = min(99, (data_quality_score * 0.3 + pattern_score * 0.5 + kb_boost))
        
        return {
            "overall": round(overall, 1),
            "data_quality": data_quality_score,
            "pattern_clarity": pattern_score,
            "knowledge_base_match": kb_boost > 0,
            "factors": {
                "event_count": total_events,
                "unique_patterns": patterns.get('unique_alerts', 0),
                "cluster_count": len(clusters)
            }
        }
    
    def _generate_summary(self, patterns: Dict, clusters: List) -> Dict[str, Any]:
        """Generate executive summary"""
        severity_dist = patterns.get('severity_distribution', {})
        
        # Calculate health score
        total = patterns['total_events']
        critical = severity_dist.get('critical', 0)
        warning = severity_dist.get('warning', 0)
        
        if total == 0:
            health_score = 100
        else:
            health_score = max(0, 100 - (critical * 5) - (warning * 2))
        
        # Determine overall status
        if critical > 10 or health_score < 50:
            status = "critical"
        elif critical > 0 or warning > 10:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "health_score": health_score,
            "total_events": total,
            "critical_count": critical,
            "warning_count": warning,
            "info_count": severity_dist.get('info', 0),
            "services_affected": patterns['unique_services'],
            "hosts_affected": patterns['unique_hosts'],
            "top_alert": patterns['alert_frequency'][0] if patterns['alert_frequency'] else None,
            "top_service": patterns['service_frequency'][0] if patterns['service_frequency'] else None
        }
    
    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback rule-based analysis when AI is not available"""
        patterns = self.detect_patterns()
        clusters = self.cluster_events()
        
        # Generate rule-based analysis
        analysis_parts = []
        
        analysis_parts.append("## Event Analysis Report\n")
        analysis_parts.append(f"**Total Events Analyzed:** {patterns['total_events']}")
        analysis_parts.append(f"**Unique Alert Types:** {patterns['unique_alerts']}")
        analysis_parts.append(f"**Services Affected:** {patterns['unique_services']}")
        analysis_parts.append(f"**Hosts Involved:** {patterns['unique_hosts']}\n")
        
        analysis_parts.append("### Severity Breakdown")
        for sev, count in patterns['severity_distribution'].items():
            analysis_parts.append(f"- {sev.upper()}: {count} events")
        
        analysis_parts.append("\n### Top Alerts")
        for i, item in enumerate(patterns['alert_frequency'][:5], 1):
            analysis_parts.append(f"{i}. {item['alert']} ({item['count']} occurrences)")
        
        analysis_parts.append("\n### Most Affected Services")
        for i, item in enumerate(patterns['service_frequency'][:5], 1):
            analysis_parts.append(f"{i}. {item['service']} ({item['count']} alerts)")
        
        analysis_parts.append("\n### Recommendations")
        if patterns['severity_distribution'].get('critical', 0) > 0:
            analysis_parts.append("- **URGENT**: Address critical alerts immediately")
        if patterns['alert_frequency']:
            top_alert = patterns['alert_frequency'][0]
            if top_alert['count'] > 5:
                analysis_parts.append(f"- Investigate recurring alert: {top_alert['alert']}")
        if patterns['service_frequency']:
            top_service = patterns['service_frequency'][0]
            analysis_parts.append(f"- Focus on {top_service['service']} which has the most alerts")
        
        return {
            "success": True,
            "analysis_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "patterns": patterns,
            "clusters": clusters,
            "ai_analysis": "\n".join(analysis_parts),
            "suggestions": [],
            "summary": self._generate_summary(patterns, clusters),
            "note": "AI analysis not available - showing rule-based analysis"
        }
    
    def generate_report_data(self) -> Dict[str, Any]:
        """Generate data suitable for report generation"""
        patterns = self.detect_patterns()
        clusters = self.cluster_events()
        summary = self._generate_summary(patterns, clusters)
        
        return {
            "report_type": "event_analysis",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "patterns": patterns,
            "clusters": clusters,
            "events_sample": self.events[:100],
            "charts_data": {
                "severity_pie": [
                    {"name": k, "value": v} 
                    for k, v in patterns['severity_distribution'].items()
                ],
                "alert_bar": patterns['alert_frequency'][:10],
                "service_bar": patterns['service_frequency'][:10],
                "timeline": patterns['timeline'][:30]
            }
        }


# Singleton instance
event_analyzer = EventAnalyzer()
