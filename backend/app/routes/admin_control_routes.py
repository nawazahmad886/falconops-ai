"""
FalconOps AI — Admin Control Console Routes
Feature flags, AI Copilot prompt editing, deny-pattern tuning, audit log,
and per-tenant URL routing configuration.

All endpoints are admin-only.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..utils.auth import require_admin
from ..services.feature_flags_service import (
    get_config, update_config, list_audit_log, get_module_catalog, get_available_models,
)
from ..services.tenant_routing_service import (
    set_tenant_routing, build_dns_instructions, list_routing_summary,
)
from ..core.database import db

router = APIRouter(prefix="/api/admin", tags=["Admin Control"])


class FeatureUpdate(BaseModel):
    modules: Optional[dict] = None
    ai_copilot: Optional[dict] = None
    deny_patterns: Optional[List[str]] = None
    limits: Optional[dict] = None


class TenantRoutingUpdate(BaseModel):
    subdomain: Optional[str] = None
    custom_domain: Optional[str] = None
    base_domain: Optional[str] = None
    routing_enabled: Optional[bool] = None


class PatternTestRequest(BaseModel):
    body: str
    patterns: Optional[List[str]] = None  # If omitted, uses live deny_patterns


class PromptTestRequest(BaseModel):
    sample_message: str
    system_prompt: Optional[str] = None  # If omitted, uses live ai_copilot.system_prompt


class RoutingSelfTestRequest(BaseModel):
    method: Optional[str] = "subdomain"  # subdomain | custom_domain | path_prefix
    platform_apex: Optional[str] = "falconops.ai"


# ──────────── Feature Flags ────────────

@router.get("/features")
async def features_get(admin_user: dict = Depends(require_admin)):
    return await get_config()


@router.patch("/features")
async def features_update(body: FeatureUpdate, admin_user: dict = Depends(require_admin)):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    return await update_config(updates, admin_user)


@router.get("/features/catalog")
async def features_catalog(admin_user: dict = Depends(require_admin)):
    """Module catalog + available AI models — used to render the admin console."""
    return {
        "modules": get_module_catalog(),
        "models": get_available_models(),
    }


@router.get("/features/audit-log")
async def features_audit(limit: int = 100, admin_user: dict = Depends(require_admin)):
    return {"entries": await list_audit_log(limit)}


# ──────────── Multi-Tenant Routing ────────────

@router.get("/tenants/routing")
async def tenants_routing_list(admin_user: dict = Depends(require_admin)):
    return {"tenants": await list_routing_summary()}


@router.patch("/tenants/{tenant_id}/routing")
async def tenant_routing_update(tenant_id: str, body: TenantRoutingUpdate,
                                admin_user: dict = Depends(require_admin)):
    payload = body.dict(exclude_unset=True)
    res = await set_tenant_routing(tenant_id, **payload)
    if res.get("error"):
        raise HTTPException(400, res["error"])
    return res


@router.get("/tenants/{tenant_id}/dns-instructions")
async def tenant_dns_instructions(tenant_id: str, platform_apex: str = "falconops.ai",
                                  admin_user: dict = Depends(require_admin)):
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return build_dns_instructions(tenant, platform_apex=platform_apex)


# ──────────── Pattern / Prompt / Routing Testers ────────────

@router.post("/test/deny-patterns")
async def test_deny_patterns(req: PatternTestRequest, admin_user: dict = Depends(require_admin)):
    """Run user-supplied body against deny patterns. Returns which patterns matched."""
    from ..services.feature_flags_service import get_deny_patterns
    patterns = req.patterns if req.patterns is not None else await get_deny_patterns()
    body_lower = (req.body or "").lower()
    matches = []
    for p in patterns:
        if not p:
            continue
        if p.lower() in body_lower:
            idx = body_lower.find(p.lower())
            ctx_start = max(0, idx - 30)
            ctx_end = min(len(req.body), idx + len(p) + 30)
            matches.append({
                "pattern": p,
                "position": idx,
                "context": req.body[ctx_start:ctx_end],
            })
    return {
        "verdict": "FAIL" if matches else "PASS",
        "patterns_tested": len(patterns),
        "matches_count": len(matches),
        "matches": matches,
        "would_mark_monitor_down": bool(matches),
    }


@router.post("/test/ai-prompt")
async def test_ai_prompt(req: PromptTestRequest, admin_user: dict = Depends(require_admin)):
    """Send sample_message through AI Copilot with the supplied (or live) system prompt."""
    import os
    import uuid as _uuid
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(503, f"emergentintegrations unavailable: {e}")

    from ..services.feature_flags_service import get_ai_copilot_config
    ai_cfg = await get_ai_copilot_config()
    sys_prompt = req.system_prompt or ai_cfg.get("system_prompt")
    model = ai_cfg.get("model") or "claude-sonnet-4-5-20250929"
    provider = ai_cfg.get("model_provider") or "anthropic"
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise HTTPException(503, "EMERGENT_LLM_KEY not configured")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"prompt-test-{_uuid.uuid4().hex[:8]}",
        system_message=sys_prompt,
    ).with_model(provider, model)

    try:
        response = await chat.send_message(UserMessage(text=req.sample_message))
    except Exception as e:
        raise HTTPException(502, f"LLM call failed: {str(e)[:300]}")

    return {
        "model": model,
        "provider": provider,
        "system_prompt_chars": len(sys_prompt or ""),
        "user_message": req.sample_message,
        "assistant_response": response,
    }


@router.post("/test/tenant-routing/{tenant_id}")
async def test_tenant_routing(tenant_id: str, req: RoutingSelfTestRequest,
                              admin_user: dict = Depends(require_admin)):
    """Self-test: backend curls /api/health internally with the configured Host header
    (or path-prefix) to verify the tenant resolution middleware actually fires.
    Returns observed X-Tenant-Slug + X-Tenant-Routing response headers."""
    import httpx
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    method = (req.method or "subdomain").lower()
    apex = req.platform_apex or "falconops.ai"

    # Internal probe URL — talk to ourselves on localhost:8001 (avoids ingress)
    internal_url = "http://localhost:8001/api/health"
    headers = {}
    test_url_label = ""
    expected_slug = tenant.get("slug") or tenant.get("subdomain")

    if method == "subdomain":
        if not tenant.get("subdomain"):
            return {"verdict": "skipped", "reason": "tenant has no subdomain configured"}
        host = f"{tenant['subdomain']}.{tenant.get('base_domain') or apex}"
        headers["Host"] = host
        test_url_label = f"https://{host}{internal_url[internal_url.index('/api'):]}"
    elif method == "custom_domain":
        if not tenant.get("custom_domain"):
            return {"verdict": "skipped", "reason": "tenant has no custom_domain configured"}
        headers["Host"] = tenant["custom_domain"]
        test_url_label = f"https://{tenant['custom_domain']}{internal_url[internal_url.index('/api'):]}"
    elif method == "path_prefix":
        slug = tenant.get("slug") or tenant.get("subdomain")
        if not slug:
            return {"verdict": "skipped", "reason": "tenant has no slug/subdomain to use as path prefix"}
        internal_url = f"http://localhost:8001/t/{slug}/api/health"
        test_url_label = f"https://{apex}/t/{slug}/api/health"
    else:
        raise HTTPException(400, f"Unknown method: {method}")

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(internal_url, headers=headers, follow_redirects=False)
        observed_slug = resp.headers.get("X-Tenant-Slug")
        observed_method = resp.headers.get("X-Tenant-Routing")
        slug_ok = (observed_slug == expected_slug)
        verdict = "ok" if slug_ok else "fail"
        diagnosis = (
            f"Tenant resolved correctly via {observed_method or method}. "
            f"Backend received Host='{headers.get('Host', '—')}'. "
            f"Slug match: {expected_slug} == {observed_slug}."
            if slug_ok else
            f"Expected slug='{expected_slug}', got '{observed_slug}'. "
            "If running behind a proxy, ensure Host header is forwarded (set X-Forwarded-Host or use ingress with `proxy_set_header Host $host`)."
        )
        return {
            "verdict": verdict,
            "test_url": test_url_label,
            "internal_url": internal_url,
            "method": method,
            "host_header": headers.get("Host"),
            "expected_slug": expected_slug,
            "observed_slug": observed_slug,
            "observed_routing_method": observed_method,
            "http_status": resp.status_code,
            "diagnosis": diagnosis,
        }
    except Exception as e:
        return {"verdict": "error", "error": str(e)[:200]}


# ──────────── Live DNS Test (after CNAME propagation) ────────────

class LiveRoutingTestRequest(BaseModel):
    base_url: str  # e.g. https://falconops.ai or https://app.falconops.ai
    method: Optional[str] = "subdomain"


@router.post("/test/tenant-routing-live/{tenant_id}")
async def test_tenant_routing_live(tenant_id: str, req: LiveRoutingTestRequest,
                                   admin_user: dict = Depends(require_admin)):
    """
    Hit the actual public URL (after CNAME propagation) to verify end-to-end DNS + ingress + middleware.
    Use this once your DNS records (from /dns-instructions) have propagated.
    """
    import httpx
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    method = (req.method or "subdomain").lower()
    base = req.base_url.rstrip("/")
    expected_slug = tenant.get("slug") or tenant.get("subdomain")

    if method == "subdomain":
        sub = tenant.get("subdomain")
        if not sub:
            return {"verdict": "skipped", "reason": "tenant has no subdomain"}
        # Replace base host with subdomain.<base_host>
        from urllib.parse import urlparse
        u = urlparse(base)
        target_url = f"{u.scheme}://{sub}.{u.netloc}/api/health"
    elif method == "custom_domain":
        if not tenant.get("custom_domain"):
            return {"verdict": "skipped", "reason": "tenant has no custom_domain"}
        target_url = f"https://{tenant['custom_domain']}/api/health"
    elif method == "path_prefix":
        slug = tenant.get("slug") or tenant.get("subdomain")
        if not slug:
            return {"verdict": "skipped", "reason": "no slug/subdomain"}
        target_url = f"{base}/t/{slug}/api/health"
    else:
        raise HTTPException(400, f"Unknown method: {method}")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(target_url)
        observed_slug = resp.headers.get("X-Tenant-Slug")
        observed_method = resp.headers.get("X-Tenant-Routing")
        slug_ok = (observed_slug == expected_slug)
        verdict = "ok" if slug_ok else "fail"
        return {
            "verdict": verdict,
            "target_url": target_url,
            "method": method,
            "expected_slug": expected_slug,
            "observed_slug": observed_slug,
            "observed_routing_method": observed_method,
            "http_status": resp.status_code,
            "diagnosis": (
                f"DNS + ingress + middleware all working. Slug resolved: {observed_slug}." if slug_ok else
                f"Failed: expected slug='{expected_slug}', got '{observed_slug}'. "
                "Check: (1) DNS CNAME has propagated (use `dig {host}` or https://dnschecker.org), "
                "(2) ingress is forwarding the Host header (NOT setting it to a fixed value), "
                "(3) tenant_routing_service.resolve_tenant_from_request matches your Host."
            ),
        }
    except httpx.ConnectError as e:
        return {"verdict": "dns_unresolved",
                "target_url": target_url,
                "diagnosis": f"Could not connect — DNS likely not yet propagated ({str(e)[:120]}). Try again in 5-15 minutes."}
    except Exception as e:
        return {"verdict": "error", "error": str(e)[:200]}


# ──────────── Vector Memory Admin Endpoints ────────────

@router.get("/vector-memory/stats")
async def vector_memory_stats(admin_user: dict = Depends(require_admin)):
    from ..services.vector_memory_service import stats
    return await stats()


@router.post("/vector-memory/prune")
async def vector_memory_prune(days: int = 90, admin_user: dict = Depends(require_admin)):
    from ..services.vector_memory_service import prune_old
    deleted = await prune_old(days=days)
    return {"deleted": deleted, "older_than_days": days}


# ──────────── LLM Provider Health + Switch ────────────

@router.get("/llm/health")
async def llm_health(admin_user: dict = Depends(require_admin)):
    from ..services.llm_provider_service import health_check
    return await health_check()


class LLMTestRequest(BaseModel):
    message: str = "Say hello in one short sentence."


@router.post("/llm/test")
async def llm_test(req: LLMTestRequest, admin_user: dict = Depends(require_admin)):
    """Send a tiny ping through the active provider — useful for verifying Ollama / API keys."""
    from ..services.llm_provider_service import chat_completion
    try:
        result = await chat_completion(
            [
                {"role": "system", "content": "You are a brief assistant."},
                {"role": "user", "content": req.message},
            ]
        )
        return result
    except Exception as e:
        raise HTTPException(502, f"LLM call failed: {str(e)[:300]}")
