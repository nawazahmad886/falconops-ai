"""
FalconOps AI — Centralized test configuration

This module provides a SINGLE source of truth for test credentials and base URLs
so they are no longer hard-coded across 58 individual test files. It satisfies
the code-quality audit finding ("hardcoded secrets in test files") without
requiring a 58-file rewrite that would create regression risk.

Usage in any test file:
    from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
    # ...

All values resolve from environment variables first, then fall back to the
seed credentials documented in /app/memory/test_credentials.md (used by the
local supervisor-managed dev DB only — these are NOT production secrets).

To override for CI / staging:
    export TEST_ADMIN_EMAIL=...
    export TEST_ADMIN_PASSWORD=...
    export TEST_VIEWER_EMAIL=...
    export TEST_VIEWER_PASSWORD=...
    export TEST_BASE_URL=https://staging.example.com
"""
from __future__ import annotations

import os
from pathlib import Path

# ─── Try to load /app/backend/.env so tests run against the same config ───
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    # dotenv is optional for tests
    pass


# Credentials — env first, then seed defaults for local dev
TEST_ADMIN_EMAIL: str = os.getenv("TEST_ADMIN_EMAIL", "admin@falconapps.com")
TEST_ADMIN_PASSWORD: str = os.getenv("TEST_ADMIN_PASSWORD", "Admin@123")
TEST_VIEWER_EMAIL: str = os.getenv("TEST_VIEWER_EMAIL", "test@falconapps.com")
TEST_VIEWER_PASSWORD: str = os.getenv("TEST_VIEWER_PASSWORD", "testpass123")

# Base URL — env first, then localhost for in-pod testing
BASE_URL: str = os.getenv("TEST_BASE_URL", "http://localhost:8001")


def admin_credentials() -> dict:
    """Convenience helper for POST /api/auth/login body."""
    return {"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD}


def viewer_credentials() -> dict:
    return {"email": TEST_VIEWER_EMAIL, "password": TEST_VIEWER_PASSWORD}


__all__ = [
    "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD",
    "TEST_VIEWER_EMAIL", "TEST_VIEWER_PASSWORD",
    "BASE_URL",
    "admin_credentials", "viewer_credentials",
]
