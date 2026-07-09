"""
FalconOps AI — Tenant Routing Service
Resolves an inbound request to a tenant via:
  1. Custom domain (Host header exact match against tenant.custom_domain)
  2. Subdomain (Host header subdomain prefix match against tenant.subdomain)
  3. Path prefix /t/{slug}/... (works in any environment, no DNS needed)

Used by middleware and admin UI. Emits DNS configuration instructions for the UI.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

from ..core.database import db

logger = logging.getLogger(__name__)

# Reserved subdomains (cannot be claimed by a tenant)
RESERVED_SUBDOMAINS = {"www", "app", "api", "admin", "preview", "static", "cdn", "mail", "dev", "stage", "staging"}

SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
DOMAIN_RE = re.compile(r"^([a-z0-9-]+\.)+[a-z]{2,}$")
PATH_TENANT_RE = re.compile(r"^/t/([a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?)(?:/|$)")


def validate_subdomain(sub: str) -> Tuple[bool, Optional[str]]:
    sub = (sub or "").lower().strip()
    if not sub:
        return False, "Subdomain cannot be empty"
    if sub in RESERVED_SUBDOMAINS:
        return False, f"'{sub}' is reserved"
    if not SUBDOMAIN_RE.match(sub):
        return False, "Subdomain must be 1–40 chars, lowercase, alphanumeric or hyphen, not starting/ending with hyphen"
    return True, None


def validate_domain(dom: str) -> Tuple[bool, Optional[str]]:
    dom = (dom or "").lower().strip()
    if not dom:
        return False, "Domain cannot be empty"
    if not DOMAIN_RE.match(dom):
        return False, "Invalid domain format"
    return True, None


# ──────────────────────────────────────────────
#  Tenant resolution
# ──────────────────────────────────────────────

async def resolve_tenant_from_request(host: Optional[str], path: Optional[str], default_slug: Optional[str] = None) -> Optional[Dict]:
    """Inspect Host header + path; return the matching tenant doc or None."""
    # 1. Path-prefix /t/{slug}
    if path:
        m = PATH_TENANT_RE.match(path)
        if m:
            slug = m.group(1)
            t = await db.tenants.find_one(
                {"$or": [{"slug": slug}, {"subdomain": slug}], "routing_enabled": {"$ne": False}},
                {"_id": 0},
            )
            if t:
                return {**t, "_routing_method": "path_prefix"}

    if not host:
        return None

    host_clean = host.split(":")[0].lower()

    # 2. Custom domain (exact match)
    t = await db.tenants.find_one(
        {"custom_domain": host_clean, "routing_enabled": {"$ne": False}},
        {"_id": 0},
    )
    if t:
        return {**t, "_routing_method": "custom_domain"}

    # 3. Subdomain match (X.<base_domain>)
    parts = host_clean.split(".")
    if len(parts) >= 3:
        sub = parts[0]
        base = ".".join(parts[1:])
        if sub not in RESERVED_SUBDOMAINS:
            t = await db.tenants.find_one(
                {"subdomain": sub, "base_domain": base, "routing_enabled": {"$ne": False}},
                {"_id": 0},
            )
            if not t:
                # Also accept tenants with subdomain set and ANY base_domain (wildcard mode)
                t = await db.tenants.find_one(
                    {"subdomain": sub, "routing_enabled": {"$ne": False}, "$or": [{"base_domain": None}, {"base_domain": ""}]},
                    {"_id": 0},
                )
            if t:
                return {**t, "_routing_method": "subdomain"}

    # 4. Default tenant fallback
    if default_slug:
        t = await db.tenants.find_one({"slug": default_slug}, {"_id": 0})
        if t:
            return {**t, "_routing_method": "default"}

    return None


# ──────────────────────────────────────────────
#  Update tenant routing
# ──────────────────────────────────────────────

async def set_tenant_routing(tenant_id: str, *, subdomain: Optional[str] = None,
                             custom_domain: Optional[str] = None, base_domain: Optional[str] = None,
                             routing_enabled: Optional[bool] = None) -> Dict:
    updates: Dict = {}

    if subdomain is not None:
        sub = subdomain.lower().strip()
        if sub == "":
            updates["subdomain"] = None
        else:
            ok, err = validate_subdomain(sub)
            if not ok:
                return {"error": err}
            existing = await db.tenants.find_one({"subdomain": sub, "id": {"$ne": tenant_id}}, {"_id": 0})
            if existing:
                return {"error": f"Subdomain '{sub}' is already used by tenant '{existing.get('name')}'"}
            updates["subdomain"] = sub

    if custom_domain is not None:
        dom = custom_domain.lower().strip()
        if dom == "":
            updates["custom_domain"] = None
        else:
            ok, err = validate_domain(dom)
            if not ok:
                return {"error": err}
            existing = await db.tenants.find_one({"custom_domain": dom, "id": {"$ne": tenant_id}}, {"_id": 0})
            if existing:
                return {"error": f"Custom domain '{dom}' is already used by tenant '{existing.get('name')}'"}
            updates["custom_domain"] = dom

    if base_domain is not None:
        bd = base_domain.lower().strip() or None
        if bd:
            ok, err = validate_domain(bd)
            if not ok:
                return {"error": err}
        updates["base_domain"] = bd

    if routing_enabled is not None:
        updates["routing_enabled"] = bool(routing_enabled)

    if not updates:
        return {"error": "No updates provided"}

    res = await db.tenants.update_one({"id": tenant_id}, {"$set": updates})
    if res.matched_count == 0:
        return {"error": "Tenant not found"}

    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    return {"tenant": tenant, "applied": updates}


# ──────────────────────────────────────────────
#  DNS instructions
# ──────────────────────────────────────────────

def build_dns_instructions(tenant: Dict, platform_apex: str = "falconops.ai") -> Dict:
    """Generate copy-pasteable DNS records for the user to set up."""
    instructions: Dict = {"tenant_id": tenant.get("id"), "tenant_name": tenant.get("name"),
                          "platform_apex": platform_apex, "records": []}

    sub = tenant.get("subdomain")
    if sub:
        instructions["records"].append({
            "type": "CNAME",
            "host": f"{sub}.{platform_apex}",
            "value": f"app.{platform_apex}",
            "ttl": 300,
            "purpose": "Subdomain routing — point this CNAME at the platform's main app domain.",
        })
        instructions["urls"] = {
            "subdomain_url": f"https://{sub}.{platform_apex}",
            "path_prefix_url": f"https://{platform_apex}/t/{sub}",
        }

    custom = tenant.get("custom_domain")
    if custom:
        instructions["records"].append({
            "type": "CNAME",
            "host": custom,
            "value": f"app.{platform_apex}",
            "ttl": 300,
            "purpose": "Vanity domain — point this CNAME at the platform.",
        })
        instructions["urls"] = {**instructions.get("urls", {}), "custom_domain_url": f"https://{custom}"}

    if not sub and not custom:
        instructions["records"].append({
            "type": "INFO",
            "message": "No subdomain or custom domain configured — only path-prefix routing is active.",
            "path_prefix_url": f"https://{platform_apex}/t/{tenant.get('slug', '<slug>')}",
        })

    instructions["verify_command"] = (
        f"curl -I -H 'Host: {custom or (sub + '.' + platform_apex if sub else platform_apex)}' "
        f"https://{platform_apex}/api/health"
    )
    return instructions


async def list_routing_summary() -> List[Dict]:
    """Admin view: every tenant's current URLs."""
    out: List[Dict] = []
    async for t in db.tenants.find({}, {"_id": 0}):
        out.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "slug": t.get("slug"),
            "subdomain": t.get("subdomain"),
            "custom_domain": t.get("custom_domain"),
            "base_domain": t.get("base_domain"),
            "routing_enabled": t.get("routing_enabled", True),
        })
    return out
