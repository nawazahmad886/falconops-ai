"""
FalconOps AI - Synthetic URL Monitoring Service
Checks URL health via HTTP requests with optional login + OTP validation.
Adds multi-step journeys with shared assertion engine + variable extraction.
"""
import uuid
import time
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import requests
import pyotp

from ..core.database import db
from .assertion_engine import (
    evaluate_assertions, merge_safe_defaults, substitute_vars,
    extract_variables, check_ssl_expiry,
)

logger = logging.getLogger("synthetic-monitor")


async def execute_check(monitor: dict) -> dict:
    """Execute a synthetic URL check with optional auth + OTP."""
    monitor_id = monitor["id"]
    url = monitor["url"]
    auth_config = monitor.get("auth_config") or {}
    check_type = monitor.get("check_type", "http")  # http, login, login_otp
    timeout = monitor.get("timeout", 30)
    expected_status = monitor.get("expected_status", 200)
    expected_text = monitor.get("expected_text", "")
    # SSL verification — defaults to True for security. Operators monitoring
    # internal/self-signed sites can opt out per-monitor via verify_ssl=false.
    verify_ssl = bool(monitor.get("verify_ssl", True))

    start = time.time()
    result = {
        "id": str(uuid.uuid4()),
        "monitor_id": monitor_id,
        "monitor_name": monitor.get("name", url),
        "url": url,
        "check_type": check_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "steps": [],
    }

    session = requests.Session()
    session.headers["User-Agent"] = "FalconOps-Synthetic/2.0"
    # Suppress only the specific InsecureRequestWarning when verify_ssl=False
    # — keep ALL other urllib3 warnings flowing through.
    if not verify_ssl:
        try:
            from urllib3.exceptions import InsecureRequestWarning
            import warnings
            warnings.filterwarnings("ignore", category=InsecureRequestWarning)
        except Exception:
            pass

    try:
        if check_type == "http":
            result = await _check_http(session, result, url, timeout, expected_status, expected_text, verify_ssl=verify_ssl)

        elif check_type == "login":
            result = await _check_login(session, result, url, auth_config, timeout, expected_status, expected_text, verify_ssl=verify_ssl)

        elif check_type == "login_otp":
            result = await _check_login_otp(session, result, url, auth_config, timeout, expected_status, expected_text, verify_ssl=verify_ssl)

        elif check_type == "multi_step":
            result = await _check_multi_step(session, result, monitor, timeout)

        else:
            result = await _check_http(session, result, url, timeout, expected_status, expected_text, verify_ssl=verify_ssl)

    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["error"] = f"Request timed out after {timeout}s"
        result["steps"].append({"step": "Request", "status": "timeout", "error": f"Timeout after {timeout}s"})
    except requests.exceptions.ConnectionError as e:
        result["status"] = "connection_error"
        result["error"] = f"Connection failed: {str(e)[:200]}"
        result["steps"].append({"step": "Connect", "status": "error", "error": str(e)[:200]})
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:500]
        result["steps"].append({"step": "Check", "status": "error", "error": str(e)[:200]})
    finally:
        session.close()

    result["response_time_ms"] = round((time.time() - start) * 1000, 1)
    result["is_up"] = result.get("status") == "success"

    # Store result
    await db.db.synthetic_results.insert_one({**result})
    result.pop("_id", None)

    # Update monitor status
    await db.db.synthetic_monitors.update_one(
        {"id": monitor_id},
        {"$set": {
            "last_check": result["timestamp"],
            "last_status": result["status"],
            "last_response_time": result["response_time_ms"],
            "is_up": result["is_up"],
        }}
    )

    return result


