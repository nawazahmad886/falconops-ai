"""
FalconOps AI - AI Root Cause Analysis Engine
Intelligent RCA using metrics, logs, and topology correlation.

Uses the unified swappable LLM provider (llm_provider_service) — works equally
well with Ollama (free, local), OpenAI / Anthropic / Gemini (BYO-key),
Emergent Universal Key, or a deterministic rule-based fallback.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from ..core.database import db
from . import llm_provider_service

logger = logging.getLogger(__name__)


class RootCauseAnalysisEngine:
    """AI-powered Root Cause Analysis Engine."""

    async def analyze_incident(
        self,
        incident_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict:
        """Perform full RCA on an incident — combines metrics, logs, topology,
        and an LLM summary via the swappable provider."""
        incident = await db.incidents_engine.find_one({"id": incident_id}, {"_id": 0})
        if not incident:
            return {"error": "Incident not found"}

        # Related alerts
        alerts: List[Dict] = []
        if incident.get("alert_ids"):
            alerts = await db.alerts_engine.find(
                {"id": {"$in": incident["alert_ids"]}}, {"_id": 0}
            ).to_list(100)

        # Time window
        incident_time = incident.get("created_at")
        if incident_time:
            try:
                start_time = (
                    datetime.fromisoformat(incident_time.replace("Z", "+00:00"))
                    - timedelta(minutes=10)
                ).isoformat()
            except Exception:
                start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        else:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        end_time = datetime.now(timezone.utc).isoformat()

        context = await self._gather_rca_context(
            incident=incident,
            alerts=alerts,
            start_time=start_time,
            end_time=end_time,
            tenant_id=tenant_id,
        )

        # Always start from a deterministic rule-based RCA — guarantees a result
        # even when every LLM provider is down.
        base = self._rule_based_rca(incident, alerts, context)
        analysis = await self._enrich_with_llm(incident, alerts, context, base)

        rca_doc = {
            "incident_id": incident_id,
            "analysis": analysis,
            "context_summary": {
                "alerts_count": len(alerts),
                "metrics_analyzed": len(context.get("metrics", [])),
                "logs_analyzed": len(context.get("logs", [])),
                "services_involved": len(context.get("topology", {}).get("services", [])),
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.rca_results.insert_one(rca_doc)
        rca_doc.pop("_id", None)

        await db.incidents_engine.update_one(
            {"id": incident_id},
            {"$set": {
                "root_cause": analysis.get("root_cause"),
                "root_cause_analysis": analysis,
            }},
        )

        return {"incident_id": incident_id, "rca": analysis, "context": context}

    async def _gather_rca_context(
        self,
        incident: Dict,
        alerts: List[Dict],
        start_time: str,
        end_time: str,
        tenant_id: Optional[str],
    ) -> Dict:
        context: Dict = {
            "metrics": [],
            "logs": [],
            "topology": {},
            "recent_changes": [],
            "baseline_deviations": [],
        }

        affected_hosts = set(incident.get("affected_hosts", []))
        affected_services = set(incident.get("affected_services", []))

        for alert in alerts:
            if alert.get("tags", {}).get("host"):
                affected_hosts.add(alert["tags"]["host"])
            if alert.get("entity_name"):
                affected_services.add(alert["entity_name"])

        for host in list(affected_hosts)[:5]:
            metrics = await db.metrics_timeseries.find(
                {"tags.host": host, "timestamp": {"$gte": start_time, "$lte": end_time}},
                {"_id": 0, "name": 1, "value": 1, "timestamp": 1, "anomaly": 1},
            ).sort("timestamp", -1).limit(50).to_list(50)
            context["metrics"].extend(metrics)

        log_query: Dict = {
            "timestamp": {"$gte": start_time, "$lte": end_time},
            "level": {"$in": ["error", "fatal", "warn"]},
        }
        if affected_hosts:
            log_query["host"] = {"$in": list(affected_hosts)}
        if affected_services:
            log_query["service"] = {"$in": list(affected_services)}

        context["logs"] = await db.logs.find(
            log_query,
            {"_id": 0, "message": 1, "level": 1, "timestamp": 1, "service": 1, "host": 1},
        ).sort("timestamp", -1).limit(30).to_list(30)

        if affected_services:
            services = await db.topology_nodes.find(
                {"name": {"$in": list(affected_services)}}, {"_id": 0}
            ).to_list(20)
            service_ids = [s.get("id") for s in services if s.get("id")]
            connections = await db.topology_edges.find(
                {"$or": [
                    {"source_id": {"$in": service_ids}},
                    {"target_id": {"$in": service_ids}},
                ]},
                {"_id": 0},
            ).to_list(50)
            context["topology"] = {"services": services, "connections": connections}

        context["baseline_deviations"] = [
            m for m in context["metrics"] if (m.get("anomaly") or {}).get("is_anomaly")
        ][:10]
        return context

    async def _enrich_with_llm(
        self,
        incident: Dict,
        alerts: List[Dict],
        context: Dict,
        base: Dict,
    ) -> Dict:
        """Run a swappable-provider LLM call on top of the rule-based RCA.
        Falls back gracefully to the rule-based output if the LLM is unavailable."""
        prompt = self._build_rca_prompt(incident, alerts, context, base)
        try:
            resp = await llm_provider_service.chat_completion(
                [
                    {"role": "system", "content": (
                        "You are a Senior Site Reliability Engineer producing an incident "
                        "root-cause analysis. Be specific, technical, and evidence-based. "
                        "Reference specific metrics, logs, services, and timestamps when present."
                    )},
                    {"role": "user", "content": prompt},
                ],
                session_id=f"rca-{incident.get('id', 'unknown')}",
            )
            text = (resp.get("response") or "").strip()
            provider = resp.get("provider", "rule_based")
            model = resp.get("model")
            used_llm = provider not in ("rule_based", None) and len(text) >= 60
        except Exception as e:
            logger.warning("RCA LLM enrichment failed: %s", e)
            text, provider, model, used_llm = "", "rule_based", None, False

        if used_llm:
            return {
                **base,
                "root_cause": self._extract_section(text, "ROOT CAUSE") or base["root_cause"],
                "event_chain": self._extract_list(text, "EVENT CHAIN") or base["event_chain"],
                "impact": self._extract_section(text, "IMPACT") or base["impact"],
                "remediation": self._extract_list(text, "REMEDIATION") or base["remediation"],
                "prevention": self._extract_list(text, "PREVENTION") or base["prevention"],
                "full_analysis": text,
                "analysis_type": "ai_powered",
                "provider": provider,
                "model": model,
                "confidence": "high" if len(context.get("logs", [])) > 5 else "medium",
            }
        return {**base, "provider": "rule_based", "model": None}

    def _rule_based_rca(
        self,
        incident: Dict,
        alerts: List[Dict],
        context: Dict,
    ) -> Dict:
        """Deterministic RCA from signal pattern matching."""
        root_cause = "Unknown"
        event_chain: List[str] = []
        remediation: List[str] = []

        alert_metrics = [a.get("metric_name", "") for a in alerts]

        has_cpu = any("cpu" in m.lower() for m in alert_metrics)
        has_mem = any("memory" in m.lower() for m in alert_metrics)
        has_disk = any("disk" in m.lower() for m in alert_metrics)
        has_latency = any(("latency" in m.lower() or "response" in m.lower()) for m in alert_metrics)
        has_error = any("error" in m.lower() for m in alert_metrics)

        error_logs = context.get("logs", [])
        error_messages = [log.get("message", "") for log in error_logs if log.get("level") == "error"]

        if has_cpu and has_latency:
            root_cause = "CPU saturation causing service latency degradation"
            event_chain = [
                "High CPU utilization detected on one or more hosts",
                "Service response times increased due to resource contention",
                "Latency alerts triggered as SLA thresholds were breached",
            ]
            remediation = [
                "Identify high-CPU processes using 'top' or 'htop'",
                "Scale horizontally by adding more instances",
                "Review application code for CPU-intensive operations",
                "Consider implementing request throttling",
            ]
        elif has_mem:
            root_cause = "Memory exhaustion or memory leak"
            event_chain = [
                "Memory usage steadily increased over time",
                "Application performance degraded as memory became scarce",
                "Potential OOM conditions or swap thrashing occurred",
            ]
            remediation = [
                "Check for memory leaks in application code",
                "Review memory limits and allocations",
                "Restart affected services if immediate relief needed",
                "Analyze heap dumps to identify memory consumers",
            ]
        elif has_disk:
            root_cause = "Disk space exhaustion or I/O bottleneck"
            event_chain = [
                "Disk usage exceeded threshold or I/O latency increased",
                "Services experienced write failures or slowdowns",
                "Cascading failures as dependent services were affected",
            ]
            remediation = [
                "Clean up old logs and temporary files",
                "Expand disk capacity or add storage",
                "Implement log rotation and retention policies",
                "Move large files to object storage",
            ]
        elif has_error:
            root_cause = "Application errors causing service failures"
            if error_messages:
                root_cause += f": {error_messages[0][:100]}"
            event_chain = [
                "Error rate increased beyond normal levels",
                "Users experienced failures or degraded functionality",
                "Alerts triggered based on error rate thresholds",
            ]
            remediation = [
                "Review application logs for error details",
                "Check for recent deployments or configuration changes",
                "Verify dependent service health",
                "Roll back recent changes if necessary",
            ]
        elif has_latency:
            root_cause = "Service latency degradation"
            event_chain = [
                "Response times increased beyond acceptable thresholds",
                "User experience degraded",
                "SLA breaches occurred",
            ]
            remediation = [
                "Check database query performance",
                "Review network latency between services",
                "Look for resource contention",
                "Verify external dependency health",
            ]
        else:
            root_cause = f"Multiple issues detected across {len(alerts)} alerts"
            event_chain = [
                f"{len(alerts)} alerts triggered across affected services",
                "Multiple metrics deviated from normal baselines",
                "Incident created from correlated alerts",
            ]
            remediation = [
                "Review all alert details individually",
                "Check recent changes and deployments",
                "Verify service health across the topology",
                "Engage relevant teams for investigation",
            ]

        if error_logs:
            event_chain.insert(0, f"First error detected: {error_logs[-1].get('message', '')[:80]}")

        anomalies = context.get("baseline_deviations", [])
        for anomaly in anomalies[:3]:
            event_chain.append(f"Anomaly: {anomaly.get('name')} = {anomaly.get('value')}")

        return {
            "root_cause": root_cause,
            "event_chain": event_chain,
            "impact": (
                f"Affected {len(incident.get('affected_services', []))} services "
                f"and {len(incident.get('affected_hosts', []))} hosts"
            ),
            "remediation": remediation,
            "prevention": [
                "Set up proactive monitoring for early warning",
                "Implement auto-scaling for resource-based issues",
                "Add circuit breakers for dependent services",
                "Review and update alerting thresholds",
            ],
            "analysis_type": "rule_based",
            "confidence": "medium",
        }

    def _build_rca_prompt(self, incident: Dict, alerts: List[Dict], context: Dict, base: Dict) -> str:
        parts: List[str] = []
        parts.append(
            "INCIDENT DETAILS:\n"
            f"- Title: {incident.get('title')}\n"
            f"- Severity: {incident.get('severity')}\n"
            f"- Status: {incident.get('status')}\n"
            f"- Created: {incident.get('created_at')}\n"
            f"- Affected Services: {', '.join(incident.get('affected_services', [])[:5])}\n"
            f"- Affected Hosts: {', '.join(incident.get('affected_hosts', [])[:5])}\n"
        )
        if alerts:
            parts.append("\nRELATED ALERTS:")
            for alert in alerts[:10]:
                parts.append(
                    f"  - [{alert.get('severity')}] {alert.get('title')}: "
                    f"{alert.get('metric_name')}={alert.get('metric_value')}"
                )
        if context.get("logs"):
            parts.append("\nERROR/WARNING LOGS:")
            for log in context["logs"][:10]:
                parts.append(
                    f"  [{log.get('level')}] {log.get('service')}: {log.get('message', '')[:100]}"
                )
        if context.get("baseline_deviations"):
            parts.append("\nANOMALOUS METRICS:")
            for anomaly in context["baseline_deviations"][:5]:
                parts.append(
                    f"  - {anomaly.get('name')}: value={anomaly.get('value')}, "
                    f"z-score={(anomaly.get('anomaly') or {}).get('z_score')}"
                )
        if context.get("topology", {}).get("services"):
            parts.append("\nSERVICE TOPOLOGY:")
            for svc in context["topology"]["services"][:5]:
                parts.append(
                    f"  - {svc.get('name')} ({svc.get('type')}) - Status: {svc.get('status')}"
                )
        parts.append(
            "\nDETERMINISTIC HYPOTHESIS (refine, don't repeat):\n"
            f"  ROOT CAUSE: {base.get('root_cause')}\n"
            f"  EVENT CHAIN: {' → '.join(base.get('event_chain') or [])}\n"
        )
        parts.append(
            "\nProduce a structured response with EXACTLY these labeled sections:\n"
            "ROOT CAUSE: <one specific sentence>\n"
            "EVENT CHAIN:\n"
            "- <step 1>\n- <step 2>\n- <step 3>\n"
            "IMPACT: <business + technical impact>\n"
            "REMEDIATION:\n"
            "- <step 1>\n- <step 2>\n- <step 3>\n"
            "PREVENTION:\n"
            "- <step 1>\n- <step 2>\n- <step 3>\n"
        )
        return "\n".join(parts)

    def _extract_section(self, text: str, section: str) -> str:
        """Extract one labeled section using regex header matching.

        A header is the label at line start, optionally with '#', '*', '-' prefix,
        and **must be followed by ':' or end-of-line** (so we don't match e.g.
        the word 'ROOT CAUSE' inside a title like 'Root Cause Analysis').
        """
        if not text:
            return ""
        import re as _re
        all_sections = ["ROOT CAUSE", "EVENT CHAIN", "IMPACT", "REMEDIATION", "PREVENTION"]
        sec_u = section.upper()
        padded = "\n" + text

        def _header_match(lbl: str):
            # Header must be at line start, optionally prefixed by '#', '*', '-', whitespace,
            # AND followed by ':' or end-of-line (with optional trailing '**' for markdown).
            pat = rf"(?im)^[\s#*\-•]*{_re.escape(lbl)}\**\s*(?::|$)"
            return _re.search(pat, padded)

        head = _header_match(section)
        if not head:
            return ""
        head_end = head.end()
        end = len(padded)
        for nxt in all_sections:
            if nxt == sec_u:
                continue
            m = _header_match(nxt)
            if m and m.start() >= head_end and m.start() < end:
                end = m.start()
        chunk = padded[head_end:end].strip()
        chunk = chunk.lstrip("#").lstrip("*").strip()
        first_para = chunk.split("\n\n")[0].strip()
        return first_para[:600]

    def _extract_list(self, text: str, section: str) -> List[str]:
        body = self._extract_section(text, section)
        if not body:
            return []
        import re as _re
        items: List[str] = []
        # Strip only the leading bullet marker (-, •, *, or "N." / "N)") plus optional whitespace,
        # but NEVER digits inside content (e.g. timestamps like 11:36:33Z).
        bullet_re = _re.compile(r"^([-•*]+\s*|\d{1,3}[.)]\s+)")
        for raw in body.split("\n"):
            line = raw.strip()
            if not line:
                continue
            stripped = bullet_re.sub("", line).strip()
            # Strip leading/trailing markdown emphasis
            stripped = stripped.strip("*").strip()
            if len(stripped) >= 8:
                items.append(stripped)
        return items[:6]


# Singleton
rca_engine = RootCauseAnalysisEngine()
