"""
FalconOps AI - Authentication Utilities
Password hashing, JWT token management, and auth dependencies
"""
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from ..core.database import db

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """Get current user from JWT token (returns None if not authenticated)"""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        return user
    except jwt.PyJWTError:
        return None


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Require authentication - raises 401 if not authenticated"""
    user = await get_current_user(credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Require admin role for access"""
    user = await get_current_user(credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_write_access(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Require admin or user role (not viewer) for write operations"""
    user = await get_current_user(credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Write access denied for viewer role")
    return user


# ======================== MULTI-TENANCY SUPPORT ========================

async def get_current_tenant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """Get tenant_id from current user's JWT token"""
    user = await get_current_user(credentials)
    if not user:
        return None
    return user.get("tenant_id")


async def require_tenant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Require tenant_id - raises 401 if not present"""
    user = await require_auth(credentials)
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant not assigned")
    return tenant_id


def build_tenant_query(tenant_id: Optional[str], base_query: dict = None) -> dict:
    """Build a MongoDB query with tenant_id filter"""
    query = base_query.copy() if base_query else {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    return query


async def ensure_tenant_access(user: dict, tenant_id: str) -> bool:
    """Verify user has access to specified tenant"""
    if user.get("role") == "admin":
        return True  # Admins can access all tenants
    return user.get("tenant_id") == tenant_id