async def _check_http(session, result, url, timeout, expected_status, expected_text, verify_ssl=True):
    """Simple HTTP GET check."""
    resp = session.get(url, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    step = {
        "step": "HTTP GET",
        "url": url,
        "status_code": resp.status_code,
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    }

    if resp.status_code == expected_status:
        step["status"] = "pass"
    else:
        step["status"] = "fail"
        step["error"] = f"Expected {expected_status}, got {resp.status_code}"

    if expected_text and expected_text not in resp.text:
        step["status"] = "fail"
        step["error"] = f"Expected text '{expected_text[:50]}' not found in response"

    result["steps"].append(step)
    result["status_code"] = resp.status_code
    result["status"] = "success" if step["status"] == "pass" else "failed"
    result["ssl_valid"] = resp.url.startswith("https")
    return result


async def _check_login(session, result, url, auth_config, timeout, expected_status, expected_text, verify_ssl=True):
    """Login check: GET page → POST credentials → verify response."""
    login_url = auth_config.get("login_url", url)
    username = auth_config.get("username", "")
    password = auth_config.get("password", "")
    username_field = auth_config.get("username_field", "username")
    password_field = auth_config.get("password_field", "password")
    success_url = auth_config.get("success_url", "")
    success_text = auth_config.get("success_text", expected_text)

    # Step 1: Load login page
    resp = session.get(login_url, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    result["steps"].append({
        "step": "Load Login Page",
        "url": login_url,
        "status_code": resp.status_code,
        "status": "pass" if resp.status_code == 200 else "fail",
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    })

    if resp.status_code != 200:
        result["status"] = "failed"
        result["status_code"] = resp.status_code
        return result

    # Step 2: POST credentials
    login_data = {username_field: username, password_field: password}
    resp = session.post(login_url, data=login_data, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    step2 = {
        "step": "Submit Login",
        "status_code": resp.status_code,
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    }

    login_success = resp.status_code in (200, 302, 303)
    if success_text and success_text not in resp.text:
        login_success = False
        step2["error"] = f"Success text '{success_text[:50]}' not found"
    if success_url and success_url not in resp.url:
        login_success = False
        step2["error"] = f"Not redirected to {success_url}"

    step2["status"] = "pass" if login_success else "fail"
    result["steps"].append(step2)
    result["status_code"] = resp.status_code
    result["status"] = "success" if login_success else "failed"
    return result


async def _check_login_otp(session, result, url, auth_config, timeout, expected_status, expected_text, verify_ssl=True):
    """Login + OTP check: GET page → POST credentials → Submit TOTP → verify."""
    login_url = auth_config.get("login_url", url)
    username = auth_config.get("username", "")
    password = auth_config.get("password", "")
    username_field = auth_config.get("username_field", "username")
    password_field = auth_config.get("password_field", "password")
    otp_secret = auth_config.get("otp_secret", "")
    otp_field = auth_config.get("otp_field", "otp")
    otp_url = auth_config.get("otp_url", login_url)
    success_url = auth_config.get("success_url", "")
    success_text = auth_config.get("success_text", expected_text)

    # Step 1: Load login page
    resp = session.get(login_url, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    result["steps"].append({
        "step": "Load Login Page",
        "url": login_url,
        "status_code": resp.status_code,
        "status": "pass" if resp.status_code == 200 else "fail",
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    })

    if resp.status_code != 200:
        result["status"] = "failed"
        result["status_code"] = resp.status_code
        return result

    # Step 2: POST credentials
    login_data = {username_field: username, password_field: password}
    resp = session.post(login_url, data=login_data, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    step2 = {
        "step": "Submit Credentials",
        "status_code": resp.status_code,
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    }
    cred_success = resp.status_code in (200, 302, 303)
    step2["status"] = "pass" if cred_success else "fail"
    result["steps"].append(step2)

    if not cred_success:
        result["status"] = "failed"
        result["status_code"] = resp.status_code
        return result

    # Step 3: Generate and submit OTP
    otp_code = ""
    if otp_secret:
        totp = pyotp.TOTP(otp_secret)
        otp_code = totp.now()
    else:
        otp_code = "000000"  # Placeholder if no secret configured

    otp_data = {otp_field: otp_code}
    resp = session.post(otp_url, data=otp_data, timeout=timeout, allow_redirects=True, verify=verify_ssl)
    step3 = {
        "step": "Submit OTP",
        "otp_generated": bool(otp_secret),
        "status_code": resp.status_code,
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 1),
    }

    otp_success = resp.status_code in (200, 302, 303)
    if success_text and success_text not in resp.text:
        otp_success = False
        step3["error"] = f"Success text '{success_text[:50]}' not found after OTP"
    if success_url and success_url not in resp.url:
        otp_success = False
        step3["error"] = f"Not redirected to {success_url} after OTP"

    step3["status"] = "pass" if otp_success else "fail"
    result["steps"].append(step3)
    result["status_code"] = resp.status_code
    result["status"] = "success" if otp_success else "failed"
    return result


async def calculate_availability(monitor_id: str, hours: int = 24) -> dict:
    """Calculate availability percentage for a monitor."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total = await db.db.synthetic_results.count_documents(
        {"monitor_id": monitor_id, "timestamp": {"$gte": since}}
    )
    up = await db.db.synthetic_results.count_documents(
        {"monitor_id": monitor_id, "timestamp": {"$gte": since}, "is_up": True}
    )
    if total == 0:
        return {"availability_pct": 100, "total_checks": 0, "up_checks": 0, "down_checks": 0}

    return {
        "availability_pct": round(up / total * 100, 2),
        "total_checks": total,
        "up_checks": up,
        "down_checks": total - up,
    }


async def get_response_time_series(monitor_id: str, hours: int = 24) -> list:
    """Get response time series data."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    results = await db.db.synthetic_results.find(
        {"monitor_id": monitor_id, "timestamp": {"$gte": since}},
        {"_id": 0, "timestamp": 1, "response_time_ms": 1, "status": 1, "is_up": 1}
    ).sort("timestamp", 1).to_list(length=500)
    return results


# ─────────────────────────────────────────────────────
#  Multi-Step Journey
# ─────────────────────────────────────────────────────

async def _check_multi_step(session, result, monitor, timeout):
    """Execute a multi-step synthetic journey with assertions + variable extraction.

    Each step shape:
      {
        "name": "Login API",
        "method": "POST",
        "url": "https://api.example.com/login",
        "headers": {"Content-Type": "application/json"},
        "body": {"email": "test@x.com", "password": "***"},
        "body_type": "json" | "form" | "raw",
        "assertions": [{"type": "json_path_eq", "path": "$.success", "value": true}],
        "extract": {"auth_token": "$.token"},
        "max_response_time_ms": 2000,
        "ssl_expiry_warn_days": 14,
        "apply_safe_defaults": true,
        "timeout": 10
      }

    Subsequent steps can reference previously extracted variables via ${var_name}
    in url / headers / body strings.
    """
    steps_in: List[Dict] = monitor.get("steps") or []
    if not steps_in:
        # Synthesize a single GET step from the legacy fields
        steps_in = [{
            "name": "GET",
            "method": "GET",
            "url": monitor["url"],
            "assertions": monitor.get("assertions") or [],
            "max_response_time_ms": monitor.get("max_response_time_ms"),
            "ssl_expiry_warn_days": monitor.get("ssl_expiry_warn_days", 14),
        }]

    variables: Dict[str, str] = dict(monitor.get("variables") or {})
    aggregate_status = "success"
    journey_failure_reason = None

    for idx, raw_step in enumerate(steps_in, start=1):
        step = substitute_vars(raw_step, variables)
        name = step.get("name") or f"Step {idx}"
        method = (step.get("method") or "GET").upper()
        url = step.get("url")
        headers = step.get("headers") or {}
        body = step.get("body")
        body_type = step.get("body_type") or ("json" if isinstance(body, (dict, list)) else "raw")
        step_timeout = int(step.get("timeout") or timeout)
        max_rt = step.get("max_response_time_ms")
        ssl_warn_days = int(step.get("ssl_expiry_warn_days") or 14)
        apply_defaults = step.get("apply_safe_defaults", True)
        assertions_raw = step.get("assertions") or []
        assertions = merge_safe_defaults(assertions_raw, enable=apply_defaults)
        extract_map = step.get("extract") or {}

        if not url:
            failure = {"step": name, "step_number": idx, "status": "error",
                       "error": "Missing url in step"}
            result["steps"].append(failure)
            aggregate_status = "failed"
            journey_failure_reason = f"Step {idx} '{name}': missing URL"
            break

        s_start = time.time()
        try:
            kwargs = {"timeout": step_timeout, "allow_redirects": True, "verify": False, "headers": headers}
            if body is not None:
                if body_type == "json":
                    kwargs["json"] = body
                elif body_type == "form":
                    kwargs["data"] = body
                else:
                    kwargs["data"] = body if isinstance(body, (str, bytes)) else _json_safe(body)

            resp = session.request(method, url, **kwargs)
            duration_ms = round((time.time() - s_start) * 1000, 1)
            body_text = resp.text or ""
            failures = evaluate_assertions(assertions, body_text, resp.status_code, duration_ms, max_rt)

            # SSL probe (HTTPS only, async to thread)
            ssl_days = None
            if url.lower().startswith("https://"):
                ssl_info = await asyncio.to_thread(check_ssl_expiry, url, ssl_warn_days)
                ssl_days = ssl_info.get("days_remaining")

            # Extract variables for next steps
            new_vars = extract_variables(extract_map, body_text)
            variables.update(new_vars)

            step_status = "pass" if not failures else "fail"
            step_record = {
                "step": name,
                "step_number": idx,
                "method": method,
                "url": url,
                "status_code": resp.status_code,
                "response_time_ms": duration_ms,
                "status": step_status,
                "assertion_failures": failures,
                "extracted_variables": list(new_vars.keys()),
                "ssl_days_remaining": ssl_days,
            }
            if failures:
                step_record["error"] = failures[0].get("reason")
                journey_failure_reason = f"Step {idx} '{name}': {failures[0].get('reason')}"

            result["steps"].append(step_record)

            if step_status == "fail":
                aggregate_status = "failed"
                break

        except requests.exceptions.Timeout:
            result["steps"].append({"step": name, "step_number": idx, "status": "timeout",
                                    "method": method, "url": url,
                                    "error": f"Step timed out after {step_timeout}s"})
            aggregate_status = "timeout"
            journey_failure_reason = f"Step {idx} '{name}': timeout"
            break
        except Exception as e:
            result["steps"].append({"step": name, "step_number": idx, "status": "error",
                                    "method": method, "url": url, "error": str(e)[:300]})
            aggregate_status = "error"
            journey_failure_reason = f"Step {idx} '{name}': {str(e)[:120]}"
            break

    result["status"] = aggregate_status
    result["failure_reason"] = journey_failure_reason
    result["extracted_variables"] = variables
    # status_code = last step's status_code (if any)
    last_step = next((s for s in reversed(result["steps"]) if s.get("status_code")), None)
    if last_step:
        result["status_code"] = last_step["status_code"]
    return result


def _json_safe(obj):
    import json as _j
    try:
        return _j.dumps(obj)
    except Exception:
        return str(obj)

