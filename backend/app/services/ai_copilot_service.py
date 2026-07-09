"""
FalconOps AI - AI Copilot Service
LLM-powered log analysis, RCA, and NOC assistant
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

# Lazy-guarded so the platform boots even when the optional `emergentintegrations`
# wheel isn't installed (e.g. air-gapped on-prem deployments using Ollama/OpenAI).
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    EMERGENT_LIB_AVAILABLE = True
except Exception:  # pragma: no cover — library is optional
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore
    EMERGENT_LIB_AVAILABLE = False

from ..core.database import db
from .log_analysis_service import get_log_statistics, correlate_logs

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
AI_AVAILABLE = EMERGENT_LIB_AVAILABLE and bool(EMERGENT_LLM_KEY)


# ======================== AI LOG ANALYZER ========================

async def analyze_logs_with_ai(logs: List[Dict], context: str = "") -> Dict[str, Any]:
    """Use AI to analyze log patterns and provide insights"""
    if not logs:
        return {"analysis": "No logs to analyze", "insights": [], "recommendations": []}
    
    if not EMERGENT_LLM_KEY:
        return {"error": "AI service not configured", "insights": [], "recommendations": []}
    if not EMERGENT_LIB_AVAILABLE:
        return {"error": "emergentintegrations library not installed — set provider via llm_provider_service or vendor the wheel", "insights": [], "recommendations": []}
    
    try:
        # Prepare log summary for AI
        error_logs = [l for l in logs if l.get("severity") in ["critical", "error"]][:20]
        warning_logs = [l for l in logs if l.get("severity") == "warning"][:10]
        
        log_summary = "Recent Error Logs:\n"
        for log in error_logs:
            log_summary += f"- [{log.get('service', 'unknown')}] {log.get('message', '')[:150]}\n"
        
        if warning_logs:
            log_summary += "\nRecent Warnings:\n"
            for log in warning_logs:
                log_summary += f"- [{log.get('service', 'unknown')}] {log.get('message', '')[:150]}\n"
        
        # Services affected
        services = list(set(l.get("service", "unknown") for l in logs))
        log_summary += f"\nServices affected: {', '.join(services[:10])}"
        
        # Create AI chat session
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"log-analysis-{uuid.uuid4().hex[:8]}",
            system_message="""You are an expert Site Reliability Engineer (SRE) and NOC analyst. 
Analyze the provided logs and identify:
1. Key patterns and anomalies
2. Potential root causes
3. Impact assessment
4. Recommended actions

Be concise but thorough. Focus on actionable insights."""
        ).with_model("openai", "gpt-5.2")
        
        prompt = f"""Analyze these application logs and provide insights:

{log_summary}

{f"Additional context: {context}" if context else ""}

Provide your analysis in this format:
1. SUMMARY: Brief overview of the situation
2. KEY PATTERNS: Main patterns identified
3. ROOT CAUSE HYPOTHESIS: Most likely root cause(s)
4. IMPACT: Services and users affected
5. RECOMMENDATIONS: Immediate actions to take"""

        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse response into structured format
        return {
            "analysis": response,
            "insights": extract_insights(response),
            "recommendations": extract_recommendations(response),
            "logs_analyzed": len(logs),
            "error_count": len(error_logs),
            "services_affected": services[:10],
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI log analysis failed: {e}")
        return {
            "error": str(e),
            "analysis": "AI analysis temporarily unavailable",
            "insights": [],
            "recommendations": []
        }


# ======================== AI ROOT CAUSE ANALYSIS ========================

async def perform_ai_rca(incident_data: Dict, related_logs: List[Dict] = None) -> Dict[str, Any]:
    """Perform AI-powered Root Cause Analysis"""
    if not EMERGENT_LLM_KEY:
        return {"error": "AI service not configured"}
    if not EMERGENT_LIB_AVAILABLE:
        return {"error": "emergentintegrations library not installed"}
    
    try:
        # Build context from incident and logs
        context_parts = []
        
        if incident_data:
            context_parts.append(f"Incident: {incident_data.get('title', 'Unknown')}")
            context_parts.append(f"Severity: {incident_data.get('severity', 'unknown')}")
            context_parts.append(f"Service: {incident_data.get('service', 'unknown')}")
            context_parts.append(f"Alert Count: {incident_data.get('alert_count', 0)}")
            
            if incident_data.get("description"):
                context_parts.append(f"Description: {incident_data['description']}")
        
        if related_logs:
            context_parts.append("\nRelated Logs:")
            for log in related_logs[:15]:
                context_parts.append(f"- [{log.get('timestamp', '')}] [{log.get('service', '')}] {log.get('message', '')[:150]}")
        
        # Get additional context from database
        recent_alerts = await db.alerts.find(
            {"status": "open"},
            {"_id": 0, "title": 1, "service": 1, "severity": 1}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        if recent_alerts:
            context_parts.append("\nRecent Open Alerts:")
            for alert in recent_alerts:
                context_parts.append(f"- [{alert.get('severity', '')}] {alert.get('service', '')}: {alert.get('title', '')}")
        
        context = "\n".join(context_parts)
        
        # Create AI session for RCA
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"rca-{uuid.uuid4().hex[:8]}",
            system_message="""You are an expert Site Reliability Engineer performing Root Cause Analysis.
