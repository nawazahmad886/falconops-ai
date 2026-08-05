"""
LLM pricing registry — Mongo-backed, admin-editable, replacing the
previously hardcoded USD_PER_1K_TOKENS dict in ai_monitoring_service.py.

seed_from_defaults() migrates that dict's exact values on first boot so
upgrading an existing deployment produces identical cost numbers on day
one — pricing only changes going forward when an admin edits a rate (or a
future seed adds a new model), never silently on upgrade.

Split input/output/cache-read rates throughout — a blended rate hides that
output tokens are typically priced several times higher than input, and
cache-read tokens are typically priced far below either.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Migrated verbatim from ai_monitoring_service.USD_PER_1K_TOKENS — the exact
# values already in production use, now the seed data for the Mongo registry
# rather than the live source of truth.
DEFAULT_RATES = [
    {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "input_price_per_1k": 0.0030, "output_price_per_1k": 0.0150, "cache_read_price_per_1k": None},
    {"provider": "anthropic", "model": "claude-sonnet-4-5", "input_price_per_1k": 0.0030, "output_price_per_1k": 0.0150, "cache_read_price_per_1k": None},
    {"provider": "openai", "model": "gpt-4o", "input_price_per_1k": 0.0025, "output_price_per_1k": 0.0100, "cache_read_price_per_1k": 0.00125},
    {"provider": "openai", "model": "gpt-4o-mini", "input_price_per_1k": 0.00015, "output_price_per_1k": 0.00060, "cache_read_price_per_1k": 0.000075},
    {"provider": "gemini", "model": "gemini-2.5-pro", "input_price_per_1k": 0.00125, "output_price_per_1k": 0.00500, "cache_read_price_per_1k": None},
    {"provider": "gemini", "model": "gemini-1.5-flash", "input_price_per_1k": 0.000075, "output_price_per_1k": 0.00030, "cache_read_price_per_1k": None},
    {"provider": "ollama", "model": "ollama", "input_price_per_1k": 0.0, "output_price_per_1k": 0.0, "cache_read_price_per_1k": None},
    {"provider": "rule_based", "model": "rule_based", "input_price_per_1k": 0.0, "output_price_per_1k": 0.0, "cache_read_price_per_1k": None},
]


async def _ensure_indexes() -> None:
    from .core.database import db
    try:
        await db.llm_pricing.create_index([("provider", 1), ("model", 1)], unique=True)
    except Exception as e:
        logger.warning(f"llm_pricing index setup failed: {e}")


async def seed_from_defaults() -> None:
    """Idempotent — same pattern as every other seed this session
    (rbac_service.init_default_roles, agent_definition_service.seed_rased_
    wrapper_agents, templates_seed.seed_built_in_templates)."""
    await _ensure_indexes()
    from .core.database import db
    now = datetime.now(timezone.utc).isoformat()
    for rate in DEFAULT_RATES:
        existing = await db.llm_pricing.find_one({"provider": rate["provider"], "model": rate["model"]})
        if existing:
            continue
        await db.llm_pricing.insert_one({
            **rate, "currency": "USD", "effective_from": now,
            "updated_by": "system:seed", "updated_at": now,
        })
    logger.info("llm_pricing: default rates seeded")


async def get_rate(provider: str, model: str) -> Optional[Dict[str, Any]]:
    from .core.database import db
    return await db.llm_pricing.find_one({"provider": provider, "model": model}, {"_id": 0})


async def list_rates() -> List[Dict[str, Any]]:
    from .core.database import db
    return await db.llm_pricing.find({}, {"_id": 0}).sort([("provider", 1), ("model", 1)]).to_list(500)


async def set_rate(
    provider: str, model: str, *, input_price_per_1k: float, output_price_per_1k: float,
    cache_read_price_per_1k: Optional[float] = None, currency: str = "USD", updated_by: str = "unknown",
) -> Dict[str, Any]:
    await _ensure_indexes()
    from .core.database import db
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.llm_pricing.find_one({"provider": provider, "model": model}, {"_id": 0})
    doc = {
        "provider": provider, "model": model,
        "input_price_per_1k": input_price_per_1k, "output_price_per_1k": output_price_per_1k,
        "cache_read_price_per_1k": cache_read_price_per_1k, "currency": currency,
        "effective_from": existing.get("effective_from") if existing else now,
        "updated_by": updated_by, "updated_at": now,
    }
    await db.llm_pricing.update_one({"provider": provider, "model": model}, {"$set": doc}, upsert=True)
    return doc


async def delete_rate(provider: str, model: str) -> Dict[str, Any]:
    from .core.database import db
    result = await db.llm_pricing.delete_one({"provider": provider, "model": model})
    if result.deleted_count == 0:
        return {"error": "rate not found"}
    return {"provider": provider, "model": model, "deleted": True}


async def compute_cost(provider: str, model: str, input_tokens: int, output_tokens: int,
                        cached_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Real per-model input/output(/cache) pricing, or an honest unavailable
    reason if the model isn't in the registry — never a fabricated default
    rate for an unrecognized model. Looks up by (provider, model) first,
    falling back to a model-only match for backward compat with the old
    dict's model-only keys (it never stored provider)."""
    rate = await get_rate(provider, model)
    if rate is None:
        from .core.database import db
        rate = await db.llm_pricing.find_one({"model": model}, {"_id": 0})
    if rate is None:
        return {"total_cost_usd": None, "input_cost_usd": None, "output_cost_usd": None,
                "cache_savings_usd": None, "reason": f"no pricing configured for provider={provider!r} model={model!r}"}

    input_cost = round(input_tokens * rate["input_price_per_1k"] / 1000.0, 6)
    output_cost = round(output_tokens * rate["output_price_per_1k"] / 1000.0, 6)
    total = round(input_cost + output_cost, 6)

    cache_savings = None
    cache_rate = rate.get("cache_read_price_per_1k")
    if cached_tokens is not None and cache_rate is not None:
        # Savings = what those tokens would have cost at the full input rate,
        # minus what they actually cost at the cache-read rate. Requires both
        # a real cache-token reading AND a configured cache rate — absent
        # either, this stays None rather than a guess.
        full_price = cached_tokens * rate["input_price_per_1k"] / 1000.0
        cache_price = cached_tokens * cache_rate / 1000.0
        cache_savings = round(max(0.0, full_price - cache_price), 6)

    return {"total_cost_usd": total, "input_cost_usd": input_cost, "output_cost_usd": output_cost,
            "cache_savings_usd": cache_savings, "reason": None}


__all__ = ["seed_from_defaults", "get_rate", "list_rates", "set_rate", "delete_rate", "compute_cost", "DEFAULT_RATES"]
