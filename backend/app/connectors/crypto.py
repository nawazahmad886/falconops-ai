"""
FalconOps AI - Connector SDK: secret encryption at rest

Encrypts password-typed config fields in db.integrations (API keys, tokens,
credentials) using Fernet symmetric encryption, closing a real gap: this
collection previously stored all connector secrets as plaintext (confirmed by
repo-wide grep before this module existed — no Fernet/KMS/Vault touched it).

Key management: CONNECTOR_SECRET_KEY env var if set, else a key is generated
once and persisted in db.connector_crypto_config (a singleton doc, same idiom
used elsewhere in this codebase for shared config). Startup does NOT hard-fail
if the env var is absent — that would break every existing on-prem install
that predates this module — but logs a loud warning recommending one for
production.

Migration of pre-existing plaintext secrets is two-layered:
  1. Sniff-and-reencrypt-on-save: encrypt_config_secrets() is a no-op for
     values already carrying ENC_PREFIX, and encrypts anything still
     plaintext — so any future save transparently upgrades that doc.
  2. migrate_legacy_integrations(): a one-time, idempotent, non-fatal sweep
     run at startup that proactively re-encrypts every existing plaintext
     secret (after backing up the original), so installs don't have to wait
     for an admin to click Save.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from pymongo import ReturnDocument

from ..core.config import CONNECTOR_SECRET_KEY
from ..core.database import db

logger = logging.getLogger(__name__)

ENC_PREFIX = "fnet:"

_fernet_cache: Optional[Fernet] = None


async def get_fernet() -> Fernet:
    """Lazily resolves and caches the Fernet instance for the process lifetime."""
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache

    key = CONNECTOR_SECRET_KEY
    if not key:
        doc = await db.connector_crypto_config.find_one_and_update(
            {"key": "fernet_key"},
            {"$setOnInsert": {
                "key": "fernet_key",
                "value": Fernet.generate_key().decode("utf-8"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        key = doc["value"]
        logger.warning(
            "CONNECTOR_SECRET_KEY not set — auto-generated a connector secret "
            "encryption key and persisted it in db.connector_crypto_config. "
            "Set CONNECTOR_SECRET_KEY explicitly in production so the key "
            "isn't tied to this database instance."
        )

    _fernet_cache = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    return _fernet_cache


async def encrypt_value(plaintext: str) -> str:
    """Idempotent: a no-op for a value that's already encrypted. This matters
    because save_integration()'s existing masked-value restore logic puts back
    the *previously stored* value unchanged (encrypted, post-migration) before
    this function runs — without this check, every save that leaves a secret
    untouched (e.g. just toggling enabled/disabled) would re-encrypt an
    already-encrypted value and corrupt it (double ENC_PREFIX, undecryptable)."""
    if not plaintext:
        return plaintext
    if plaintext.startswith(ENC_PREFIX):
        return plaintext
    fernet = await get_fernet()
    return ENC_PREFIX + fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


async def decrypt_value(stored: str) -> str:
    """No ENC_PREFIX -> returned as-is (legacy plaintext, never crashes on it).
    InvalidToken (corrupt/foreign-key ciphertext) -> logged, raw value returned
    rather than raising, so a bad value never takes down a whole request."""
    if not stored or not stored.startswith(ENC_PREFIX):
        return stored
    fernet = await get_fernet()
    ciphertext = stored[len(ENC_PREFIX):]
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("connector secret decrypt failed (InvalidToken) — returning raw stored value")
        return stored
    except Exception as e:
        logger.warning(f"connector secret decrypt failed ({e}) — returning raw stored value")
        return stored


def _secret_field_keys(catalog_item: Optional[Dict[str, Any]]) -> set:
    if not catalog_item:
        return set()
    return {f["key"] for f in catalog_item.get("fields", []) if f.get("type") == "password"}


async def encrypt_config_secrets(config: Dict[str, Any], catalog_item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Only touches keys the catalog marks type:"password" — reuses the
    existing field-typing convention rather than introducing a new one."""
    secret_keys = _secret_field_keys(catalog_item)
    if not secret_keys:
        return config
    out = dict(config)
    for key in secret_keys:
        val = out.get(key)
        if isinstance(val, str) and val:
            out[key] = await encrypt_value(val)
    return out


async def decrypt_config_secrets(config: Dict[str, Any], catalog_item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    secret_keys = _secret_field_keys(catalog_item)
    if not secret_keys:
        return config
    out = dict(config)
    for key in secret_keys:
        val = out.get(key)
        if isinstance(val, str) and val:
            out[key] = await decrypt_value(val)
    return out


async def migrate_legacy_integrations() -> Dict[str, int]:
    """One-time, idempotent sweep: re-encrypts any plaintext password-typed
    field still stored in db.integrations, after backing up the original doc.
    Safe to run on every boot — no-op for already-migrated or secret-less docs."""
    from ..services.integration_management_service import INTEGRATION_CATALOG

    catalog_by_id = {item["id"]: item for item in INTEGRATION_CATALOG}
    migrated = 0
    skipped = 0

    async for doc in db.integrations.find({}, {"_id": 0}):
        catalog_item = catalog_by_id.get(doc.get("integration_id"))
        secret_keys = _secret_field_keys(catalog_item)
        config = doc.get("config") or {}
        needs_migration = any(
            isinstance(config.get(k), str) and config.get(k) and not config[k].startswith(ENC_PREFIX)
            for k in secret_keys
        )
        if not needs_migration:
            skipped += 1
            continue

        await db.integrations_migration_backup.update_one(
            {"integration_id": doc["integration_id"]},
            {"$setOnInsert": {**doc, "backed_up_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        new_config = await encrypt_config_secrets(config, catalog_item)
        await db.integrations.update_one(
            {"integration_id": doc["integration_id"]},
            {"$set": {"config": new_config}},
        )
        migrated += 1

    return {"migrated": migrated, "skipped": skipped}