Your goal is to identify the root cause of incidents based on logs, alerts, and system metrics.
Be analytical, consider cascading failures, and focus on the PRIMARY root cause."""
        ).with_model("openai", "gpt-5.2")
        
        prompt = f"""Perform Root Cause Analysis for this incident:

{context}

Provide your RCA in this format:
1. ROOT CAUSE: The primary root cause (be specific)
2. CONTRIBUTING FACTORS: Secondary issues that contributed
3. TIMELINE: How the incident progressed
4. IMPACT SCOPE: Full impact assessment
5. IMMEDIATE ACTIONS: Steps to resolve now
6. PREVENTION: How to prevent recurrence
7. CONFIDENCE: Your confidence level (High/Medium/Low) and why"""

        response = await chat.send_message(UserMessage(text=prompt))
        
        # Extract structured RCA
        return {
            "root_cause": extract_section(response, "ROOT CAUSE"),
            "contributing_factors": extract_section(response, "CONTRIBUTING FACTORS"),
            "timeline": extract_section(response, "TIMELINE"),
            "impact_scope": extract_section(response, "IMPACT SCOPE"),
            "immediate_actions": extract_recommendations(response),
            "prevention": extract_section(response, "PREVENTION"),
            "confidence": extract_confidence(response),
            "full_analysis": response,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI RCA failed: {e}")
        return {"error": str(e)}


# ======================== AI COPILOT CHAT ========================

class AICopilot:
    """AI-powered NOC Copilot for interactive assistance"""
    
    def __init__(self):
        self.sessions = {}
    
    async def chat(self, session_id: str, message: str, user_context: Dict = None) -> Dict[str, Any]:
        """Send a message to the AI Copilot and get a response"""
        if not EMERGENT_LLM_KEY:
            return {"error": "AI Copilot not configured", "response": "AI service is not available"}
        
        try:
            # Get or create chat session
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "chat": LlmChat(
                        api_key=EMERGENT_LLM_KEY,
                        session_id=session_id,
                        system_message="""You are FalconOps AI Copilot, an intelligent NOC assistant.
You help NOC engineers with:
- Analyzing incidents and alerts
- Identifying root causes
- Providing troubleshooting guidance
- Explaining system behavior
- Recommending actions

