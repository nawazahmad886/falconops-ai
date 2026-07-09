"""
FalconOps AI — Feature Flag & Platform Configuration Service
Provides admin-controllable runtime toggles, AI-Copilot system prompt editing,
deny-pattern customization, model selection, and a full audit log of changes.

Storage:
  - feature_flags: a single document with id="global" containing the live config
  - feature_audit_log: append-only log of every change (who, when, from→to)

The frontend Admin Console reads/writes these collections via /api/admin/features.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from ..core.database import db
from .assertion_engine import DEFAULT_BODY_DENY_PATTERNS

logger = logging.getLogger(__name__)

DEFAULT_AI_SYSTEM_PROMPT = """You are FalconOps Copilot — an AI SRE assistant embedded inside the
FalconOps AIOps platform. You help operators create monitors, triage incidents, and
fix availability issues by proposing structured actions that a human admin must approve
before they execute.

## Your capabilities (the only actions you can propose):
1. `create_url_monitor` — create a new HTTP/HTTPS uptime monitor
2. `toggle_monitor` — enable/disable an existing monitor
3. `delete_monitor` — remove a monitor
4. `update_monitor` — modify interval, timeout, assertions, etc.
5. `run_check_now` — trigger an immediate check of an existing monitor

## Output contract
When the user asks for an operational change, reply in TWO parts:
1. A short natural-language explanation of what you'll do and why (under 80 words).
2. A fenced JSON block (```json ... ```) with the exact action proposal.

