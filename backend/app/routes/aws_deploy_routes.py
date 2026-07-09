"""
FalconOps AI — AWS Production Deployment Helper
Generates ready-to-paste bash commands for the operator, plus a connectivity
sanity-check endpoint to verify AWS creds + state before they run terraform.

Designed for use behind an admin-only "Deploy AWS" wizard in the UI.
"""
from __future__ import annotations

import os
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deploy/aws", tags=["AWS Deployment"])


# ─────────────────────────────────────────────────────
# Pydantic
# ─────────────────────────────────────────────────────

class DeployConfig(BaseModel):
    aws_region: str = Field("us-east-1")
    aws_account_id: Optional[str] = None
    ecr_repo_backend: str = Field("falconops-backend")
    ecr_repo_frontend: str = Field("falconops-frontend")
    ecs_cluster: str = Field("falconops-prod")
    ecs_service_backend: str = Field("falconops-backend-svc")
    ecs_service_frontend: str = Field("falconops-frontend-svc")
    s3_reports_bucket: str = Field("falconops-reports-prod")
    image_tag: str = Field("latest")
    docker_build_target: Optional[str] = Field("production")


class TestConnectionRequest(BaseModel):
    aws_region: str = "us-east-1"
    # Optional inline creds (otherwise rely on env)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


# ─────────────────────────────────────────────────────
# Command generation
# ─────────────────────────────────────────────────────

def _generate_steps(cfg: DeployConfig) -> Dict:
    """Build all the bash commands the operator will run, organised by phase."""
    acct = cfg.aws_account_id or "${AWS_ACCOUNT_ID}"
    ecr_backend = f"{acct}.dkr.ecr.{cfg.aws_region}.amazonaws.com/{cfg.ecr_repo_backend}"
    ecr_frontend = f"{acct}.dkr.ecr.{cfg.aws_region}.amazonaws.com/{cfg.ecr_repo_frontend}"

    return {
        "phases": [
            {
                "id": "preflight",
                "title": "0. Pre-flight checks",
                "blurb": "Confirm AWS CLI is wired up and you can read account ID.",
                "commands": [
                    "aws --version",
                    "aws sts get-caller-identity",
                    f"export AWS_REGION={cfg.aws_region}",
                    "export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)",
                ],
            },
            {
                "id": "terraform_init",
                "title": "1. Terraform — init + plan",
                "blurb": "Initialise providers + generate plan. Review before apply.",
                "commands": [
                    "cd /app/infra",
                    "terraform init -upgrade",
                    f"terraform plan -var=\"region={cfg.aws_region}\" -out=tfplan",
                ],
            },
            {
                "id": "terraform_apply",
                "title": "2. Terraform — apply (irreversible)",
                "blurb": "Creates ECR repos, ECS cluster + services, S3 reports bucket, Secrets Manager entries, ALB + ACM.",
                "destructive": True,
                "commands": [
                    "terraform apply tfplan",
                    f"export S3_BUCKET={cfg.s3_reports_bucket}",
                    'echo "✅ Capture the ALB DNS name from terraform output → point Route53 / your DNS at it."',
                ],
            },
            {
                "id": "build_push_backend",
                "title": "3. Build & push backend image",
                "blurb": "Multi-stage Docker build → tag → push to ECR.",
                "commands": [
                    f"aws ecr get-login-password --region {cfg.aws_region} | docker login --username AWS --password-stdin {ecr_backend.split('/')[0]}",
                    f"docker build --target {cfg.docker_build_target or 'production'} -t falconops-backend:latest /app/backend",
                    f"docker tag falconops-backend:latest {ecr_backend}:{cfg.image_tag}",
                    f"docker push {ecr_backend}:{cfg.image_tag}",
                ],
            },
            {
                "id": "build_push_frontend",
                "title": "4. Build & push frontend image",
                "blurb": "Yarn install → React build → multi-stage nginx image → push.",
                "commands": [
                    "docker build -t falconops-frontend:latest /app/frontend",
                    f"docker tag falconops-frontend:latest {ecr_frontend}:{cfg.image_tag}",
                    f"docker push {ecr_frontend}:{cfg.image_tag}",
                ],
            },
            {
                "id": "secrets",
                "title": "5. Hydrate Secrets Manager",
                "blurb": "Store live secrets — read from your local .env files. NEVER commit these.",
                "commands": [
                    'aws secretsmanager put-secret-value --secret-id falconops/jwt --secret-string "$(grep JWT_SECRET_KEY /app/backend/.env | cut -d= -f2-)"',
                    'aws secretsmanager put-secret-value --secret-id falconops/emergent-llm --secret-string "$(grep EMERGENT_LLM_KEY /app/backend/.env | cut -d= -f2-)"',
                    'aws secretsmanager put-secret-value --secret-id falconops/resend --secret-string "$(grep RESEND_API_KEY /app/backend/.env | cut -d= -f2-)"',
                    'aws secretsmanager put-secret-value --secret-id falconops/stripe --secret-string "$(grep STRIPE_API_KEY /app/backend/.env | cut -d= -f2-)"',
                    'aws secretsmanager put-secret-value --secret-id falconops/mongo --secret-string "$(grep MONGO_URL /app/backend/.env | cut -d= -f2-)"',
                ],
            },
            {
                "id": "flip_storage",
                "title": "6. Flip STORAGE_BACKEND=s3 + roll ECS",
                "blurb": "Switch from local /tmp to S3 + force ECS to pull the new image.",
                "commands": [
                    f"aws ecs update-service --cluster {cfg.ecs_cluster} --service {cfg.ecs_service_backend} --force-new-deployment --region {cfg.aws_region}",
                    f"aws ecs update-service --cluster {cfg.ecs_cluster} --service {cfg.ecs_service_frontend} --force-new-deployment --region {cfg.aws_region}",
                    "echo 'ECS rollout started — watch with:'",
                    f"echo \"aws ecs describe-services --cluster {cfg.ecs_cluster} --services {cfg.ecs_service_backend} --region {cfg.aws_region} --query 'services[0].deployments'\"",
                ],
            },
            {
                "id": "validate",
                "title": "7. Validate live deployment",
                "blurb": "Health checks on the deployed service.",
                "commands": [
                    'export FALCONOPS_URL=$(terraform output -raw alb_dns_name 2>/dev/null || echo "https://your-falconops-host.example.com")',
                    'curl -fsSL "$FALCONOPS_URL/api/health" | jq .',
                    'curl -fsSL "$FALCONOPS_URL/api/health" | jq .storage   # should show {"backend": "s3", ...}',
                    'echo "✅ FalconOps AI is live on AWS"',
                ],
            },
        ],
        "summary": {
            "region": cfg.aws_region,
            "account_id_hint": cfg.aws_account_id or "(read via sts:GetCallerIdentity at pre-flight)",
            "ecs_cluster": cfg.ecs_cluster,
            "image_tag": cfg.image_tag,
            "s3_bucket": cfg.s3_reports_bucket,
        },
        "post_flip_env": {
            "STORAGE_BACKEND": "s3",
            "REPORTS_S3_BUCKET": cfg.s3_reports_bucket,
            "AWS_REGION": cfg.aws_region,
        },
        "rollback_command": (
            f"aws ecs update-service --cluster {cfg.ecs_cluster} --service {cfg.ecs_service_backend} "
            f"--task-definition $(aws ecs describe-services --cluster {cfg.ecs_cluster} "
            f"--services {cfg.ecs_service_backend} --query 'services[0].deployments[1].taskDefinition' "
            f"--output text) --region {cfg.aws_region}"
        ),
    }


