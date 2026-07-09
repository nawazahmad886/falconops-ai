"""Phase 26 tests: enterprise contact alias, bundle request flow,
token-gated download, source-download admin gating, max-uses enforcement.
"""
import os
import pytest
import requests
from pathlib import Path

# Load frontend .env so REACT_APP_BACKEND_URL is available when running pytest from CLI
def _load_env(path):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

_load_env("/app/frontend/.env")
_load_env("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token")


@pytest.fixture(scope="module")
def viewer_token():
    r = requests.post(f"{API}/auth/login", json=VIEWER, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token")


# ── Enterprise contact alias ────────────────────────────────────────────────
class TestEnterpriseContactAlias:
    def test_contact_enterprise_accepts_payload(self):
        payload = {
            "name": "TEST_Enterprise Buyer",
            "email": "TEST_buyer@example.com",
            "company": "TEST Corp",
            "team_size": "200-1000",
            "message": "We want a quote for 500 nodes",
        }
        r = requests.post(f"{API}/contact/enterprise", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert "lead_id" in data and isinstance(data["lead_id"], str)


# ── Bundle request + token validate + token download ───────────────────────
@pytest.fixture(scope="module")
def bundle_token():
    payload = {
        "name": "TEST_Bundle User",
        "email": "TEST_bundle@example.com",
        "company": "TEST Acme",
        "team_size": "50-200",
        "use_case": "Air-gapped on-prem evaluation",
    }
    r = requests.post(f"{API}/licenses/request-bundle", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("expires_in_days") == 7
    assert data.get("max_uses") == 3
    assert data.get("lead_id")

    # Fetch token from the DB-backed validate endpoint:
    # We need the actual token string. Since dev URL may not be exposed,
    # query Mongo directly via a helper request — but we don't have that.
    # The dev URL field _dev_download_url is None when ENV is not 'dev'.
    # So we look up the token via Mongo using motor.
    return data["lead_id"]


@pytest.fixture(scope="module")
def actual_bundle_token():
    """Hit request-bundle, then read token from MongoDB."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")

    payload = {
        "name": "TEST_TokenUser",
        "email": "TEST_tokenuser@example.com",
        "company": "TEST CorpToken",
        "team_size": "10-50",
        "use_case": "Token-flow tests",
    }
    r = requests.post(f"{API}/licenses/request-bundle", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead_id"]

    async def _fetch():
        client = AsyncIOMotorClient(mongo_url)
        try:
            db = client[db_name]
            doc = await db.bundle_tokens.find_one({"lead_id": lead_id}, {"_id": 0})
            return doc
        finally:
            client.close()

    doc = asyncio.get_event_loop().run_until_complete(_fetch())
    assert doc, "bundle_tokens row not created"
    return doc["token"]


class TestBundleTokenValidate:
    def test_validate_valid_token(self, actual_bundle_token):
        r = requests.get(
            f"{API}/licenses/bundle-token/validate",
            params={"token": actual_bundle_token},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["email"].lower() == "test_tokenuser@example.com"
        assert d["company"] == "TEST CorpToken"
        assert d["uses"] == 0
        assert d["max_uses"] == 3
        assert "expires_at" in d

    def test_validate_invalid_token(self):
        r = requests.get(
            f"{API}/licenses/bundle-token/validate",
            params={"token": "x" * 64},  # well-formed but not in DB
            timeout=20,
        )
        assert r.status_code == 404

    def test_validate_malformed_token(self):
        r = requests.get(
            f"{API}/licenses/bundle-token/validate",
            params={"token": "short"},
            timeout=20,
        )
        assert r.status_code == 400


# ── Token-gated download (and uses increment) ──────────────────────────────
class TestTokenDownload:
    def test_download_with_bad_token_404(self):
        r = requests.get(
            f"{API}/licenses/download-with-token",
            params={"token": "y" * 64},
            timeout=60,
            stream=True,
        )
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:200]}"

    def test_download_with_valid_token_streams(self, actual_bundle_token):
        # First download
        r = requests.get(
            f"{API}/licenses/download-with-token",
            params={"token": actual_bundle_token},
            timeout=180,
            stream=True,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        content = r.content
        assert len(content) > 100_000, f"archive too small: {len(content)} bytes"

        # Verify uses incremented to 1
        v = requests.get(
            f"{API}/licenses/bundle-token/validate",
            params={"token": actual_bundle_token},
            timeout=20,
        )
        assert v.status_code == 200
        assert v.json()["uses"] == 1

    def test_max_uses_enforced(self, actual_bundle_token):
        # Already 1 use from prior test. Download 2 more → uses = 3.
        for i in range(2, 4):
            r = requests.get(
                f"{API}/licenses/download-with-token",
                params={"token": actual_bundle_token},
                timeout=180,
                stream=True,
            )
            assert r.status_code == 200, f"call #{i} status {r.status_code}"
            _ = r.content

        # 4th attempt must be rejected (429 per spec)
        r4 = requests.get(
            f"{API}/licenses/download-with-token",
            params={"token": actual_bundle_token},
            timeout=60,
        )
        assert r4.status_code == 429, f"expected 429 after max uses, got {r4.status_code}: {r4.text[:200]}"


# ── Admin source-download gating still enforced ─────────────────────────────
class TestSourceDownloadGating:
    def test_download_source_no_auth_401(self):
        r = requests.get(f"{API}/licenses/download/source", timeout=20)
        assert r.status_code == 401, f"got {r.status_code}: {r.text[:200]}"

    def test_download_source_viewer_forbidden(self, viewer_token):
        r = requests.get(
            f"{API}/licenses/download/source",
            headers={"Authorization": f"Bearer {viewer_token}"},
            timeout=20,
        )
        assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"
