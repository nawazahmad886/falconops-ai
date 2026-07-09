"""
FalconOps AI - Licensing System
Enterprise license management and validation
"""
import os
import uuid
import hashlib
import hmac
import base64
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet

from ..core.database import db

# License secret key - in production, use environment variable
LICENSE_SECRET = os.environ.get("LICENSE_SECRET", "FalconOps-AI-Enterprise-2026-Secret-Key")


# ======================== LICENSE KEY GENERATION ========================

def generate_license_key(
    organization: str,
    license_type: str,  # trial, standard, professional, enterprise
    max_users: int,
    max_servers: int,
    max_monitors: int,
    valid_days: int = 365,
    features: list = None
) -> Dict[str, Any]:
    """Generate a new license key"""
    license_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(days=valid_days)
    
    # License payload
    payload = {
        "id": license_id,
        "organization": organization,
        "type": license_type,
        "max_users": max_users,
        "max_servers": max_servers,
        "max_monitors": max_monitors,
        "features": features or get_default_features(license_type),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "version": "1.0"
    }
    
    # Create signature
    payload_json = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        LICENSE_SECRET.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Encode license key
    license_data = {
        "payload": payload,
        "signature": signature
    }
    
    license_key = base64.urlsafe_b64encode(
        json.dumps(license_data).encode()
    ).decode()
    
    return {
        "license_key": license_key,
        "license_id": license_id,
        "organization": organization,
        "type": license_type,
        "expires_at": expires_at.isoformat(),
        "max_users": max_users,
        "max_servers": max_servers,
        "max_monitors": max_monitors,
        "features": payload["features"]
    }


def get_default_features(license_type: str) -> list:
    """Get default features based on license type"""
    base_features = ["monitoring", "alerts", "dashboard"]
    
    if license_type == "trial":
        return base_features + ["basic_reports"]
    elif license_type == "standard":
        return base_features + ["reports", "api_access", "email_alerts"]
    elif license_type == "professional":
        return base_features + ["reports", "api_access", "email_alerts", "apm", "topology", "runbooks"]
    elif license_type == "enterprise":
        return base_features + [
            "reports", "api_access", "email_alerts", "apm", "topology", 
            "runbooks", "ai_analysis", "ai_copilot", "multi_tenancy",
            "sso", "audit_logs", "custom_integrations", "on_prem_agents",
            "sla_reports", "white_label"
        ]
    return base_features


# ======================== LICENSE VALIDATION ========================

def validate_license_key(license_key: str) -> Dict[str, Any]:
    """Validate a license key and return its details"""
    try:
        # Decode license key
        license_data = json.loads(base64.urlsafe_b64decode(license_key.encode()))
        payload = license_data["payload"]
        signature = license_data["signature"]
        
        # Verify signature
        payload_json = json.dumps(payload, sort_keys=True)
        expected_signature = hmac.new(
            LICENSE_SECRET.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return {"valid": False, "error": "Invalid license signature"}
        
        # Check expiration
        expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            return {
                "valid": False, 
                "error": "License expired",
                "expired_at": payload["expires_at"]
            }
        
        # Calculate days remaining
        days_remaining = (expires_at - datetime.now(timezone.utc)).days
        
        return {
            "valid": True,
            "license_id": payload["id"],
            "organization": payload["organization"],
            "type": payload["type"],
            "max_users": payload["max_users"],
            "max_servers": payload["max_servers"],
            "max_monitors": payload["max_monitors"],
            "features": payload["features"],
            "expires_at": payload["expires_at"],
            "days_remaining": days_remaining,
            "version": payload.get("version", "1.0")
        }
        
    except Exception as e:
        return {"valid": False, "error": f"Invalid license key format: {str(e)}"}


def check_feature_access(license_key: str, feature: str) -> bool:
    """Check if a feature is available in the license"""
    result = validate_license_key(license_key)
    if not result.get("valid"):
        return False
    return feature in result.get("features", [])


def check_limit(license_key: str, limit_type: str, current_count: int) -> Dict[str, Any]:
    """Check if a limit is exceeded"""
    result = validate_license_key(license_key)
    if not result.get("valid"):
        return {"allowed": False, "error": result.get("error")}
    
    limit_map = {
        "users": "max_users",
        "servers": "max_servers",
        "monitors": "max_monitors"
    }
    
    max_key = limit_map.get(limit_type)
    if not max_key:
        return {"allowed": True}
    
    max_value = result.get(max_key, 0)
    allowed = current_count < max_value
    
    return {
        "allowed": allowed,
        "current": current_count,
        "max": max_value,
        "remaining": max(0, max_value - current_count)
    }


# ======================== LICENSE STORAGE ========================

async def store_license(license_key: str) -> Dict[str, Any]:
    """Store license in database"""
    result = validate_license_key(license_key)
    if not result.get("valid"):
        return {"success": False, "error": result.get("error")}
    
    license_doc = {
        "id": result["license_id"],
        "license_key": license_key,
        "organization": result["organization"],
        "type": result["type"],
        "max_users": result["max_users"],
        "max_servers": result["max_servers"],
        "max_monitors": result["max_monitors"],
        "features": result["features"],
        "expires_at": result["expires_at"],
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    
    # Remove any existing license
    await db.licenses.delete_many({})
    
    # Store new license
    await db.licenses.insert_one(license_doc)
    
    return {"success": True, "license": {k: v for k, v in license_doc.items() if k != "_id"}}


async def get_current_license() -> Optional[Dict[str, Any]]:
    """Get the current active license"""
    license_doc = await db.licenses.find_one({"status": "active"}, {"_id": 0})
    
    if not license_doc:
        return None
    
    # Validate the stored license
    result = validate_license_key(license_doc.get("license_key", ""))
    if not result.get("valid"):
        # License expired or invalid
        await db.licenses.update_one(
            {"id": license_doc["id"]},
            {"$set": {"status": "expired"}}
        )
        return None
    
    return {**license_doc, "days_remaining": result.get("days_remaining", 0)}


async def revoke_license() -> Dict[str, Any]:
    """Revoke the current license"""
    result = await db.licenses.delete_many({})
    return {"success": True, "deleted": result.deleted_count}


# ======================== LICENSE PLANS ========================

LICENSE_PLANS = {
    "trial": {
        "name": "Trial",
        "description": "14-day free trial",
        "max_users": 3,
        "max_servers": 5,
        "max_monitors": 10,
        "valid_days": 14,
        "price": 0
    },
    "standard": {
        "name": "Standard",
        "description": "For small teams",
        "max_users": 10,
        "max_servers": 25,
        "max_monitors": 50,
        "valid_days": 365,
        "price": 299
    },
    "professional": {
        "name": "Professional",
        "description": "For growing organizations",
        "max_users": 50,
        "max_servers": 100,
        "max_monitors": 200,
        "valid_days": 365,
        "price": 799
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "For large enterprises",
        "max_users": 999999,
        "max_servers": 999999,
        "max_monitors": 999999,
        "valid_days": 365,
        "price": "Contact Sales"
    }
}


def get_license_plans() -> Dict[str, Any]:
    """Get available license plans"""
    return LICENSE_PLANS
