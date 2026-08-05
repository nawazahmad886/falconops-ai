"""
Agent memory — a thin adapter over the EXISTING vector_memory_service, not a
new memory store. STM/LTM/incident memory are just new `kind` values on the
same db.vector_memory collection every other vector-memory caller already
uses (chat_message/ai_insight/incident/runbook) — reusing the same
embedding pipeline, the same cosine-similarity search, the same tenant
scoping. This satisfies the Agent Builder spec's own "reuse existing
memory, no duplicate system" instruction literally, not just in spirit.
"""
from typing import Any, Dict, List, Optional

from .. import vector_memory_service

STM_KIND = "agent_stm"
LTM_KIND = "agent_ltm"
INCIDENT_MEMORY_KIND = "agent_incident_memory"


async def remember_stm(agent_execution_id: str, text: str, tenant_id: Optional[str] = None) -> Optional[str]:
    return await vector_memory_service.remember(
        text=text, kind=STM_KIND, tenant_id=tenant_id, source_id=agent_execution_id,
        metadata={"agent_execution_id": agent_execution_id},
    )


async def remember_ltm(agent_id: str, text: str, tenant_id: Optional[str] = None, metadata: Optional[Dict] = None) -> Optional[str]:
    return await vector_memory_service.remember(
        text=text, kind=LTM_KIND, tenant_id=tenant_id, source_id=None,
        metadata={"agent_id": agent_id, **(metadata or {})},
    )


async def remember_incident(incident_id: str, text: str, tenant_id: Optional[str] = None) -> Optional[str]:
    return await vector_memory_service.remember(
        text=text, kind=INCIDENT_MEMORY_KIND, tenant_id=tenant_id, source_id=incident_id,
        metadata={"incident_id": incident_id},
    )


async def search_ltm(agent_id: str, query_text: str, top_k: int = 5, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return await vector_memory_service.search(query_text, top_k=top_k, tenant_id=tenant_id, kinds=[LTM_KIND])


async def search_incident_memory(query_text: str, top_k: int = 5, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return await vector_memory_service.search(query_text, top_k=top_k, tenant_id=tenant_id, kinds=[INCIDENT_MEMORY_KIND])


__all__ = [
    "STM_KIND", "LTM_KIND", "INCIDENT_MEMORY_KIND",
    "remember_stm", "remember_ltm", "remember_incident", "search_ltm", "search_incident_memory",
]
