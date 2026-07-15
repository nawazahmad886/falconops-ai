"""
FalconOps AI - Authentication Routes
User registration, login, and profile management
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from ..core.database import db
from ..models.schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from ..utils.auth import hash_password, verify_password, create_access_token, require_auth
from fastapi import Depends

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Per-IP rate limits — throttles brute force/credential stuffing without ever locking a
# legitimate account (that trade-off was deliberately ruled out; this only makes an
# attacker's own IP wait, it never blocks a real user's account).
LOGIN_RATE_LIMIT = (10, 300)     # 10 attempts / 5 minutes per IP
REGISTER_RATE_LIMIT = (5, 3600)  # 5 registrations / hour per IP


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _record_auth_event(
    action: str, email: str, ip: str, user_agent: str,
    severity: str = "info", message: str = "", tenant_id: str = None,
) -> None:
    """Feeds real login/signup activity into the security-monitoring pipeline (brute
    force, credential stuffing, impossible travel, signup abuse, malicious-IP checks) —
    fire-and-forget so a slow geo lookup or a monitoring hiccup can never affect the
    auth response itself."""
    try:
        from ..services.security_service import ingest_security_event
        from ..services.geo_ip_service import get_geo_location
        geo = await get_geo_location(ip)
        await ingest_security_event({
            "action": action,
            "user": email,
            "source_ip": ip,
            "category": "authentication",
            "severity": severity,
            "message": message or f"{action} for {email} from {ip}",
            "geo_location": geo,
            "user_agent": user_agent,
            "source": "auth_api",
        }, tenant_id=tenant_id)
    except Exception as e:
        logger.warning(f"Auth security event recording skipped: {e}")


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request):
    """Register a new user"""
    ip = _client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    from ..services.rate_limiter_service import is_rate_limited
    if await is_rate_limited(f"register:{ip}", *REGISTER_RATE_LIMIT):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please try again later.")

    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        asyncio.create_task(_record_auth_event(
            "signup_failed", user_data.email, ip, user_agent, severity="info",
            message=f"Registration attempt for already-registered email {user_data.email} from {ip}",
        ))
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "organization": user_data.organization,
        "hashed_password": hash_password(user_data.password),
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.users.insert_one(user_doc)
    asyncio.create_task(_record_auth_event("signup", user_data.email, ip, user_agent, severity="info"))

    token = create_access_token({"sub": user_id})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            organization=user_data.organization,
            role="user",
            created_at=user_doc["created_at"]
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request):
    """Login user and return JWT token"""
    ip = _client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    from ..services.rate_limiter_service import is_rate_limited
    if await is_rate_limited(f"login:{ip}", *LOGIN_RATE_LIMIT):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")

    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        asyncio.create_task(_record_auth_event(
            "login_failed", credentials.email, ip, user_agent, severity="warning",
            message=f"Login attempt for unknown email {credentials.email} from {ip}",
        ))
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Support both password field names for backward compatibility
    password_hash = user.get("hashed_password") or user.get("password_hash")
    if not password_hash or not verify_password(credentials.password, password_hash):
        asyncio.create_task(_record_auth_event(
            "login_failed", credentials.email, ip, user_agent, severity="warning",
            tenant_id=user.get("tenant_id"),
        ))
        raise HTTPException(status_code=401, detail="Invalid email or password")

    asyncio.create_task(_record_auth_event(
        "login_success", credentials.email, ip, user_agent, severity="info",
        tenant_id=user.get("tenant_id"),
    ))

    token = create_access_token({"sub": user["id"]})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            organization=user.get("organization"),
            role=user.get("role", "user"),
            created_at=user["created_at"]
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(require_auth)):
    """Get current user profile"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        organization=current_user.get("organization"),
        role=current_user.get("role", "user"),
        created_at=current_user["created_at"]
    )