@router.post("/plan")
async def plan_deployment(cfg: DeployConfig, admin_user: dict = Depends(require_admin)):
    """Generate the full ordered list of bash commands for the operator to copy-paste."""
    return _generate_steps(cfg)


@router.post("/test-connection")
async def test_connection(req: TestConnectionRequest, admin_user: dict = Depends(require_admin)):
    """Best-effort AWS connectivity check — runs `aws sts get-caller-identity` locally
    if the CLI is installed. This is a fast smoke test before the operator commits
    to `terraform apply`."""
    env = {**os.environ}
    if req.aws_access_key_id and req.aws_secret_access_key:
        env["AWS_ACCESS_KEY_ID"] = req.aws_access_key_id
        env["AWS_SECRET_ACCESS_KEY"] = req.aws_secret_access_key
    env["AWS_REGION"] = req.aws_region or "us-east-1"

    try:
        proc = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--region", env["AWS_REGION"]],
            capture_output=True, text=True, timeout=15, env=env,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "aws CLI not found in this environment — operators must install awscli on their machine before running the deployment commands.",
            "hint": "brew install awscli  # macOS\nsudo apt install -y awscli  # Debian/Ubuntu",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "aws sts call timed out after 15s — check VPN / network"}

    if proc.returncode != 0:
        return {
            "ok": False,
            "exit_code": proc.returncode,
            "stderr": (proc.stderr or "").strip()[:600],
            "hint": "Run `aws configure` to set up credentials, or paste an access key + secret in this form for a temporary check.",
        }
    return {
        "ok": True,
        "identity": (proc.stdout or "").strip(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def deployment_health(admin_user: dict = Depends(require_admin)):
    """Report what's wired up in the local environment for an AWS deploy."""
    env_present = {
        "AWS_REGION": bool(os.environ.get("AWS_REGION")),
        "AWS_ACCESS_KEY_ID": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
        "STORAGE_BACKEND": os.environ.get("STORAGE_BACKEND", "local"),
        "REPORTS_S3_BUCKET": os.environ.get("REPORTS_S3_BUCKET"),
        "EMERGENT_LLM_KEY": bool(os.environ.get("EMERGENT_LLM_KEY")),
        "RESEND_API_KEY": bool(os.environ.get("RESEND_API_KEY")),
        "STRIPE_API_KEY": bool(os.environ.get("STRIPE_API_KEY")),
    }

    cli_present = False
    try:
        proc = subprocess.run(["aws", "--version"], capture_output=True, text=True, timeout=5)
        cli_present = proc.returncode == 0
    except Exception:
        pass

    terraform_present = False
    try:
        proc = subprocess.run(["terraform", "version"], capture_output=True, text=True, timeout=5)
        terraform_present = proc.returncode == 0
    except Exception:
        pass

    return {
        "env": env_present,
        "tooling": {
            "aws_cli": cli_present,
            "terraform": terraform_present,
        },
        "infra_dir_present": os.path.isdir("/app/infra"),
        "playbook_present": os.path.isfile("/app/DEPLOY_AWS.md"),
    }
