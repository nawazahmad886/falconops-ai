"""
FalconOps AI - AI Crew Service
Multi-agent AI framework for incident analysis and RCA
"""
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncio

logger = logging.getLogger(__name__)

# Singleton AI service instance
_aiops_service = None


class AIOpsService:
    """AI Operations Service for incident analysis using Emergent LLM"""
    
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        self.model = "gpt-5.2"
        self.provider = "openai"
        
    async def analyze_incident(self, incident_data: Dict[str, Any], alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze incident with AI agents"""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            if not self.api_key:
                return {
                    "status": "error",
                    "message": "Emergent LLM key not configured",
                    "root_cause": None,
                    "suggested_actions": []
                }
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"incident-{incident_data.get('id', 'unknown')}-{datetime.now(timezone.utc).timestamp()}",
                system_message="""You are an expert Site Reliability Engineer and Incident Commander.
                Analyze infrastructure incidents to identify root causes and recommend remediation steps.
                Be specific, technical, and actionable in your analysis.
                Format your response as JSON with keys: root_cause, impact_analysis, suggested_actions (list), confidence_score (0-100)."""
            ).with_model(self.provider, self.model)
            
            alerts_summary = "\n".join([
                f"- [{a.get('severity', 'unknown').upper()}] {a.get('title', 'Unknown')} on {a.get('service', 'Unknown')}: {a.get('description', 'No description')}"
                for a in alerts[:20]
            ])
            
            prompt = f"""Analyze this incident:

INCIDENT: {incident_data.get('title', 'Unknown Incident')}
SEVERITY: {incident_data.get('severity', 'unknown')}
SERVICE: {incident_data.get('service', 'unknown')}
STATUS: {incident_data.get('status', 'unknown')}
CREATED: {incident_data.get('created_at', 'unknown')}

ASSOCIATED ALERTS ({len(alerts)} total):
{alerts_summary}

Provide:
1. Root cause analysis
2. Impact assessment
3. Recommended remediation steps (5-7 specific actions)
4. Confidence score for your analysis

Return as JSON."""

            response = await chat.send_message(UserMessage(text=prompt))
            
            # Try to parse JSON from response
            import json
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()
                
                result = json.loads(json_str)
                return {
                    "status": "success",
                    "root_cause": result.get("root_cause", "Unable to determine root cause"),
                    "impact_analysis": result.get("impact_analysis", ""),
                    "suggested_actions": result.get("suggested_actions", []),
                    "confidence_score": result.get("confidence_score", 50),
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    "model_used": f"{self.provider}/{self.model}"
                }
            except json.JSONDecodeError:
                # Return raw response if JSON parsing fails
                return {
                    "status": "success",
                    "root_cause": response,
                    "impact_analysis": "",
                    "suggested_actions": ["Review the AI analysis for actionable insights"],
                    "confidence_score": 50,
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    "model_used": f"{self.provider}/{self.model}"
                }
                
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "root_cause": None,
                "suggested_actions": []
            }
    
    async def correlate_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use AI to correlate alerts and identify patterns"""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            if not self.api_key or len(alerts) < 2:
                return {"correlated_groups": [], "patterns": []}
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"correlation-{datetime.now(timezone.utc).timestamp()}",
                system_message="""You are an expert at correlating infrastructure alerts.
                Identify alerts that are likely related and group them together.
                Look for temporal patterns, service dependencies, and cascading failures.
                Return JSON with: correlated_groups (list of alert groups), patterns (identified patterns)."""
            ).with_model(self.provider, self.model)
            
            alerts_text = "\n".join([
                f"[{i}] {a.get('severity', 'unknown').upper()} | {a.get('service', 'unknown')} | {a.get('title', 'unknown')} | {a.get('created_at', 'unknown')}"
                for i, a in enumerate(alerts[:50])
            ])
            
            prompt = f"""Analyze and correlate these alerts:

{alerts_text}

Group related alerts and identify patterns. Return as JSON."""

            response = await chat.send_message(UserMessage(text=prompt))
            
            import json
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()
                return json.loads(json_str)
            except Exception:
                return {"correlated_groups": [], "patterns": [], "raw_analysis": response}
                
        except Exception as e:
            logger.error(f"Alert correlation failed: {e}")
            return {"correlated_groups": [], "patterns": [], "error": str(e)}


def get_aiops_service() -> AIOpsService:
    """Get or create singleton AIOps service"""
    global _aiops_service
    if _aiops_service is None:
        _aiops_service = AIOpsService()
    return _aiops_service


def get_aiops_crew():
    """Alias for get_aiops_service for compatibility"""
    return get_aiops_service()