## Rules
- If the user is just asking a question, reply naturally WITHOUT a JSON block.
- Always propose strong assertions to avoid HTTP-200-with-error-body false-positives.
- Never invent monitor IDs. If the user refers to an existing monitor, ask for the ID or name.
- Default region: us-east. Default interval: 60 seconds. Default timeout: 10 seconds.
- Be crisp, SRE-tone, confident. No fluff.
"""

# Module catalog — ordered grouping for the UI
MODULE_CATALOG: List[Dict] = [
    {"key": "ai_copilot",            "label": "AI Copilot Chat",            "category": "AI",        "default": True},
    {"key": "ai_agents",             "label": "AI Multi-Agent System",     "category": "AI",        "default": True},
    {"key": "auto_healing",          "label": "K8s Auto-Healing",          "category": "AIOps",     "default": True},
    {"key": "auto_correlation",      "label": "Alert Auto-Correlation",     "category": "AIOps",     "default": True},
    {"key": "uptime_monitoring",     "label": "URL / Uptime Monitoring",    "category": "Monitoring", "default": True},
    {"key": "synthetic_monitoring",  "label": "Synthetic Monitoring",       "category": "Monitoring", "default": True},
    {"key": "ssl_monitoring",        "label": "SSL Certificate Monitoring", "category": "Monitoring", "default": True},
    {"key": "scheduled_reports",     "label": "Scheduled Email Reports",    "category": "Reporting",  "default": True},
    {"key": "weekly_reports",        "label": "Weekly Report Generator",    "category": "Reporting",  "default": True},
    {"key": "client_portal",         "label": "Client Portal (OTP shares)", "category": "Reporting",  "default": True},
    {"key": "stripe_billing",        "label": "Stripe Billing",             "category": "Commercial", "default": True},
    {"key": "multi_tenant_routing",  "label": "Multi-Tenant URL Routing",   "category": "Platform",   "default": True},
]

DEFAULT_AI_MODELS = [
    # Ollama (free local — recommended for on-prem)
    {"id": "llama3.1:8b",        "label": "Llama 3.1 8B (Ollama, local)",      "provider": "ollama"},
    {"id": "llama3.2:3b",        "label": "Llama 3.2 3B (Ollama, fast)",       "provider": "ollama"},
    {"id": "qwen2.5:7b",         "label": "Qwen 2.5 7B (Ollama)",              "provider": "ollama"},
    {"id": "mistral:7b",         "label": "Mistral 7B (Ollama)",               "provider": "ollama"},
    # User-supplied API keys
    {"id": "gpt-4o-mini",                  "label": "GPT-4o mini",            "provider": "openai"},
    {"id": "gpt-4o",                       "label": "GPT-4o",                 "provider": "openai"},
    {"id": "claude-3-5-sonnet-20241022",   "label": "Claude 3.5 Sonnet",      "provider": "anthropic"},
    {"id": "claude-3-5-haiku-20241022",    "label": "Claude 3.5 Haiku (fast)","provider": "anthropic"},
    {"id": "gemini-1.5-flash",             "label": "Gemini 1.5 Flash",       "provider": "gemini"},
    {"id": "gemini-1.5-pro",               "label": "Gemini 1.5 Pro",         "provider": "gemini"},
    # Emergent (legacy, credit-based)
    {"id": "claude-sonnet-4-5-20250929",   "label": "Claude Sonnet 4.5 (Emergent)", "provider": "emergent"},
]


def _default_config() -> Dict:
    import os
    # Auto-pick provider: Ollama if reachable, else env-based, else rule_based
    auto_provider = "rule_based"
    if os.environ.get("LLM_PROVIDER"):
        auto_provider = os.environ.get("LLM_PROVIDER")
    elif os.environ.get("EMERGENT_LLM_KEY"):
        auto_provider = "emergent"  # legacy default
    elif os.environ.get("OPENAI_API_KEY"):
        auto_provider = "openai"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        auto_provider = "anthropic"

    return {
        "id": "global",
        "modules": {m["key"]: m["default"] for m in MODULE_CATALOG},
        "ai_copilot": {
            "system_prompt": DEFAULT_AI_SYSTEM_PROMPT,
            "provider": auto_provider,  # ollama | openai | anthropic | gemini | emergent | rule_based
            "model": "",  # empty = use provider default
            "model_provider": "anthropic",  # legacy field, kept for backward compat
            "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            "max_history_turns": 20,
        },
        "deny_patterns": list(DEFAULT_BODY_DENY_PATTERNS),
        "limits": {
            "default_check_interval_sec": 60,
            "default_check_timeout_sec": 10,
            "max_response_time_ms_default": 5000,
            "alert_cooldown_min": 5,
            "max_retention_days": 90,
            "auto_action_allowlist": [],
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "system",
    }


async def get_config() -> Dict:
    cfg = await db.feature_flags.find_one({"id": "global"}, {"_id": 0})
    if not cfg:
        cfg = _default_config()
        await db.feature_flags.insert_one(dict(cfg))
        cfg.pop("_id", None)
    # Backfill any newly-added module flags with defaults
    changed = False
    modules = cfg.setdefault("modules", {})
    for m in MODULE_CATALOG:
        if m["key"] not in modules:
            modules[m["key"]] = m["default"]
            changed = True
    if "ai_copilot" not in cfg:
        cfg["ai_copilot"] = _default_config()["ai_copilot"]; changed = True
    else:
        # Backfill new ai_copilot keys (provider, ollama_base_url) without overwriting existing
        defaults = _default_config()["ai_copilot"]
        for k in ("provider", "ollama_base_url"):
            if k not in cfg["ai_copilot"]:
                cfg["ai_copilot"][k] = defaults[k]; changed = True
    if "deny_patterns" not in cfg:
        cfg["deny_patterns"] = list(DEFAULT_BODY_DENY_PATTERNS); changed = True
    if "limits" not in cfg:
        cfg["limits"] = _default_config()["limits"]; changed = True
    elif "auto_action_allowlist" not in cfg["limits"]:
        cfg["limits"]["auto_action_allowlist"] = []; changed = True
    if changed:
        await db.feature_flags.update_one({"id": "global"}, {"$set": cfg}, upsert=True)
    return cfg


async def is_module_enabled(key: str) -> bool:
    cfg = await get_config()
    return bool(cfg.get("modules", {}).get(key, True))


async def get_ai_copilot_config() -> Dict:
    cfg = await get_config()
    return cfg.get("ai_copilot", _default_config()["ai_copilot"])


async def get_deny_patterns() -> List[str]:
    cfg = await get_config()
    return cfg.get("deny_patterns", list(DEFAULT_BODY_DENY_PATTERNS))


async def update_config(updates: Dict, admin_user: Dict) -> Dict:
    """Apply a partial update to the global config, with audit log."""
    current = await get_config()
    diffs: List[Dict] = []
    new_state = dict(current)

    # Module toggles
    if "modules" in updates and isinstance(updates["modules"], dict):
        new_modules = dict(new_state.get("modules", {}))
        for k, v in updates["modules"].items():
            if new_modules.get(k) != v:
                diffs.append({"section": "modules", "key": k, "from": new_modules.get(k), "to": v})
                new_modules[k] = bool(v)
        new_state["modules"] = new_modules

    # AI copilot config
    if "ai_copilot" in updates and isinstance(updates["ai_copilot"], dict):
        cur = dict(new_state.get("ai_copilot", {}))
        for k, v in updates["ai_copilot"].items():
            if cur.get(k) != v:
                # Truncate long values in audit log
                from_val = cur.get(k)
                from_short = (str(from_val)[:120] + "…") if from_val and len(str(from_val)) > 120 else from_val
                to_short = (str(v)[:120] + "…") if v and len(str(v)) > 120 else v
                diffs.append({"section": "ai_copilot", "key": k, "from": from_short, "to": to_short})
                cur[k] = v
        new_state["ai_copilot"] = cur

    # Deny patterns
    if "deny_patterns" in updates and isinstance(updates["deny_patterns"], list):
        cur = list(new_state.get("deny_patterns", []))
        new_list = [str(x).strip() for x in updates["deny_patterns"] if str(x).strip()]
        if cur != new_list:
            added = [x for x in new_list if x not in cur]
            removed = [x for x in cur if x not in new_list]
            diffs.append({"section": "deny_patterns", "added": added, "removed": removed,
                          "count_from": len(cur), "count_to": len(new_list)})
            new_state["deny_patterns"] = new_list

    # Limits
    if "limits" in updates and isinstance(updates["limits"], dict):
        cur = dict(new_state.get("limits", {}))
        for k, v in updates["limits"].items():
            if cur.get(k) != v:
                diffs.append({"section": "limits", "key": k, "from": cur.get(k), "to": v})
                cur[k] = v
        new_state["limits"] = cur

    if not diffs:
        return current  # no-op

    new_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    new_state["updated_by"] = admin_user.get("email", "unknown")
    new_state["id"] = "global"
    await db.feature_flags.update_one({"id": "global"}, {"$set": new_state}, upsert=True)

    # Audit log
    await db.feature_audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "changed_at": new_state["updated_at"],
        "changed_by": new_state["updated_by"],
        "diffs": diffs,
        "diff_count": len(diffs),
    })

    new_state.pop("_id", None)
    return new_state


async def list_audit_log(limit: int = 100) -> List[Dict]:
    return await db.feature_audit_log.find({}, {"_id": 0}).sort("changed_at", -1).limit(limit).to_list(length=limit)


def get_module_catalog() -> List[Dict]:
    return MODULE_CATALOG


def get_available_models() -> List[Dict]:
    return DEFAULT_AI_MODELS