You have access to the monitoring platform's data. Be helpful, concise, and technical.
When discussing incidents or alerts, be specific and actionable."""
                    ).with_model("openai", "gpt-5.2"),
                    "history": [],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            
            session = self.sessions[session_id]
            
            # Enrich message with context if available
            enriched_message = message
            
            if user_context:
                # Add relevant context
                context_parts = []
                
                if user_context.get("current_page"):
                    context_parts.append(f"User is viewing: {user_context['current_page']}")
                
                if user_context.get("selected_incident"):
                    context_parts.append(f"Selected incident: {user_context['selected_incident']}")
                
                if user_context.get("selected_service"):
                    context_parts.append(f"Selected service: {user_context['selected_service']}")
                
                if context_parts:
                    enriched_message = f"[Context: {', '.join(context_parts)}]\n\nUser question: {message}"
            
            # Get real-time system context
            system_context = await self._get_system_context()
            if system_context:
                enriched_message = f"{enriched_message}\n\n[Current System Status: {system_context}]"
            
            # Send message
            response = await session["chat"].send_message(UserMessage(text=enriched_message))
            
            # Store in history
            session["history"].append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            session["history"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Keep history manageable
            if len(session["history"]) > 50:
                session["history"] = session["history"][-50:]
            
            # Store chat message in database
            await self._store_chat_message(session_id, message, response)
            
            return {
                "response": response,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI Copilot chat failed: {e}")
            return {
                "error": str(e),
                "response": "I apologize, but I encountered an error processing your request. Please try again."
            }
    
    async def _get_system_context(self) -> str:
        """Get current system context for AI"""
        try:
            parts = []

            # Alerts & incidents
            open_alerts = await db.alerts.count_documents({"status": "open"})
            critical_alerts = await db.alerts.count_documents({"status": "open", "severity": "critical"})
            open_incidents = await db.incidents.count_documents({"status": "open"})
            if open_alerts > 0:
                parts.append(f"{open_alerts} open alerts ({critical_alerts} critical)")
            if open_incidents > 0:
                parts.append(f"{open_incidents} open incidents")

            # Health rule violations
            active_violations = await db["db.health_violations"].count_documents(
                {"state": {"$in": ["active", "critical", "warning"]}}
            )
            if active_violations > 0:
                viol_docs = await db["db.health_violations"].find(
                    {"state": {"$in": ["active", "critical", "warning"]}},
                    {"_id": 0, "rule_name": 1, "severity": 1, "metric": 1, "source_name": 1, "actual_value": 1}
                ).sort("timestamp", -1).limit(10).to_list(10)
                parts.append(f"{active_violations} active health-rule violations")
                for v in viol_docs[:5]:
                    parts.append(f"  - [{v.get('severity','?').upper()}] {v.get('rule_name','')} on {v.get('source_name','')} ({v.get('metric','')}={v.get('actual_value','')})")

            # Health rules
            rules_count = await db.health_rules.count_documents({"enabled": True})
            parts.append(f"{rules_count} active health rules")

            # Servers
            servers = await db.servers.find({}, {"_id": 0, "hostname": 1, "status": 1}).to_list(20)
            if servers:
                parts.append(f"{len(servers)} monitored servers: {', '.join(s.get('hostname','') for s in servers[:5])}")

            # DB instances
            db_count = await db.db_instances.count_documents({})
            if db_count:
                parts.append(f"{db_count} monitored database instances")

            # Monitors
            monitors_up = await db.monitors.count_documents({"enabled": True, "status": "up"})
            monitors_down = await db.monitors.count_documents({"enabled": True, "status": "down"})
            if monitors_up or monitors_down:
                parts.append(f"Monitors: {monitors_up} up, {monitors_down} down")

            return "\n".join(parts) if parts else "System healthy - no active issues"
        except Exception as e:
            logger.warning(f"Failed to get system context: {e}")
            return ""
    
    async def _store_chat_message(self, session_id: str, user_message: str, ai_response: str):
        """Store chat message in database"""
        try:
            await db.copilot_chats.insert_one({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_message": user_message,
                "ai_response": ai_response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to store chat message: {e}")
    
    async def get_history(self, session_id: str) -> List[Dict]:
        """Get chat history for a session"""
        if session_id in self.sessions:
            return self.sessions[session_id]["history"]
        
        # Try to load from database
        try:
            messages = await db.copilot_chats.find(
                {"session_id": session_id},
                {"_id": 0}
            ).sort("timestamp", 1).limit(50).to_list(50)
            
            history = []
            for msg in messages:
                history.append({"role": "user", "content": msg["user_message"], "timestamp": msg["timestamp"]})
                history.append({"role": "assistant", "content": msg["ai_response"], "timestamp": msg["timestamp"]})
            
            return history
        except:
            return []
    
    def clear_session(self, session_id: str):
        """Clear a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Singleton instance
ai_copilot = AICopilot()


# ======================== HELPER FUNCTIONS ========================

def extract_insights(text: str) -> List[str]:
    """Extract key insights from AI response"""
    insights = []
    
    # Look for numbered points or bullet points
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
            # Clean up the line
            cleaned = line.lstrip('0123456789.-•) ').strip()
            if cleaned and len(cleaned) > 10:
                insights.append(cleaned[:300])
    
    return insights[:10]


def extract_recommendations(text: str) -> List[str]:
    """Extract recommendations from AI response"""
    recommendations = []
    
    # Look for action keywords
    action_keywords = ["recommend", "should", "need to", "must", "action", "fix", "resolve", "immediate"]
    
    lines = text.split('\n')
    in_recommendations = False
    
    for line in lines:
        line = line.strip()
        
        # Check if we're in recommendations section
        if "recommendation" in line.lower() or "action" in line.lower():
            in_recommendations = True
            continue
        
        if in_recommendations and line:
            if line[0].isdigit() or line.startswith('-') or line.startswith('•'):
                cleaned = line.lstrip('0123456789.-•) ').strip()
                if cleaned and len(cleaned) > 5:
                    recommendations.append(cleaned[:300])
        elif any(kw in line.lower() for kw in action_keywords):
            recommendations.append(line[:300])
    
    return list(set(recommendations))[:10]


def extract_section(text: str, section_name: str) -> str:
    """Extract a specific section from AI response"""
    lines = text.split('\n')
    in_section = False
    section_content = []
    
    for line in lines:
        if section_name.upper() in line.upper():
            in_section = True
            # Check if content is on same line
            parts = line.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                section_content.append(parts[1].strip())
            continue
        
        if in_section:
            # Check if we hit next section
            if any(header in line.upper() for header in ["ROOT CAUSE", "CONTRIBUTING", "TIMELINE", "IMPACT", "IMMEDIATE", "PREVENTION", "CONFIDENCE"]):
                if section_content:
                    break
            elif line.strip():
                section_content.append(line.strip())
    
    return " ".join(section_content)[:500] if section_content else "Not identified"


def extract_confidence(text: str) -> str:
    """Extract confidence level from AI response"""
    text_lower = text.lower()
    
    if "high confidence" in text_lower or "confidence: high" in text_lower:
        return "high"
    elif "low confidence" in text_lower or "confidence: low" in text_lower:
        return "low"
    elif "medium confidence" in text_lower or "confidence: medium" in text_lower:
        return "medium"
    
    return "medium"
