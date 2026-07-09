"""
FalconOps AI - Storage Abstraction
Dev (local /tmp) and Production (S3) backends.
Switch via env var STORAGE_BACKEND = "local" | "s3"
S3 config: REPORTS_S3_BUCKET, AWS_REGION
"""
import os
import io
import logging
import tempfile
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
REPORTS_S3_BUCKET = os.environ.get("REPORTS_S3_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PRESIGN_EXPIRY = int(os.environ.get("S3_PRESIGN_EXPIRY_SECONDS", "3600"))

LOCAL_REPORTS_DIR = "/tmp/falconops_reports"
LOCAL_BRANDING_DIR = "/tmp/falconops_branding"
os.makedirs(LOCAL_REPORTS_DIR, exist_ok=True)
os.makedirs(LOCAL_BRANDING_DIR, exist_ok=True)

_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3", region_name=AWS_REGION)
    return _s3


def _report_key(report_id: str, fmt: str) -> str:
    ext = {"docx": "docx", "xlsx": "xlsx", "pdf": "pdf"}.get(fmt, fmt)
    return f"reports/{report_id}.{ext}"


def _branding_key(tenant_id: str) -> str:
    return f"branding/{tenant_id}.png"


# ============ REPORT FILES ============

def save_report_file(report_id: str, fmt: str, data: bytes) -> str:
    """Persist report bytes. Returns storage path (local path or s3 URI)."""
    if STORAGE_BACKEND == "s3" and REPORTS_S3_BUCKET:
        key = _report_key(report_id, fmt)
        content_type = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(fmt, "application/octet-stream")
        _get_s3().put_object(
            Bucket=REPORTS_S3_BUCKET, Key=key, Body=data,
            ContentType=content_type, ServerSideEncryption="AES256",
        )
        logger.info(f"Uploaded {fmt} to s3://{REPORTS_S3_BUCKET}/{key}")
        return f"s3://{REPORTS_S3_BUCKET}/{key}"

    # Local
    ext = "xlsx" if fmt == "excel" else fmt
    path = os.path.join(LOCAL_REPORTS_DIR, f"{report_id}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_report_file(stored_path: str) -> Optional[bytes]:
    """Read bytes back given the stored path/URI. Used for attachments in emails."""
    if not stored_path:
        return None
    if stored_path.startswith("s3://"):
        try:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            resp = _get_s3().get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            logger.error(f"S3 read failed: {e}")
            return None
    if os.path.exists(stored_path):
        with open(stored_path, "rb") as f:
            return f.read()
    return None


def get_report_download(stored_path: str, filename: str, media_type: str):
    """Return either a local FileResponse or a RedirectResponse to a presigned S3 URL."""
    from fastapi.responses import FileResponse, RedirectResponse
    if stored_path and stored_path.startswith("s3://"):
        try:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            url = _get_s3().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket, "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                    "ResponseContentType": media_type,
                },
                ExpiresIn=PRESIGN_EXPIRY,
            )
            return RedirectResponse(url=url, status_code=302)
        except Exception as e:
            logger.error(f"Presign failed: {e}")
            return None
    if stored_path and os.path.exists(stored_path):
        return FileResponse(stored_path, filename=filename, media_type=media_type)
    return None


def report_file_exists(stored_path: str) -> bool:
    if not stored_path:
        return False
    if stored_path.startswith("s3://"):
        try:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            _get_s3().head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
    return os.path.exists(stored_path)


# ============ BRANDING LOGO ============

def save_branding_logo(tenant_id: str, data: bytes) -> str:
    """Save tenant logo. Returns path/URI."""
    if STORAGE_BACKEND == "s3" and REPORTS_S3_BUCKET:
        key = _branding_key(tenant_id)
        _get_s3().put_object(
            Bucket=REPORTS_S3_BUCKET, Key=key, Body=data,
            ContentType="image/png", ServerSideEncryption="AES256",
        )
        return f"s3://{REPORTS_S3_BUCKET}/{key}"
    path = os.path.join(LOCAL_BRANDING_DIR, f"{tenant_id}.png")
    with open(path, "wb") as f:
        f.write(data)
    return path


def get_branding_logo_local_path(stored_path: str) -> Optional[str]:
    """Reportlab needs a real filesystem path. If S3, download to a temp file and return its path."""
    if not stored_path:
        return None
    if stored_path.startswith("s3://"):
        try:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=LOCAL_BRANDING_DIR)
            resp = _get_s3().get_object(Bucket=bucket, Key=key)
            tmp.write(resp["Body"].read())
            tmp.close()
            return tmp.name
        except Exception as e:
            logger.error(f"Branding download failed: {e}")
            return None
    return stored_path if os.path.exists(stored_path) else None


def branding_exists(stored_path: str) -> bool:
    if not stored_path:
        return False
    if stored_path.startswith("s3://"):
        try:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            _get_s3().head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
    return os.path.exists(stored_path)


def storage_info() -> dict:
    return {
        "backend": STORAGE_BACKEND,
        "s3_bucket": REPORTS_S3_BUCKET if STORAGE_BACKEND == "s3" else None,
        "aws_region": AWS_REGION if STORAGE_BACKEND == "s3" else None,
        "local_reports_dir": LOCAL_REPORTS_DIR if STORAGE_BACKEND == "local" else None,
    }
