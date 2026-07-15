"""
FalconOps AI - Core Configuration
JWT and application settings
"""
import os
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment
ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / '.env')

# JWT Configuration — never fall back to a known/guessable secret. If JWT_SECRET_KEY is
# unset or left at an insecure placeholder, generate a random one for this process
# instead: tokens signed with it are still unforgeable, at the cost of invalidating
# sessions on every restart (and not working across multiple replicas) until a real
# secret is configured — a safe failure mode instead of a silently forgeable one.
_INSECURE_JWT_DEFAULTS = {"", "fallback_secret", "change-this", "changeme", "secret", "your-secret-key"}
_env_jwt_secret = os.environ.get('JWT_SECRET_KEY', '')
if _env_jwt_secret and _env_jwt_secret.strip().lower() not in _INSECURE_JWT_DEFAULTS:
    JWT_SECRET = _env_jwt_secret
else:
    JWT_SECRET = secrets.token_hex(32)
    logger.critical(
        "JWT_SECRET_KEY is unset or an insecure placeholder — generated a random "
        "per-process secret instead of using a guessable fallback. All previously "
        "issued tokens are now invalid, and tokens from this run won't survive a "
        "restart or work across multiple instances. Set a strong JWT_SECRET_KEY in "
        "backend/.env before deploying to production."
    )

JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 1440))

# Re-export database
from .database import db, get_database as get_db, close_database
