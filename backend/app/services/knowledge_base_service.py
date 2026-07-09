"""
FalconOps AI - Self-Learning Knowledge Base Service
Stores incident patterns and learns from resolutions
"""
import os
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import Counter
import hashlib

from ..core.database import db

# AI Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


class KnowledgeBaseService:
    """Self-learning incident knowledge base"""
    
    # Similarity thresholds
    HIGH_SIMILARITY = 0.85
    MEDIUM_SIMILARITY = 0.60
    LOW_SIMILARITY = 0.40
    
    def __init__(self):
        pass
    
    def _generate_pattern_hash(self, alerts: List[str]) -> str:
        """Generate a hash for alert patterns"""
        sorted_alerts = sorted([a.lower().strip() for a in alerts])
        pattern_str = "|".join(sorted_alerts)
        return hashlib.sha256(pattern_str.encode()).hexdigest()[:16]
    
    def _calculate_similarity(self, alerts1: List[str], alerts2: List[str]) -> float:
        """Calculate Jaccard similarity between two alert sets"""
        if not alerts1 or not alerts2:
            return 0.0
        
        set1 = set([a.lower().strip() for a in alerts1])
        set2 = set([a.lower().strip() for a in alerts2])
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    async def store_incident(
        self,
        alerts: List[str],
        services: List[str],
        root_cause: str,
        resolution: str,
        user_id: str,
        severity: str = "warning",
        confidence: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Store an incident pattern in the knowledge base"""
        
        pattern_hash = self._generate_pattern_hash(alerts)
        
        # Check if similar pattern exists
        existing = await db.incident_knowledge.find_one({
            "pattern_hash": pattern_hash
        })
        
        incident_record = {
            "id": str(uuid.uuid4()),
            "pattern_hash": pattern_hash,
            "alerts": alerts,
            "services": services,
            "root_cause": root_cause,
            "resolution": resolution,
            "severity": severity,
            "confidence_score": confidence,
            "occurrence_count": 1,
            "success_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user_id,
            "metadata": metadata or {},
            "feedback_scores": [],
            "resolution_times": [],
            "is_verified": False
        }
        
        if existing:
            # Update existing pattern
            await db.incident_knowledge.update_one(
                {"pattern_hash": pattern_hash},
                {
                    "$inc": {"occurrence_count": 1},
                    "$set": {
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "root_cause": root_cause,
                        "resolution": resolution,
                        "confidence_score": min(1.0, existing.get("confidence_score", 0.5) + 0.05)
                    },
                    "$push": {
                        "resolution_history": {
                            "resolution": resolution,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "user_id": user_id
                        }
                    }
                }
            )
            return {"success": True, "updated": True, "pattern_hash": pattern_hash}
        else:
            await db.incident_knowledge.insert_one(incident_record)
            return {"success": True, "created": True, "incident_id": incident_record["id"]}
    
    async def find_similar_incidents(
        self,
        alerts: List[str],
        services: Optional[List[str]] = None,
        min_similarity: float = 0.4,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar incidents from knowledge base"""
        
        # Get all knowledge base entries
        knowledge_entries = await db.incident_knowledge.find(
            {},
            {"_id": 0}
        ).to_list(length=1000)
        
        similar_incidents = []
        
        for entry in knowledge_entries:
            # Calculate alert similarity
            alert_similarity = self._calculate_similarity(alerts, entry.get("alerts", []))
            
            # Calculate service similarity (if provided)
            service_similarity = 0.0
            if services and entry.get("services"):
                service_similarity = self._calculate_similarity(services, entry.get("services", []))
            
            # Combined similarity (weighted)
            combined_similarity = alert_similarity * 0.7 + service_similarity * 0.3 if services else alert_similarity
            
            if combined_similarity >= min_similarity:
                similar_incidents.append({
                    **entry,
                    "similarity_score": round(combined_similarity, 3),
                    "alert_match": round(alert_similarity, 3),
                    "service_match": round(service_similarity, 3) if services else None
                })
        
        # Sort by similarity and occurrence count
        similar_incidents.sort(
            key=lambda x: (x["similarity_score"], x.get("occurrence_count", 0)),
            reverse=True
        )
        
        return similar_incidents[:limit]
    
    async def get_instant_suggestion(
        self,
        alerts: List[str],
        services: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get immediate suggestion based on learned patterns"""
        
        similar = await self.find_similar_incidents(alerts, services, min_similarity=self.MEDIUM_SIMILARITY, limit=1)
        
        if not similar:
            return None
        
        best_match = similar[0]
        
        # Calculate confidence based on similarity and occurrence
        base_confidence = best_match["similarity_score"] * 100
        occurrence_bonus = min(20, best_match.get("occurrence_count", 1) * 2)
        success_bonus = min(15, best_match.get("success_count", 0) * 3)
        
        confidence = min(99, base_confidence + occurrence_bonus + success_bonus)
        
        return {
            "found": True,
            "confidence": round(confidence, 1),
            "root_cause": best_match.get("root_cause"),
            "resolution": best_match.get("resolution"),
            "similarity": best_match.get("similarity_score"),
            "occurrence_count": best_match.get("occurrence_count", 1),
            "success_count": best_match.get("success_count", 0),
            "pattern_id": best_match.get("id"),
            "source": "knowledge_base"
        }
    
    async def record_feedback(
        self,
        pattern_id: str,
        helpful: bool,
        user_id: str,
        resolution_time_minutes: Optional[int] = None,
        feedback_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record feedback for a suggestion"""
        
        update_ops = {
            "$push": {
                "feedback_scores": {
                    "helpful": helpful,
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": feedback_notes
                }
            },
            "$set": {
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if helpful:
            update_ops["$inc"] = {"success_count": 1}
        
        if resolution_time_minutes:
            update_ops["$push"]["resolution_times"] = resolution_time_minutes
        
        result = await db.incident_knowledge.update_one(
            {"id": pattern_id},
            update_ops
        )
        
        return {"success": result.modified_count > 0}
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        
        total_patterns = await db.incident_knowledge.count_documents({})
        
        # Get aggregate stats
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_occurrences": {"$sum": "$occurrence_count"},
                    "total_successes": {"$sum": "$success_count"},
                    "avg_confidence": {"$avg": "$confidence_score"},
                    "verified_count": {"$sum": {"$cond": ["$is_verified", 1, 0]}}
                }
            }
        ]
        
        stats_result = await db.incident_knowledge.aggregate(pipeline).to_list(length=1)
        
        stats = stats_result[0] if stats_result else {}
        
        # Get top patterns
        top_patterns = await db.incident_knowledge.find(
            {},
            {"_id": 0, "id": 1, "root_cause": 1, "occurrence_count": 1, "success_count": 1}
        ).sort("occurrence_count", -1).limit(10).to_list(length=10)
        
        return {
            "total_patterns": total_patterns,
            "total_occurrences": stats.get("total_occurrences", 0),
            "total_successes": stats.get("total_successes", 0),
            "verified_patterns": stats.get("verified_count", 0),
            "avg_confidence": round(stats.get("avg_confidence", 0) * 100, 1),
            "top_patterns": top_patterns,
            "learning_score": self._calculate_learning_score(stats)
        }
    
    def _calculate_learning_score(self, stats: Dict) -> int:
        """Calculate overall learning effectiveness score"""
        if not stats:
            return 0
        
        occurrences = stats.get("total_occurrences", 0)
        successes = stats.get("total_successes", 0)
        
        if occurrences == 0:
            return 0
        
        success_rate = successes / occurrences
        volume_bonus = min(30, occurrences // 10)
        
        return min(100, int(success_rate * 70 + volume_bonus))
    
    async def export_knowledge(self) -> List[Dict[str, Any]]:
        """Export entire knowledge base"""
        return await db.incident_knowledge.find(
            {},
            {"_id": 0}
        ).to_list(length=10000)
    
    async def import_knowledge(self, data: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """Import knowledge base entries"""
        imported = 0
        updated = 0
        
        for entry in data:
            result = await self.store_incident(
                alerts=entry.get("alerts", []),
                services=entry.get("services", []),
                root_cause=entry.get("root_cause", ""),
                resolution=entry.get("resolution", ""),
                user_id=user_id,
                severity=entry.get("severity", "warning"),
                confidence=entry.get("confidence_score", 0.5)
            )
            
            if result.get("created"):
                imported += 1
            elif result.get("updated"):
                updated += 1
        
        return {"imported": imported, "updated": updated}


# Singleton instance
knowledge_base = KnowledgeBaseService()
