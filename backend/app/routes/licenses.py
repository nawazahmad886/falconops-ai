"""
FalconOps AI - Licensing Routes
License management, validation, and application download
"""
import os
import uuid
import tarfile
import tempfile
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..core.database import db
from ..utils.auth import require_admin, require_auth
from ..services.licensing_service import (
    generate_license_key,
    validate_license_key,
    store_license,
    get_current_license,
    revoke_license,
    get_license_plans,
    check_feature_access,
    LICENSE_PLANS
)

router = APIRouter(prefix="/api/licenses", tags=["Licensing"])


# ======================== SCHEMAS ========================

class LicenseGenerateRequest(BaseModel):
    """Request to generate a new license"""
    organization: str = Field(..., min_length=1, description="Organization name")
    license_type: str = Field(..., description="License type: trial, standard, professional, enterprise")
    customer_email: str = Field(..., description="Customer email")
    max_users: Optional[int] = None
    max_servers: Optional[int] = None
    max_monitors: Optional[int] = None
    valid_days: Optional[int] = None
    features: Optional[List[str]] = None


class LicenseActivateRequest(BaseModel):
    """Request to activate a license"""
    license_key: str = Field(..., min_length=10, description="License key to activate")


class LicenseValidateRequest(BaseModel):
    """Request to validate a license"""
    license_key: str = Field(..., min_length=10, description="License key to validate")


class LicenseResponse(BaseModel):
    """License response"""
    license_id: str
    organization: str
    license_type: str
    customer_email: Optional[str] = None
    max_users: int
    max_servers: int
    max_monitors: int
    features: List[str]
    expires_at: str
    days_remaining: Optional[int] = None
    status: Optional[str] = None


# ======================== LICENSE MANAGEMENT ENDPOINTS ========================

@router.post("/generate", response_model=dict)
async def generate_license(request: LicenseGenerateRequest, admin_user: dict = Depends(require_admin)):
    """Generate a new license key (Admin only)"""
    
    # Validate license type
    if request.license_type not in LICENSE_PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid license type. Must be one of: {list(LICENSE_PLANS.keys())}")
    
    # Get plan defaults
    plan = LICENSE_PLANS[request.license_type]
    
    # Generate license
    license_data = generate_license_key(
        organization=request.organization,
        license_type=request.license_type,
        max_users=request.max_users or plan["max_users"],
        max_servers=request.max_servers or plan["max_servers"],
        max_monitors=request.max_monitors or plan["max_monitors"],
        valid_days=request.valid_days or plan["valid_days"],
        features=request.features
    )
    
    # Store in database for tracking
    license_record = {
        "id": license_data["license_id"],
        "license_key": license_data["license_key"],
        "organization": request.organization,
        "customer_email": request.customer_email,
        "type": request.license_type,
        "max_users": license_data["max_users"],
        "max_servers": license_data["max_servers"],
        "max_monitors": license_data["max_monitors"],
        "features": license_data["features"],
        "expires_at": license_data["expires_at"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin_user["id"],
        "status": "generated"
    }
    
    await db.license_records.insert_one(license_record)
    
    return {
        "success": True,
        "license_key": license_data["license_key"],
        "license_id": license_data["license_id"],
        "organization": request.organization,
        "customer_email": request.customer_email,
        "type": request.license_type,
        "expires_at": license_data["expires_at"],
        "features": license_data["features"]
    }


@router.post("/validate")
async def validate_license(request: LicenseValidateRequest):
    """Validate a license key"""
    result = validate_license_key(request.license_key)
    return result


@router.post("/activate")
async def activate_license(request: LicenseActivateRequest, user: dict = Depends(require_admin)):
    """Activate a license for this installation (Admin only)"""
    result = await store_license(request.license_key)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to activate license"))
    
    return result


@router.get("/current")
async def get_active_license(user: dict = Depends(require_auth)):
    """Get the current active license"""
    license_data = await get_current_license()
    
    if not license_data:
        return {"active": False, "message": "No active license"}
    
    return {
        "active": True,
        "license": license_data
    }


@router.delete("/revoke")
async def revoke_current_license(admin_user: dict = Depends(require_admin)):
    """Revoke the current license (Admin only)"""
    result = await revoke_license()
    return result


@router.get("/plans")
async def get_available_plans():
    """Get available license plans"""
    return {
        "plans": get_license_plans()
    }


@router.get("/records")
async def list_license_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """List all generated license records (Admin only)"""
    records = await db.license_records.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.license_records.count_documents({})
    
    return {
        "records": records,
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ======================== APPLICATION DOWNLOAD ENDPOINTS ========================

def create_source_archive(include_docker: bool = True, archive_format: str = "tar.gz") -> str:
    """Create a comprehensive enterprise deployment archive (tar.gz or zip)"""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    archive_name = f"falconops-ai-enterprise-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    archive_dir = os.path.join(temp_dir, archive_name)
    os.makedirs(archive_dir)
    
    # Paths to include
    base_path = Path("/app")
    
    # Backend directory - include ALL files for production
    backend_src = base_path / "backend"
    backend_dst = Path(archive_dir) / "backend"
    if backend_src.exists():
        shutil.copytree(
            backend_src, 
            backend_dst,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env', 'venv', 'env', '.git', '.pytest_cache')
        )

    # Vendor private wheels — ship offline-installable dependencies alongside the backend
    vendor_src = base_path / "backend" / "vendor"
    vendor_dst = backend_dst / "vendor"
    if vendor_src.exists():
        # Already copied above with the rest of backend; this is a no-op safety net
        if not vendor_dst.exists():
            shutil.copytree(vendor_src, vendor_dst)
    
    # Frontend directory - include source for building
    frontend_src = base_path / "frontend"
    frontend_dst = Path(archive_dir) / "frontend"
    if frontend_src.exists():
        shutil.copytree(
            frontend_src, 
            frontend_dst,
            ignore=shutil.ignore_patterns('node_modules', '.env', '.git', '*.log', 'build', '.cache')
        )
    
    # Create comprehensive database setup scripts
    create_database_scripts(archive_dir)
    
    # Create systemd service files for production
    create_systemd_services(archive_dir)
    
    # Create Kubernetes deployment files
    create_kubernetes_configs(archive_dir)
    
    # Create .env.example files
    backend_env_example = """# FalconOps AI - Backend Environment Configuration
# Copy this file to backend/.env and configure your settings.
# The bundled install.sh does this automatically — only edit values, never key names.

# ════════════════════ REQUIRED ════════════════════
MONGO_URL=mongodb://mongo:27017
DB_NAME=falconops
JWT_SECRET_KEY=change-this-to-a-secure-random-string-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
# Production-safe: comma-separated list of allowed origins. Use "*" only for development.
CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:8001

# ════════════════════ ENVIRONMENT MODE ════════════════════
ENVIRONMENT=production
APP_URL=http://localhost
PUBLIC_BASE_URL=http://localhost
REDIS_URL=redis://redis:6379

# ════════════════════ LICENSING (ON-PREMISE) ════════════════════
LICENSE_KEY=
LICENSE_SECRET=change-this-to-match-the-secret-given-with-your-license
BUNDLE_TOKEN_TTL_DAYS=7
BUNDLE_TOKEN_MAX_USES=3

# ════════════════════ AI / LLM PROVIDERS ════════════════════
# FalconOps supports pluggable LLM providers via /app/backend/app/services/llm_provider_service.py
# Configure ONE of the following — leave others blank to disable that provider.

# Option A — Emergent Universal LLM Key (covers Claude, GPT, Gemini). Requires the
#            emergentintegrations wheel (shipped under backend/vendor/ for air-gapped installs).
EMERGENT_LLM_KEY=

# Option B — OpenAI (gpt-4o-mini / gpt-5.x). Stand-alone API key.
OPENAI_API_KEY=

# Option C — Anthropic (Claude). Stand-alone API key.
ANTHROPIC_API_KEY=

# Option D — Google Gemini. Stand-alone API key.
GOOGLE_API_KEY=

# Option E — Local on-prem Ollama (FREE, no key). Set provider=ollama in Admin Console.
OLLAMA_BASE_URL=http://localhost:11434

# Optional explicit override; if blank, FalconOps auto-detects in this order:
# ollama > openai > anthropic > gemini > emergent > rule_based
LLM_PROVIDER=

# ════════════════════ EMAIL (Reports, OTP, Lead Notifications) ════════════════════
# Obtain at https://resend.com/api-keys (sandbox mode works for testing)
RESEND_API_KEY=
# IMPORTANT: backend reads SENDER_EMAIL (not DEFAULT_SENDER_EMAIL).
SENDER_EMAIL=onboarding@resend.dev
ALERT_EMAIL=alerts@yourcompany.com
SALES_EMAIL=sales@yourcompany.com
# Optional secondary email provider
SENDGRID_API_KEY=

# ════════════════════ NOTIFICATION CHANNELS (alerts/threats fan-out) ════════════════════
# Optional — used by connector_dispatcher.py as defaults if no integration configured in DB.
TEAMS_WEBHOOK_URL=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=

# ════════════════════ PAYMENTS (Stripe billing - optional) ════════════════════
STRIPE_API_KEY=
STRIPE_WEBHOOK_SECRET=

# ════════════════════ STORAGE (local = /tmp, or s3) ════════════════════
STORAGE_BACKEND=local
REPORTS_S3_BUCKET=
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# ════════════════════ AI INTELLIGENCE LAYER / RAG ════════════════════
# Embedded ChromaDB vector store for the Incident Analysis Agent memory.
# Defaults to <backend>/data/chroma — override for a dedicated data volume.
CHROMA_PATH=
# Pre-flight prompt-injection guard on all LLM calls (true|false, default true)
LLM_PREFLIGHT_INJECTION_BLOCK=true

# ════════════════════ ONEAGENT (observability agent downloads) ════════════════════
# Directory containing OneAgent binaries + source tarball served at
# /api/oneagent/download/*. Defaults to <backend>/static/agents/oneagent.
ONEAGENT_DIR=

# ════════════════════ POST-INSTALL VERIFICATION ════════════════════
# After the stack is up, log in and call GET /api/self-monitor/env-check
# to confirm every module sees the env vars it needs (no secrets echoed).
"""

    frontend_env_example = """# FalconOps AI - Frontend Environment Configuration
# IMPORTANT: React env vars are baked at BUILD time (yarn build).
# If you change REACT_APP_BACKEND_URL, you must rebuild: `docker-compose build frontend`
# OR `yarn build` for native installs.

# For docker-compose-based install (default) → all traffic routes via nginx on port 80
REACT_APP_BACKEND_URL=http://localhost

# For native install without nginx, point directly at backend
# REACT_APP_BACKEND_URL=http://localhost:8001

ESLINT_NO_DEV_ERRORS=true
DISABLE_ESLINT_PLUGIN=true
"""
    
    with open(backend_dst / ".env.example", "w") as f:
        f.write(backend_env_example)
    with open(backend_dst / ".env", "w") as f:
        f.write(backend_env_example)  # prefilled default so the stack boots
    
    with open(frontend_dst / ".env.example", "w") as f:
        f.write(frontend_env_example)
    with open(frontend_dst / ".env", "w") as f:
        f.write(frontend_env_example)
    
    # Add Docker configuration if requested
    if include_docker:
        create_docker_files(archive_dir)
    
    # Create README + PREREQUISITES + QUICK_START
    create_readme(archive_dir, include_docker)
    create_prerequisites_doc(archive_dir)
    create_quickstart_doc(archive_dir)
    create_podman_assets(archive_dir)
    
    # Create installation scripts
    create_install_script(archive_dir)
    create_linux_bootstrap_script(archive_dir)
    create_enterprise_assets(archive_dir)
    
    # Build archive in requested format
    if archive_format == "zip":
        archive_path = os.path.join(temp_dir, f"{archive_name}.zip")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, _dirs, files in os.walk(archive_dir):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, os.path.dirname(archive_dir))
                    zf.write(abs_path, rel_path)
    else:
        archive_path = os.path.join(temp_dir, f"{archive_name}.tar.gz")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(archive_dir, arcname=archive_name)
    
    # Cleanup the extracted directory, keep archive
    shutil.rmtree(archive_dir)
    
    return archive_path


# Backwards-compatible alias
def create_source_tarball(include_docker: bool = True) -> str:
    return create_source_archive(include_docker=include_docker, archive_format="tar.gz")


def create_database_scripts(archive_dir: str):
    """Create database initialization and migration scripts"""
    
    scripts_dir = Path(archive_dir) / "scripts" / "database"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    
    # MongoDB initialization script
    mongo_init = '''#!/bin/bash
# FalconOps AI - MongoDB Initialization Script

MONGO_HOST=${MONGO_HOST:-localhost}
MONGO_PORT=${MONGO_PORT:-27017}
DB_NAME=${DB_NAME:-falconops}

echo "=========================================="
echo "   FalconOps AI - Database Setup"
echo "=========================================="

# Wait for MongoDB to be ready
echo "Waiting for MongoDB..."
until mongosh --host $MONGO_HOST --port $MONGO_PORT --eval "db.adminCommand('ping')" &>/dev/null; do
    sleep 2
done
echo "[✓] MongoDB is ready"

# Create database and collections
mongosh --host $MONGO_HOST --port $MONGO_PORT <<EOF
use $DB_NAME

// Create collections with validation
db.createCollection("users", {
    validator: {
        \\$jsonSchema: {
            bsonType: "object",
            required: ["email", "password_hash", "role"],
            properties: {
                email: { bsonType: "string" },
                password_hash: { bsonType: "string" },
                role: { enum: ["admin", "operator", "viewer"] }
            }
        }
    }
})

db.createCollection("alerts")
db.createCollection("incidents")
db.createCollection("monitors")
db.createCollection("runbooks")
db.createCollection("health_rules")
db.createCollection("metrics")
db.createCollection("logs")
db.createCollection("topology_nodes")
db.createCollection("topology_edges")
db.createCollection("license_records")
db.createCollection("audit_logs")

// Create indexes for performance
db.users.createIndex({ "email": 1 }, { unique: true })
db.alerts.createIndex({ "created_at": -1 })
db.alerts.createIndex({ "status": 1, "severity": 1 })
db.alerts.createIndex({ "tenant_id": 1 })
db.incidents.createIndex({ "created_at": -1 })
db.incidents.createIndex({ "status": 1 })
db.incidents.createIndex({ "tenant_id": 1 })
db.monitors.createIndex({ "name": 1 })
db.runbooks.createIndex({ "name": 1 })
db.health_rules.createIndex({ "enabled": 1 })
db.metrics.createIndex({ "name": 1, "timestamp": -1 })
db.metrics.createIndex({ "tenant_id": 1, "timestamp": -1 })
db.logs.createIndex({ "timestamp": -1 })
db.logs.createIndex({ "level": 1, "timestamp": -1 })
db.logs.createIndex({ "trace_id": 1 })
db.topology_nodes.createIndex({ "name": 1, "environment": 1 })
db.audit_logs.createIndex({ "timestamp": -1 })

// Create default admin user (password: Admin@123)
db.users.insertOne({
    id: "admin-001",
    email: "admin@falconapps.com",
    password_hash: "\\$2b\\$12\\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qOOPtLJGwPmuWS",
    role: "admin",
    name: "System Administrator",
    created_at: new Date().toISOString()
})

print("\\n[✓] Database initialized successfully!")
print("[✓] Default admin user created: admin@falconapps.com / Admin@123")
EOF

echo ""
echo "=========================================="
echo "   Database Setup Complete!"
echo "=========================================="
'''
    
    with open(scripts_dir / "init-mongodb.sh", "w") as f:
        f.write(mongo_init)
    os.chmod(scripts_dir / "init-mongodb.sh", 0o755)
    
    # Backup script
    backup_script = '''#!/bin/bash
# FalconOps AI - Database Backup Script

MONGO_HOST=${MONGO_HOST:-localhost}
MONGO_PORT=${MONGO_PORT:-27017}
DB_NAME=${DB_NAME:-falconops}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/falconops}
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "Creating backup of $DB_NAME..."
mongodump --host $MONGO_HOST --port $MONGO_PORT --db $DB_NAME --out "$BACKUP_DIR/backup_$DATE"

# Compress backup
cd $BACKUP_DIR
tar -czf "backup_$DATE.tar.gz" "backup_$DATE"
rm -rf "backup_$DATE"

# Keep only last 7 backups
ls -t backup_*.tar.gz | tail -n +8 | xargs -r rm

echo "Backup completed: $BACKUP_DIR/backup_$DATE.tar.gz"
'''
    
    with open(scripts_dir / "backup.sh", "w") as f:
        f.write(backup_script)
    os.chmod(scripts_dir / "backup.sh", 0o755)
    
    # Restore script
    restore_script = '''#!/bin/bash
# FalconOps AI - Database Restore Script

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_file.tar.gz>"
    exit 1
fi

MONGO_HOST=${MONGO_HOST:-localhost}
MONGO_PORT=${MONGO_PORT:-27017}
DB_NAME=${DB_NAME:-falconops}
BACKUP_FILE=$1
TEMP_DIR=$(mktemp -d)

echo "Extracting backup..."
tar -xzf "$BACKUP_FILE" -C $TEMP_DIR

BACKUP_DIR=$(find $TEMP_DIR -type d -name "$DB_NAME" | head -1)
if [ -z "$BACKUP_DIR" ]; then
    BACKUP_DIR=$(find $TEMP_DIR -type d -name "backup_*" | head -1)/$DB_NAME
fi

echo "Restoring database from $BACKUP_DIR..."
mongorestore --host $MONGO_HOST --port $MONGO_PORT --db $DB_NAME --drop "$BACKUP_DIR"

rm -rf $TEMP_DIR
echo "Restore completed!"
'''
    
    with open(scripts_dir / "restore.sh", "w") as f:
        f.write(restore_script)
    os.chmod(scripts_dir / "restore.sh", 0o755)


def create_systemd_services(archive_dir: str):
    """Create systemd service files for production deployment"""
    
    systemd_dir = Path(archive_dir) / "scripts" / "systemd"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    
    # Backend service
    backend_service = '''[Unit]
Description=FalconOps AI Backend API
After=network.target mongodb.service
Wants=mongodb.service

[Service]
Type=simple
User=falconops
Group=falconops
WorkingDirectory=/opt/falconops/backend
Environment=PATH=/opt/falconops/backend/venv/bin:/usr/local/bin:/usr/bin
EnvironmentFile=/opt/falconops/backend/.env
ExecStart=/opt/falconops/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=append:/var/log/falconops/backend.log
StandardError=append:/var/log/falconops/backend-error.log

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/falconops /var/log/falconops
PrivateTmp=true

[Install]
WantedBy=multi-user.target
'''
    
    with open(systemd_dir / "falconops-backend.service", "w") as f:
        f.write(backend_service)
    
    # Frontend Nginx site config
    nginx_site = '''# FalconOps AI - Nginx Site Configuration
# Copy to /etc/nginx/sites-available/falconops

server {
    listen 80;
    server_name falconops.example.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name falconops.example.com;
    
    # SSL Configuration (update paths to your certificates)
    ssl_certificate /etc/ssl/certs/falconops.crt;
    ssl_certificate_key /etc/ssl/private/falconops.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Logging
    access_log /var/log/nginx/falconops-access.log;
    error_log /var/log/nginx/falconops-error.log;
    
    # Frontend static files
    root /opt/falconops/frontend/build;
    index index.html;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;
    
    # Frontend routes (React Router)
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API proxy
    location /api {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
    
    # WebSocket proxy
    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
    
    # Static assets caching
    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
'''
    
    with open(systemd_dir / "falconops-nginx.conf", "w") as f:
        f.write(nginx_site)
    
    # Installation instructions for systemd
    systemd_readme = '''# FalconOps AI - Systemd Installation Guide

## Prerequisites
- Ubuntu 20.04+ or RHEL/CentOS 8+
- MongoDB 6.0+
- Nginx
- Python 3.11+
- Node.js 18+ (for building frontend)

## Installation Steps

### 1. Create system user
```bash
sudo useradd -r -s /bin/false falconops
sudo mkdir -p /opt/falconops /var/log/falconops
sudo chown -R falconops:falconops /opt/falconops /var/log/falconops
```

### 2. Extract application
```bash
sudo tar -xzf falconops-ai-enterprise-*.tar.gz -C /opt/
sudo mv /opt/falconops-ai-enterprise-*/* /opt/falconops/
```

### 3. Setup Backend
```bash
cd /opt/falconops/backend
sudo -u falconops python3 -m venv venv
sudo -u falconops ./venv/bin/pip install -r requirements.txt
sudo cp .env.example .env
sudo nano .env  # Configure your settings
```

### 4. Setup Frontend
```bash
cd /opt/falconops/frontend
# If build folder doesn't exist:
yarn install
yarn build
```

### 5. Initialize Database
```bash
cd /opt/falconops/scripts/database
./init-mongodb.sh
```

### 6. Install Services
```bash
sudo cp /opt/falconops/scripts/systemd/falconops-backend.service /etc/systemd/system/
sudo cp /opt/falconops/scripts/systemd/falconops-nginx.conf /etc/nginx/sites-available/falconops
sudo ln -s /etc/nginx/sites-available/falconops /etc/nginx/sites-enabled/
sudo systemctl daemon-reload
sudo systemctl enable falconops-backend
sudo systemctl start falconops-backend
sudo systemctl restart nginx
```

### 7. Verify Installation
```bash
sudo systemctl status falconops-backend
curl http://localhost:8001/api/health
```

## Management Commands
```bash
# Start/Stop/Restart
sudo systemctl start falconops-backend
sudo systemctl stop falconops-backend
sudo systemctl restart falconops-backend

# View logs
sudo journalctl -u falconops-backend -f
tail -f /var/log/falconops/backend.log

# Backup database
/opt/falconops/scripts/database/backup.sh
```
'''
    
    with open(systemd_dir / "README.md", "w") as f:
        f.write(systemd_readme)


def create_kubernetes_configs(archive_dir: str):
    """Create Kubernetes deployment configurations"""
    
    k8s_dir = Path(archive_dir) / "kubernetes"
    k8s_dir.mkdir(parents=True, exist_ok=True)
    
    # Namespace
    namespace = '''apiVersion: v1
kind: Namespace
metadata:
  name: falconops
  labels:
    app: falconops
'''
    
    with open(k8s_dir / "00-namespace.yaml", "w") as f:
        f.write(namespace)
    
    # ConfigMap
    configmap = '''apiVersion: v1
kind: ConfigMap
metadata:
  name: falconops-config
  namespace: falconops
data:
  MONGO_URL: "mongodb://mongodb-service:27017"
  DB_NAME: "falconops"
  JWT_ALGORITHM: "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES: "1440"
  CORS_ORIGINS: "*"
'''
    
    with open(k8s_dir / "01-configmap.yaml", "w") as f:
        f.write(configmap)
    
    # Secrets template
    secrets = '''apiVersion: v1
kind: Secret
metadata:
  name: falconops-secrets
  namespace: falconops
type: Opaque
stringData:
  JWT_SECRET_KEY: "CHANGE-THIS-TO-A-SECURE-KEY"
  LICENSE_KEY: "YOUR-LICENSE-KEY-HERE"
  # Optional
  RESEND_API_KEY: ""
  EMERGENT_LLM_KEY: ""
  OPENAI_API_KEY: ""
  ANTHROPIC_API_KEY: ""
'''
    
    with open(k8s_dir / "02-secrets.yaml", "w") as f:
        f.write(secrets)
    
    # MongoDB StatefulSet
    mongodb = '''apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: falconops
spec:
  serviceName: mongodb
  replicas: 1
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
      - name: mongodb
        image: mongo:6.0
        ports:
        - containerPort: 27017
        volumeMounts:
        - name: mongodb-data
          mountPath: /data/db
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: mongodb-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: mongodb-service
  namespace: falconops
spec:
  selector:
    app: mongodb
  ports:
  - port: 27017
    targetPort: 27017
  clusterIP: None
'''
    
    with open(k8s_dir / "03-mongodb.yaml", "w") as f:
        f.write(mongodb)
    
    # Backend Deployment
    backend = '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: falconops-backend
  namespace: falconops
spec:
  replicas: 2
  selector:
    matchLabels:
      app: falconops-backend
  template:
    metadata:
      labels:
        app: falconops-backend
    spec:
      containers:
      - name: backend
        image: falconops/backend:latest
        ports:
        - containerPort: 8001
        envFrom:
        - configMapRef:
            name: falconops-config
        - secretRef:
            name: falconops-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: falconops-backend-service
  namespace: falconops
spec:
  selector:
    app: falconops-backend
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP
'''
    
    with open(k8s_dir / "04-backend.yaml", "w") as f:
        f.write(backend)
    
    # Frontend Deployment
    frontend = '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: falconops-frontend
  namespace: falconops
spec:
  replicas: 2
  selector:
    matchLabels:
      app: falconops-frontend
  template:
    metadata:
      labels:
        app: falconops-frontend
    spec:
      containers:
      - name: frontend
        image: falconops/frontend:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: falconops-frontend-service
  namespace: falconops
spec:
  selector:
    app: falconops-frontend
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
'''
    
    with open(k8s_dir / "05-frontend.yaml", "w") as f:
        f.write(frontend)
    
    # Ingress
    ingress = '''apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: falconops-ingress
  namespace: falconops
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - falconops.example.com
    secretName: falconops-tls
  rules:
  - host: falconops.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: falconops-backend-service
            port:
              number: 8001
      - path: /
        pathType: Prefix
        backend:
          service:
            name: falconops-frontend-service
            port:
              number: 80
'''
    
    with open(k8s_dir / "06-ingress.yaml", "w") as f:
        f.write(ingress)
    
    # HPA
    hpa = '''apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: falconops-backend-hpa
  namespace: falconops
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: falconops-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
'''
    
    with open(k8s_dir / "07-hpa.yaml", "w") as f:
        f.write(hpa)
    
    # Kubernetes README
    k8s_readme = '''# FalconOps AI - Kubernetes Deployment Guide

## Prerequisites
- Kubernetes cluster (1.25+)
- kubectl configured
- Helm 3 (optional, for cert-manager)
- Ingress Controller (nginx-ingress recommended)

## Quick Start

### 1. Build and Push Docker Images
```bash
# Backend
cd backend
docker build -t your-registry/falconops-backend:latest .
docker push your-registry/falconops-backend:latest

# Frontend
cd frontend
docker build -t your-registry/falconops-frontend:latest .
docker push your-registry/falconops-frontend:latest
```

### 2. Update Image References
Edit `04-backend.yaml` and `05-frontend.yaml` to use your registry.

### 3. Configure Secrets
Edit `02-secrets.yaml` with your actual values:
- JWT_SECRET_KEY: Generate a secure random string
- LICENSE_KEY: Your FalconOps license key

### 4. Deploy
```bash
kubectl apply -f kubernetes/
```

### 5. Verify Deployment
```bash
kubectl get pods -n falconops
kubectl get services -n falconops
kubectl get ingress -n falconops
```

## Production Recommendations

### Storage
- Use managed MongoDB (Atlas, DocumentDB) for production
- Configure persistent volumes for data

### Security
- Enable network policies
- Use pod security policies
- Rotate secrets regularly

### Monitoring
- Deploy Prometheus + Grafana for metrics
- Configure alerts for pod health

### Scaling
- Adjust HPA settings based on load
- Consider dedicated node pools for FalconOps

## Troubleshooting
```bash
# Check pod logs
kubectl logs -f deployment/falconops-backend -n falconops

# Describe pod for events
kubectl describe pod <pod-name> -n falconops

# Access backend shell
kubectl exec -it deployment/falconops-backend -n falconops -- /bin/bash
```
'''
    
    with open(k8s_dir / "README.md", "w") as f:
        f.write(k8s_readme)


def create_docker_files(archive_dir: str):
    """Create Docker and docker-compose configuration files"""
    
    # Backend Dockerfile — production-grade, air-gap friendly, non-root user
    backend_dockerfile = """# FalconOps AI — Backend Dockerfile (multi-stage, vendor-wheel aware)
FROM python:3.11-slim AS builder

WORKDIR /build

# Build tooling for native wheels (cryptography, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \\
        gcc g++ libffi-dev libssl-dev curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Bring in requirements + the vendor wheel cache
COPY requirements.txt .
COPY vendor/ ./vendor/

# Install: prefer vendored wheels (offline), fall back to PyPI if available.
RUN python -m pip install --upgrade pip wheel \\
 && if [ -d ./vendor ] && ls ./vendor/*.whl >/dev/null 2>&1; then \\
        pip install --no-cache-dir --find-links=./vendor -r requirements.txt || \\
        pip install --no-cache-dir --find-links=./vendor ./vendor/*.whl; \\
    else \\
        pip install --no-cache-dir -r requirements.txt; \\
    fi

# ── Runtime image ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && useradd --create-home --uid 1001 --shell /bin/bash falcon

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=falcon:falcon . .

USER falcon
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
  CMD curl -fsS http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
"""
    
    # Frontend Dockerfile
    frontend_dockerfile = """# FalconOps AI - Frontend Dockerfile
FROM node:18-alpine as build

WORKDIR /app

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy source code
COPY . .

# Build the application
RUN yarn build

# Production stage
FROM nginx:alpine

# Copy build files
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
"""
    
    # Nginx configuration for frontend
    nginx_conf = """server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Handle React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (optional - configure if running on same host)
    location /api {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
"""
    
    # Docker Compose — production-hardened with healthchecks + restart policies
    docker_compose = """version: '3.8'

x-restart: &restart
  restart: unless-stopped

x-logging: &logging
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "5"

services:
  # ── MongoDB ─────────────────────────────────────────────────────────────
  mongodb:
    image: mongo:6.0
    container_name: falconops-mongodb
    <<: [*restart, *logging]
    environment:
      MONGO_INITDB_DATABASE: ${DB_NAME:-falconops}
    volumes:
      - mongodb_data:/data/db
      - ./scripts/database/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js:ro
    networks:
      - falconops-network
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.runCommand('ping').ok"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  # ── Backend API ─────────────────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: falconops/backend:latest
    container_name: falconops-backend
    <<: [*restart, *logging]
    env_file: ./backend/.env
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=${DB_NAME:-falconops}
    networks:
      - falconops-network
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8001/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  # ── Frontend ───────────────────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    image: falconops/frontend:latest
    container_name: falconops-frontend
    <<: [*restart, *logging]
    ports:
      - "${FRONTEND_PORT:-80}:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - falconops-network
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O- http://localhost/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

volumes:
  mongodb_data:
    driver: local

networks:
  falconops-network:
    driver: bridge
"""
    
    # Write files
    backend_path = Path(archive_dir) / "backend"
    frontend_path = Path(archive_dir) / "frontend"
    
    with open(backend_path / "Dockerfile", "w") as f:
        f.write(backend_dockerfile)
    
    with open(frontend_path / "Dockerfile", "w") as f:
        f.write(frontend_dockerfile)
    
    with open(frontend_path / "nginx.conf", "w") as f:
        f.write(nginx_conf)
    
    with open(Path(archive_dir) / "docker-compose.yml", "w") as f:
        f.write(docker_compose)


def create_readme(archive_dir: str, include_docker: bool):
    """Create comprehensive README documentation"""
    
    readme_content = """# FalconOps AI - Enterprise AI NOC Copilot
## On-Premise Deployment Package

![FalconOps AI](https://falconapps.com/logo.png)

**Version:** 1.0.0  
**Release Date:** 2025  
**Package Type:** Enterprise On-Premise

---

## 📦 Package Contents

This deployment package includes everything you need to run FalconOps AI on-premise:

```
falconops-ai-enterprise/
├── backend/                    # FastAPI Backend Application
│   ├── app/                    # Application source code
│   │   ├── routes/             # API endpoints
│   │   ├── services/           # Business logic
│   │   └── core/               # Core utilities
│   ├── requirements.txt        # Python dependencies
│   ├── main.py                 # Application entry point
│   ├── Dockerfile              # Container build file
│   └── .env.example            # Environment template
│
├── frontend/                   # React Frontend Application
│   ├── src/                    # Source code
│   │   ├── pages/              # UI pages
│   │   ├── components/         # React components
│   │   └── layouts/            # Layout templates
│   ├── build/                  # Pre-built production files (if available)
│   ├── package.json            # Node.js dependencies
│   ├── Dockerfile              # Container build file
│   └── .env.example            # Environment template
│
├── scripts/                    # Deployment scripts
│   ├── database/               # MongoDB initialization & backup
│   │   ├── init-mongodb.sh     # Database setup script
│   │   ├── backup.sh           # Automated backup script
│   │   └── restore.sh          # Database restore script
│   └── systemd/                # Linux service files
│       ├── falconops-backend.service
│       ├── falconops-nginx.conf
│       └── README.md
│
├── kubernetes/                 # Kubernetes manifests
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml
│   ├── 02-secrets.yaml
│   ├── 03-mongodb.yaml
│   ├── 04-backend.yaml
│   ├── 05-frontend.yaml
│   ├── 06-ingress.yaml
│   ├── 07-hpa.yaml
│   └── README.md
│
├── docker-compose.yml          # Docker Compose configuration
├── install.sh                  # Interactive installer
└── README.md                   # This file
```

---

## 🚀 Features

### Core Platform
- **Real-time Monitoring** - Infrastructure, application, and network monitoring
- **AI-Powered Incident Management** - Intelligent alert correlation and RCA
- **Server & APM Monitoring** - CPU, memory, disk, process monitoring
- **Network Topology** - Interactive service dependency mapping
- **Automated Runbooks** - 17 action types with visual workflow builder
- **AI Copilot** - Log analysis and intelligent insights

### Enterprise Features
- **Multi-Tenancy** - Isolated environments for different teams
- **Role-Based Access Control** - Admin, Operator, Viewer roles
- **Health Rules Engine** - Configurable alerting thresholds
- **Metrics & Logs Ingestion** - Scalable data pipeline
- **NOC Wallboard Mode** - Full-screen operations dashboard

---

## 📋 System Requirements

### Minimum Requirements
| Component | Specification |
|-----------|---------------|
| CPU | 4 cores |
| RAM | 8 GB |
| Storage | 50 GB SSD |
| OS | Ubuntu 20.04+, RHEL 8+, or Kubernetes |

### Recommended (Production)
| Component | Specification |
|-----------|---------------|
| CPU | 8+ cores |
| RAM | 16+ GB |
| Storage | 200+ GB SSD |
| Database | MongoDB 6.0+ (dedicated or managed) |

### Software Dependencies
- Python 3.11+
- Node.js 18+
- MongoDB 6.0+
- Docker & Docker Compose (for containerized deployment)
- Nginx (for reverse proxy)

---

## 🐳 Quick Start: Docker Deployment (Recommended)

### Step 1: Extract Package
```bash
tar -xzf falconops-ai-enterprise-*.tar.gz
cd falconops-ai-enterprise-*
```

### Step 2: Configure Environment
```bash
# Copy environment templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend configuration
nano backend/.env
```

**Required settings in `backend/.env`:**
```env
MONGO_URL=mongodb://mongodb:27017
DB_NAME=falconops
JWT_SECRET_KEY=your-secure-random-key-here
LICENSE_KEY=your-license-key-here
```

### Step 3: Start Services
```bash
docker-compose up -d
```

### Step 4: Initialize Database
```bash
# Wait for MongoDB to start
sleep 10

# Run database initialization
docker exec -it falconops-mongodb mongosh falconops < scripts/database/init-mongodb.sh
```

### Step 5: Access Application
| Service | URL |
|---------|-----|
| Frontend | http://localhost |
| Backend API | http://localhost:8001 |
| API Documentation | http://localhost:8001/docs |

### Default Credentials
- **Admin:** admin@falconapps.com / Admin@123
- **Viewer:** test@falconapps.com / testpass123

---

## 🖥️ Manual Installation (Linux)

### Step 1: Install Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm mongodb-org nginx

# RHEL/CentOS
sudo dnf install -y python3.11 nodejs mongodb-org nginx
```

### Step 2: Setup Backend
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Configure your settings
```

### Step 3: Setup Frontend
```bash
cd frontend
npm install -g yarn
yarn install
yarn build
cp .env.example .env
```

### Step 4: Initialize Database
```bash
cd scripts/database
chmod +x *.sh
./init-mongodb.sh
```

### Step 5: Install Systemd Services
```bash
sudo cp scripts/systemd/falconops-backend.service /etc/systemd/system/
sudo cp scripts/systemd/falconops-nginx.conf /etc/nginx/sites-available/falconops
sudo ln -s /etc/nginx/sites-available/falconops /etc/nginx/sites-enabled/

sudo systemctl daemon-reload
sudo systemctl enable falconops-backend
sudo systemctl start falconops-backend
sudo systemctl restart nginx
```

---

## ☸️ Kubernetes Deployment

See `kubernetes/README.md` for detailed Kubernetes deployment instructions.

```bash
# Quick deploy
kubectl apply -f kubernetes/
```

---

## 🔐 License Activation

1. Log in as admin user
2. Navigate to **Enterprise → Licensing**
3. Enter your license key
4. Click **Activate License**

### License Types
| Type | Users | Servers | Monitors | Support |
|------|-------|---------|----------|---------|
| Trial | 5 | 10 | 50 | Email |
| Standard | 25 | 100 | 500 | Email |
| Professional | 100 | 500 | 2,000 | Priority |
| Enterprise | Unlimited | Unlimited | Unlimited | 24/7 |

---

## 🔧 Configuration Reference

### Backend Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `MONGO_URL` | MongoDB connection string | Yes |
| `DB_NAME` | Database name | Yes |
| `JWT_SECRET_KEY` | JWT signing key | Yes |
| `LICENSE_KEY` | FalconOps license key | Yes |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `https://falconops.acme.com`) | Yes (prod) |
| `RESEND_API_KEY` | Email delivery (scheduled reports + OTP) — https://resend.com | No |
| `EMERGENT_LLM_KEY` | Emergent Universal LLM Key (Claude / GPT / Gemini via vendor wheel) | No |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Direct LLM provider keys | No |
| `OLLAMA_BASE_URL` | Local on-prem LLM via Ollama (FREE, default `http://localhost:11434`) | No |
| `LLM_PROVIDER` | Explicit override: `ollama` / `openai` / `anthropic` / `gemini` / `emergent` / `rule_based` | No |

### Frontend Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `REACT_APP_BACKEND_URL` | Backend API URL | Yes |

---

## 📊 Management Commands

### Docker
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart service
docker-compose restart backend
```

### Systemd
```bash
# Start/Stop/Restart
sudo systemctl start falconops-backend
sudo systemctl stop falconops-backend
sudo systemctl restart falconops-backend

# View status
sudo systemctl status falconops-backend

# View logs
sudo journalctl -u falconops-backend -f
```

### Database Backup
```bash
# Manual backup
./scripts/database/backup.sh

# Restore from backup
./scripts/database/restore.sh backup_20250309.tar.gz
```

---

## 🆘 Troubleshooting

### Common Issues

**Backend won't start:**
```bash
# Check logs
docker-compose logs backend
# or
sudo journalctl -u falconops-backend -n 100
```

**MongoDB connection failed:**
```bash
# Verify MongoDB is running
sudo systemctl status mongodb
# or
docker-compose ps mongodb
```

**Frontend 502 error:**
```bash
# Check nginx configuration
sudo nginx -t
sudo systemctl status nginx
```

---

## 📞 Support

- **Documentation:** https://docs.falconapps.com
- **Email:** support@falconapps.com
- **Enterprise Support:** enterprise@falconapps.com

---

## 📄 License

Copyright © 2025 FalconOps. All rights reserved.

This software is licensed under the FalconOps Enterprise License Agreement.
Unauthorized copying, distribution, or modification is prohibited.
"""
    
    with open(Path(archive_dir) / "README.md", "w") as f:
        f.write(readme_content)


def create_install_script(archive_dir: str):
    """Create production-grade installation, uninstall, and upgrade scripts."""

    install_script = r"""#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  FalconOps AI — Enterprise On-Premise Installer
#  One-command install: ./install.sh
#  Air-gap friendly:    ./install.sh --offline
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── colours ────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_RST='\033[0m'; C_OK='\033[1;32m'; C_WRN='\033[1;33m';
  C_ERR='\033[1;31m'; C_INF='\033[1;36m'; C_BLD='\033[1m'
else
  C_RST=''; C_OK=''; C_WRN=''; C_ERR=''; C_INF=''; C_BLD=''
fi
log()  { echo -e "${C_INF}[ℹ]${C_RST} $*"; }
ok()   { echo -e "${C_OK}[✓]${C_RST} $*"; }
warn() { echo -e "${C_WRN}[!]${C_RST} $*"; }
fail() { echo -e "${C_ERR}[✗]${C_RST} $*"; exit 1; }
hdr()  { echo -e "\n${C_BLD}=========================================${C_RST}"; echo -e "${C_BLD} $*${C_RST}"; echo -e "${C_BLD}=========================================${C_RST}\n"; }

OFFLINE=0
for arg in "$@"; do
  case "$arg" in
    --offline|-o) OFFLINE=1 ;;
    --help|-h)
      cat <<EOF
FalconOps AI Installer

Usage:
  ./install.sh           interactive Docker install (downloads images if needed)
  ./install.sh --offline air-gapped install (expects images.tar in this directory)
  ./install.sh --help    show this help
EOF
      exit 0 ;;
  esac
done

hdr "FalconOps AI Enterprise Installer"
log "Running pre-flight checks…"

# ── system requirements ───────────────────────────────────────────────────
TOTAL_RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
CPU_COUNT=$(nproc 2>/dev/null || echo 1)
DISK_FREE_GB=$(df -BG --output=avail . 2>/dev/null | tail -1 | tr -d 'G ' || echo 0)

[[ ${TOTAL_RAM_MB} -ge 3500 ]] && ok "RAM:  ${TOTAL_RAM_MB} MB"  || warn "RAM:  ${TOTAL_RAM_MB} MB (4 GB+ recommended)"
[[ ${CPU_COUNT}   -ge 2    ]] && ok "CPUs: ${CPU_COUNT}"          || warn "CPUs: ${CPU_COUNT} (2+ recommended)"
[[ ${DISK_FREE_GB} -ge 8    ]] && ok "Disk: ${DISK_FREE_GB} GB free" || warn "Disk: ${DISK_FREE_GB} GB free (10+ recommended)"

# ── runtime detection ────────────────────────────────────────────────────
DOCKER_BIN=""
COMPOSE_CMD=""
if command -v docker >/dev/null 2>&1; then
    DOCKER_BIN="docker"; ok "Docker: $(docker --version | cut -d, -f1)"
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"; ok "Docker Compose v2: $(docker compose version --short)"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"; ok "Docker Compose v1: $(docker-compose version --short 2>/dev/null || echo legacy)"
    fi
elif command -v podman >/dev/null 2>&1; then
    DOCKER_BIN="podman"; ok "Podman: $(podman --version)"
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"; ok "podman-compose: $(podman-compose version 2>/dev/null | head -1)"
    fi
fi

if [[ -z "$DOCKER_BIN" || -z "$COMPOSE_CMD" ]]; then
    fail "Docker or Podman (with compose plugin) not found. See PREREQUISITES.md for install instructions."
fi

# ── env file generation ──────────────────────────────────────────────────
hdr "Configuration"

if [[ ! -f backend/.env ]]; then
    cp backend/.env.example backend/.env
    ok "Created backend/.env (from .env.example)"
fi
if [[ ! -f frontend/.env ]]; then
    cp frontend/.env.example frontend/.env
    ok "Created frontend/.env"
fi

# Generate strong random secrets if still default placeholders
if grep -q "change-this-to-a-secure-random-string" backend/.env; then
    NEW_JWT=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets;print(secrets.token_hex(32))")
    sed -i "s|JWT_SECRET_KEY=change-this-to-a-secure-random-string-min-32-chars|JWT_SECRET_KEY=${NEW_JWT}|" backend/.env
    ok "Generated random JWT_SECRET_KEY"
fi
if grep -q "change-this-to-match-the-secret-given-with-your-license" backend/.env; then
    NEW_LIC=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets;print(secrets.token_hex(32))")
    sed -i "s|LICENSE_SECRET=change-this-to-match-the-secret-given-with-your-license|LICENSE_SECRET=${NEW_LIC}|" backend/.env
    ok "Generated random LICENSE_SECRET (replace with the one given on the license certificate)"
fi

prompt_var() {
    local key="$1" prompt="$2" default="${3:-}"
    local current
    current=$(grep "^${key}=" backend/.env | cut -d= -f2- || true)
    if [[ -n "$current" && "$current" != "$default" ]]; then
        return 0   # already set; don't ask again
    fi
    read -r -p "  ${prompt}: " value
    if [[ -n "$value" ]]; then
        sed -i "s|^${key}=.*|${key}=${value}|" backend/.env
        ok "Saved ${key}"
    else
        log "Skipped ${key} (can be set later in backend/.env)"
    fi
}

log "Enter your license + AI provider keys (press ENTER to skip any)."
prompt_var LICENSE_KEY       "License key (required for production)"
prompt_var EMERGENT_LLM_KEY  "Emergent Universal LLM Key (optional)"
prompt_var OPENAI_API_KEY    "OpenAI API key (optional)"
prompt_var ANTHROPIC_API_KEY "Anthropic API key (optional)"
prompt_var RESEND_API_KEY    "Resend API key for email reports (optional)"

# Validate at least one LLM path is set, else default to ollama
if ! grep -qE "^(EMERGENT_LLM_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY)=.+" backend/.env; then
    warn "No external LLM key configured — defaulting LLM_PROVIDER to 'ollama' (local). You can change this from the Admin Console."
    sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" backend/.env
fi

# ── CORS + Public URL hardening ──────────────────────────────────────────
read -r -p "  Public URL (or comma-separated list, e.g. https://falconops.acme.com): " PUBLIC_URL
if [[ -n "$PUBLIC_URL" ]]; then
    # escape any & or | for sed
    SAFE_URL=$(printf '%s' "$PUBLIC_URL" | sed -e 's/[\/&|]/\\&/g')
    # Take just the first URL if a comma-separated list was given
    PRIMARY_URL=$(echo "$PUBLIC_URL" | cut -d, -f1 | xargs)
    SAFE_PRIMARY=$(printf '%s' "$PRIMARY_URL" | sed -e 's/[\/&|]/\\&/g')
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${SAFE_URL}|"          backend/.env
    sed -i "s|^APP_URL=.*|APP_URL=${SAFE_PRIMARY}|"                backend/.env
    sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=${SAFE_PRIMARY}|" backend/.env
    # Frontend baked URL — rebuild needed if user changes it later
    sed -i "s|^REACT_APP_BACKEND_URL=.*|REACT_APP_BACKEND_URL=${SAFE_PRIMARY}|" frontend/.env
    ok "Configured public URL = ${PRIMARY_URL}"
    ok "Frontend will be rebuilt with REACT_APP_BACKEND_URL=${PRIMARY_URL}"
fi

# ── Offline mode: load images from tarball ──────────────────────────────
if [[ ${OFFLINE} -eq 1 ]]; then
    hdr "Offline image load"
    if [[ ! -f images.tar ]]; then
        fail "OFFLINE mode requires images.tar in this directory. Build with: docker save ... > images.tar"
    fi
    log "Loading container images from images.tar (this may take a few minutes)…"
    ${DOCKER_BIN} load -i images.tar
    ok "Images loaded into ${DOCKER_BIN}"
fi

# ── Vendor wheels prep ──────────────────────────────────────────────────
if [[ -d backend/vendor ]] && ls backend/vendor/*.whl >/dev/null 2>&1; then
    ok "Vendored Python wheels detected — backend Dockerfile will install offline"
fi

# ── Start services ──────────────────────────────────────────────────────
hdr "Starting services"
log "Bringing the stack up with ${COMPOSE_CMD}…"
${COMPOSE_CMD} up -d --build

# ── Health checks ───────────────────────────────────────────────────────
hdr "Validating deployment"
RETRIES=30
URL="http://localhost:8001/api/health"
log "Waiting for backend at ${URL}…"
for i in $(seq 1 ${RETRIES}); do
    if curl -fsS "${URL}" >/dev/null 2>&1; then
        ok "Backend is healthy"; break
    fi
    sleep 2
    if [[ $i -eq $RETRIES ]]; then
        warn "Backend did not become healthy in 60s — check logs: ${COMPOSE_CMD} logs backend"
    fi
done

if curl -fsS "http://localhost/" >/dev/null 2>&1; then
    ok "Frontend gateway reachable on http://localhost"
else
    warn "Frontend gateway not yet responding — Nginx may still be starting"
fi

# ── Final report ────────────────────────────────────────────────────────
hdr "Installation Complete"
cat <<EOF
${C_OK}FalconOps AI is now running.${C_RST}

  🌐  Frontend:  http://localhost
  🔌  Backend:   http://localhost:8001
  📚  API Docs:  http://localhost:8001/docs

  Default admin credentials:
    email:    admin@falconapps.com
    password: Admin@123      ${C_WRN}(rotate immediately in Settings → Profile)${C_RST}

  Manage the stack:
    Start:    ${COMPOSE_CMD} up -d
    Stop:     ${COMPOSE_CMD} stop
    Logs:     ${COMPOSE_CMD} logs -f backend
    Upgrade:  ./upgrade.sh
    Remove:   ./uninstall.sh

  Verify your .env configuration (after logging in):
    curl -s http://localhost:8001/api/self-monitor/env-check \\
      -H "Authorization: Bearer <your-jwt-token>"
    → reports which env vars are set/missing per module (no secrets echoed).
    Fix anything flagged in backend/.env, then: ${COMPOSE_CMD} restart backend

EOF
"""

    uninstall_script = r"""#!/usr/bin/env bash
# FalconOps AI — Uninstaller
set -euo pipefail

if [[ -t 1 ]]; then
  C_RST='\033[0m'; C_OK='\033[1;32m'; C_WRN='\033[1;33m'; C_INF='\033[1;36m'
else C_RST=''; C_OK=''; C_WRN=''; C_INF=''; fi

echo -e "${C_INF}FalconOps AI — Uninstaller${C_RST}"
echo "This will stop and remove all FalconOps containers."

read -r -p "Type 'remove' to continue: " confirm
[[ "$confirm" != "remove" ]] && { echo "Aborted."; exit 0; }

DOCKER_BIN=$(command -v docker || command -v podman || echo "")
COMPOSE_CMD=""
if [[ -n "$DOCKER_BIN" ]]; then
    if docker compose version >/dev/null 2>&1; then COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD="docker-compose"
    elif command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD="podman-compose"
    fi
fi

if [[ -n "$COMPOSE_CMD" ]]; then
    $COMPOSE_CMD down --remove-orphans || true
    echo -e "${C_OK}Containers stopped.${C_RST}"
fi

read -r -p "Also delete MongoDB data volume? (DATA WILL BE LOST) [y/N]: " del
if [[ "${del,,}" == "y" || "${del,,}" == "yes" ]]; then
    $DOCKER_BIN volume rm $(${DOCKER_BIN} volume ls -q | grep -E "falconops|mongo" || true) 2>/dev/null || true
    echo -e "${C_WRN}Volumes removed.${C_RST}"
fi

echo -e "${C_OK}Uninstall complete.${C_RST}"
"""

    upgrade_script = r"""#!/usr/bin/env bash
# FalconOps AI — Zero-Data-Loss Upgrade
# Pulls latest images, runs DB migrations (if any), restarts containers.
set -euo pipefail

if [[ -t 1 ]]; then
  C_RST='\033[0m'; C_OK='\033[1;32m'; C_WRN='\033[1;33m'; C_INF='\033[1;36m'
else C_RST=''; C_OK=''; C_WRN=''; C_INF=''; fi

log()  { echo -e "${C_INF}[ℹ]${C_RST} $*"; }
ok()   { echo -e "${C_OK}[✓]${C_RST} $*"; }
warn() { echo -e "${C_WRN}[!]${C_RST} $*"; }

COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD="docker-compose"
elif command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD="podman-compose"
fi
[[ -z "$COMPOSE_CMD" ]] && { echo "compose binary not found"; exit 1; }

log "Backing up database before upgrade…"
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p backups
$COMPOSE_CMD exec -T mongo mongodump --archive --gzip > "backups/falconops_${TS}.archive.gz" 2>/dev/null \
  || warn "Backup failed (mongo container may not be running) — proceeding without backup"
[[ -f "backups/falconops_${TS}.archive.gz" ]] && ok "Backup saved to backups/falconops_${TS}.archive.gz"

log "Rebuilding latest images…"
$COMPOSE_CMD build --pull

log "Recreating containers (data volumes preserved)…"
$COMPOSE_CMD up -d --force-recreate --no-deps backend frontend
$COMPOSE_CMD up -d mongo

ok "Upgrade complete. Tail logs with: $COMPOSE_CMD logs -f backend"
"""

    for fname, content in [
        ("install.sh", install_script),
        ("uninstall.sh", uninstall_script),
        ("upgrade.sh", upgrade_script),
    ]:
        path = Path(archive_dir) / fname
        with open(path, "w") as f:
            f.write(content)
        os.chmod(path, 0o755)


def create_prerequisites_doc(archive_dir: str):
    """Create comprehensive prerequisites documentation."""
    content = """# FalconOps AI — Linux Server Prerequisites

This document lists **everything** you need on a fresh Linux server to run FalconOps AI.
Two install paths are supported: **Docker (recommended, 5 minutes)** and **Bare-metal** (systemd + nginx).

---

## Hardware Requirements

| Tier | vCPU | RAM | Disk | Use case |
|------|------|-----|------|----------|
| **Test / Demo** | 2 | 4 GB | 20 GB | Single-user evaluation |
| **Small Prod** | 4 | 8 GB | 50 GB SSD | 10-50 monitors, 5 users |
| **Standard Prod** | 8 | 16 GB | 200 GB SSD | 500 monitors, 25 users |
| **Enterprise** | 16+ | 32+ GB | 500 GB SSD + Atlas | 2000+ monitors, 100+ users |

---

## Supported Operating Systems

- Ubuntu 20.04 / 22.04 / 24.04 LTS  ✅ (recommended)
- Debian 11 / 12
- RHEL / Rocky / AlmaLinux 8 / 9
- Amazon Linux 2 / 2023
- Any systemd-based distro with the packages below

Kernel: 5.x+  ·  glibc 2.31+  ·  x86_64 or arm64

---

## Path A — Docker (recommended)

### Install Docker + Compose (Ubuntu/Debian)
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
# compose plugin ships with Docker 20.10+; verify:
docker compose version
```

### Install Docker + Compose (RHEL/Rocky/Alma)
```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker
```

That's it. Run `./install-linux.sh` and pick option 1.

---

## Path B — Podman (rootless, daemonless — recommended for RHEL 9 / Rocky / Alma / Fedora)

### Install Podman (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y podman podman-compose uidmap slirp4netns fuse-overlayfs
```

### Install Podman (RHEL 9 / Rocky / Alma / Fedora)
```bash
sudo dnf install -y podman podman-compose container-tools
```

### Why Podman over Docker?
- **Rootless** — no daemon, no privileged user; safer for multi-tenant
- **Native systemd integration** via Quadlet on RHEL 9+
- **Drop-in compose** — `podman compose` replaces `docker compose`
- **Approved for many enterprises** that ban Docker daemon

### Run
```bash
./install-linux.sh   # pick option 2 (Podman)
```

### Notes for rootless mode
- Cannot bind to ports < 1024. Frontend runs on **8080**; use a reverse proxy (Caddy / nginx) on 80/443 to publish externally.
- For systemd-managed containers, see `scripts/quadlet/README.md` (RHEL 9+ has Quadlet built into Podman).
- Enable `loginctl enable-linger $USER` so containers survive logout (auto-handled by `install-linux.sh`).

---

## Path C — Bare-metal (systemd + nginx + mongodb)

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18 LTS or 20 LTS | Frontend build |
| Yarn (classic) | 1.22+ | Frontend dep manager (npm **not** supported) |
| MongoDB | 6.0+ or 7.0 | Database |
| nginx | 1.18+ | Reverse proxy + static |
| systemd | any | Service manager |
| git, curl, tar, gzip, unzip | any | Unpacking + utilities |
| gcc, libffi-dev, python3.11-dev | any | Building Python wheels (bcrypt, psutil) |

### Ubuntu 22.04 — copy / paste
```bash
sudo apt update
sudo apt install -y software-properties-common curl gnupg ca-certificates lsb-release
# Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential libffi-dev
# Node 20 + Yarn
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g yarn
# MongoDB 7.0
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \\
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \\
  https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \\
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org nginx
sudo systemctl enable --now mongod nginx
```

### RHEL 9 / Rocky / Alma — copy / paste
```bash
sudo dnf install -y gcc libffi-devel python3.11 python3.11-devel nginx git curl tar
# Node 20
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
sudo dnf install -y nodejs
sudo npm install -g yarn
# MongoDB 7.0
cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF
sudo dnf install -y mongodb-org
sudo systemctl enable --now mongod nginx
```

---

## Network / Firewall

| Port | Direction | Purpose |
|------|-----------|---------|
| 80 / 443 | inbound | nginx gateway (UI + API) |
| 27017 | localhost only | MongoDB (never expose publicly) |
| 8001 | localhost only | Backend uvicorn |
| 6379 | localhost only | Redis (optional) |
| 443 outbound | egress | Resend, Stripe, Emergent LLM, Docker Hub |

```bash
# Ubuntu UFW example
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Required API Keys (optional but recommended)

| Key | Where to get it | Purpose |
|-----|-----------------|---------|
| `EMERGENT_LLM_KEY` | Emergent → Profile → Universal Key | AI agents (RCA, Summarizer, Healer) |
| `RESEND_API_KEY` | https://resend.com/api-keys | Scheduled report emails + OTP |
| `STRIPE_API_KEY` | https://dashboard.stripe.com/apikeys | Billing (only if reselling) |
| `LICENSE_KEY` | Admin → Downloads → Generate | Enables enterprise features |

Put them all in `backend/.env` (sample: `backend/.env.example`).

---

## Post-install Verification

```bash
# Docker path
docker compose ps         # all services Up
curl http://localhost/api/health
# Bare-metal path
sudo systemctl status falconops-backend
sudo systemctl status mongod nginx
curl http://localhost:8001/api/health
```

Expected `/api/health` response:
```json
{"status": "healthy", "storage": {"backend": "local"}}
```

---

## Default Credentials (post-seed)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@falconapps.com | Admin@123 |
| Viewer | test@falconapps.com | testpass123 |

**Change `Admin@123` immediately after first login.**
"""
    with open(Path(archive_dir) / "PREREQUISITES.md", "w") as f:
        f.write(content)


def create_quickstart_doc(archive_dir: str):
    """Create an at-a-glance quickstart."""
    content = """# FalconOps AI — 60-second Quickstart

## Docker (easiest)
```bash
tar -xzf falconops-ai-enterprise-*.tar.gz   # or: unzip falconops-ai-enterprise-*.zip
cd falconops-ai-enterprise-*
chmod +x install-linux.sh
./install-linux.sh        # pick option 1
```

Open http://localhost  → login as `admin@falconapps.com` / `Admin@123`

## Bare-metal
```bash
./install-linux.sh        # pick option 2 — auto-detects distro, installs deps,
                          # seeds mongo, builds frontend, registers systemd units
```

## Completely manual
See `PREREQUISITES.md` then `README.md`.

---

## What's inside this bundle?

```
falconops-ai-enterprise/
├── backend/                 # FastAPI app + requirements.txt + Dockerfile
├── frontend/                # React source (Tailwind + shadcn) + Dockerfile
├── scripts/
│   ├── database/            # init-mongodb.sh · backup.sh · restore.sh
│   └── systemd/             # falconops-backend.service · nginx site
├── kubernetes/              # 8 manifests (ns · cm · secret · mongo · fe · be · ingress · hpa)
├── docker-compose.yml       # 4-service stack (mongo · redis · backend · frontend + nginx)
├── install-linux.sh         # interactive installer — Docker OR bare-metal
├── install.sh               # legacy alias (Docker only)
├── PREREQUISITES.md         # full hardware / OS / package matrix
├── README.md                # full docs
└── QUICKSTART.md            # this file
```
"""
    with open(Path(archive_dir) / "QUICKSTART.md", "w") as f:
        f.write(content)


def create_linux_bootstrap_script(archive_dir: str):
    """Create a polished one-command Linux installer with prereq checks and auto-install."""
    script = r"""#!/usr/bin/env bash
# FalconOps AI — Linux One-Command Installer
# Handles both Docker and bare-metal paths with prereq auto-detection
set -euo pipefail

RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YLW=$'\033[0;33m'; BLU=$'\033[0;36m'; NC=$'\033[0m'
log()   { printf "%s[*]%s %s\n" "$BLU" "$NC" "$1"; }
ok()    { printf "%s[✓]%s %s\n" "$GRN" "$NC" "$1"; }
warn()  { printf "%s[!]%s %s\n" "$YLW" "$NC" "$1"; }
fail()  { printf "%s[✗]%s %s\n" "$RED" "$NC" "$1"; exit 1; }

need_root() {
    if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
        warn "You will be prompted for sudo password."
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$ID; OS_VERSION=$VERSION_ID
    else
        fail "Cannot detect OS — /etc/os-release missing."
    fi
}

check_cmd() { command -v "$1" >/dev/null 2>&1; }

banner() {
cat <<'EOF'
╔═══════════════════════════════════════════════════════════╗
║        FalconOps AI — Enterprise Linux Installer          ║
║        Unified AIOps · SIEM · DevSecOps platform          ║
╚═══════════════════════════════════════════════════════════╝
EOF
}

preflight() {
    log "Running pre-flight checks on ${OS_ID} ${OS_VERSION}..."
    local cpu mem disk
    cpu=$(nproc 2>/dev/null || echo 0)
    mem=$(awk '/MemTotal/ {print int($2/1024/1024)}' /proc/meminfo 2>/dev/null || echo 0)
    disk=$(df -BG --output=avail / | tail -1 | tr -dc '0-9' || echo 0)

    [ "$cpu" -ge 2 ]  && ok "CPU cores: $cpu"  || warn "CPU cores: $cpu (2+ recommended)"
    [ "$mem" -ge 4 ]  && ok "RAM: ${mem} GB"   || warn "RAM: ${mem} GB (4+ GB recommended)"
    [ "$disk" -ge 20 ]&& ok "Disk free: ${disk} GB" || warn "Disk free: ${disk} GB (20+ GB recommended)"
}

install_docker() {
    if check_cmd docker && docker compose version >/dev/null 2>&1; then
        ok "Docker + Compose already installed"; return
    fi
    log "Installing Docker + Compose..."
    case "$OS_ID" in
        ubuntu|debian)
            curl -fsSL https://get.docker.com | sudo sh
            ;;
        rhel|rocky|almalinux|centos|amzn)
            sudo dnf install -y dnf-plugins-core || sudo yum install -y yum-utils
            sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo 2>/dev/null \
              || sudo yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null \
              || sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            sudo systemctl enable --now docker
            ;;
        *) fail "Unsupported OS '$OS_ID' for auto-install. Install Docker manually then re-run." ;;
    esac
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    ok "Docker installed. You may need to re-login for group changes to take effect."
}

install_podman() {
    if check_cmd podman; then
        ok "Podman already installed ($(podman --version))"
    else
        log "Installing Podman..."
        case "$OS_ID" in
            ubuntu|debian)
                sudo apt update -y
                sudo apt install -y podman podman-compose uidmap slirp4netns fuse-overlayfs
                ;;
            rhel|rocky|almalinux|centos|amzn|fedora)
                sudo dnf install -y podman podman-compose container-tools
                ;;
            *) fail "Unsupported OS '$OS_ID' for auto-install. Install Podman manually then re-run." ;;
        esac
    fi
    if ! check_cmd podman-compose && ! podman compose version >/dev/null 2>&1; then
        warn "Neither podman-compose nor 'podman compose' available — installing podman-compose via pip..."
        sudo python3 -m pip install --upgrade podman-compose 2>/dev/null || pip install --user podman-compose
    fi
    # Enable user lingering so rootless containers survive logout
    if check_cmd loginctl; then
        sudo loginctl enable-linger "$USER" 2>/dev/null || true
    fi
    ok "Podman ready (rootless mode)."
}

install_baremetal_deps() {
    log "Installing Python 3.11, Node 20, Yarn, MongoDB 7, nginx..."
    case "$OS_ID" in
        ubuntu|debian)
            sudo apt update -y
            sudo apt install -y software-properties-common curl gnupg ca-certificates lsb-release \
                build-essential libffi-dev git nginx
            sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
            sudo apt install -y python3.11 python3.11-venv python3.11-dev 2>/dev/null \
              || sudo apt install -y python3 python3-venv python3-dev
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
            sudo npm install -g yarn
            curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
                sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor 2>/dev/null || true
            codename=$(lsb_release -cs 2>/dev/null || echo jammy)
            echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
https://repo.mongodb.org/apt/ubuntu $codename/mongodb-org/7.0 multiverse" | \
                sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list >/dev/null
            sudo apt update -y
            sudo apt install -y mongodb-org
            sudo systemctl enable --now mongod nginx
            ;;
        rhel|rocky|almalinux|centos|amzn)
            sudo dnf install -y gcc libffi-devel python3.11 python3.11-devel nginx git curl tar
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
            sudo dnf install -y nodejs
            sudo npm install -g yarn
            cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo >/dev/null
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF
            sudo dnf install -y mongodb-org
            sudo systemctl enable --now mongod nginx
            ;;
        *) fail "Unsupported OS '$OS_ID' for auto-install." ;;
    esac
    ok "System dependencies installed."
}

docker_path() {
    install_docker
    log "Bootstrapping .env files..."
    [ -f backend/.env ]  || cp backend/.env.example  backend/.env
    [ -f frontend/.env ] || cp frontend/.env.example frontend/.env
    ok "Env files ready (edit backend/.env later to add LLM / Resend keys)."

    log "Building + starting stack (this may take 3–5 min on first run)..."
    docker compose up -d --build
    ok "Stack started. Waiting for health..."
    for i in $(seq 1 30); do
        if curl -fsS http://localhost/api/health >/dev/null 2>&1; then
            ok "Backend is healthy."; break
        fi
        sleep 2
    done

    printf "\n%s════════════════════════════════════════════════%s\n" "$GRN" "$NC"
    echo    "   FalconOps AI is running!"
    echo    "   UI        →  http://localhost"
    echo    "   API       →  http://localhost/api"
    echo    "   Docs      →  http://localhost/api/docs"
    echo    "   Admin     →  admin@falconapps.com / Admin@123"
    printf "%s════════════════════════════════════════════════%s\n" "$GRN" "$NC"
}

podman_path() {
    install_podman
    log "Bootstrapping .env files..."
    [ -f backend/.env ]  || cp backend/.env.example  backend/.env
    [ -f frontend/.env ] || cp frontend/.env.example frontend/.env
    ok "Env files ready."

    log "Building + starting stack with Podman (rootless)..."
    if podman compose version >/dev/null 2>&1; then
        podman compose -f podman-compose.yml up -d --build
    elif check_cmd podman-compose; then
        podman-compose -f podman-compose.yml up -d --build
    else
        fail "Neither 'podman compose' nor 'podman-compose' available."
    fi

    ok "Stack started. Waiting for health..."
    for i in $(seq 1 30); do
        if curl -fsS http://localhost:8080/api/health >/dev/null 2>&1; then
            ok "Backend is healthy."; break
        fi
        sleep 2
    done

    printf "\n%s════════════════════════════════════════════════%s\n" "$GRN" "$NC"
    echo    "   FalconOps AI is running on Podman (rootless)!"
    echo    "   UI        →  http://localhost:8080"
    echo    "   API       →  http://localhost:8080/api"
    echo    "   Admin     →  admin@falconapps.com / Admin@123"
    echo    ""
    echo    "   To run on port 80, add a reverse proxy (Caddy / nginx) in front,"
    echo    "   or for systemd-managed Quadlet units see scripts/quadlet/README.md"
    printf "%s════════════════════════════════════════════════%s\n" "$GRN" "$NC"
}

baremetal_path() {
    install_baremetal_deps

    log "Creating system user 'falconops'..."
    id -u falconops >/dev/null 2>&1 || sudo useradd -r -m -d /opt/falconops -s /bin/bash falconops
    sudo mkdir -p /opt/falconops /var/log/falconops
    sudo cp -r ./backend ./frontend ./scripts /opt/falconops/
    sudo chown -R falconops:falconops /opt/falconops /var/log/falconops

    log "Creating Python venv + installing backend deps..."
    sudo -u falconops bash -c "cd /opt/falconops/backend && python3.11 -m venv venv 2>/dev/null || python3 -m venv venv"
    sudo -u falconops bash -c "cd /opt/falconops/backend && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt"
    [ -f /opt/falconops/backend/.env ] || sudo -u falconops cp /opt/falconops/backend/.env.example /opt/falconops/backend/.env

    log "Building frontend (yarn)..."
    sudo -u falconops bash -c "cd /opt/falconops/frontend && yarn install --frozen-lockfile && yarn build"

    log "Seeding MongoDB..."
    sudo bash /opt/falconops/scripts/database/init-mongodb.sh || warn "Mongo seed may have partially failed — check manually."

    log "Installing systemd units + nginx site..."
    sudo cp /opt/falconops/scripts/systemd/falconops-backend.service /etc/systemd/system/
    sudo cp /opt/falconops/scripts/systemd/falconops-nginx.conf /etc/nginx/conf.d/falconops.conf
    sudo systemctl daemon-reload
    sudo systemctl enable --now falconops-backend
    sudo systemctl reload nginx

    ok "Install complete. UI → http://localhost  ·  API → http://localhost:8001/api"
}

main() {
    banner
    need_root
    detect_os
    preflight

    echo
    echo "Choose installation method:"
    echo "  1) Docker        (recommended · 4 containers · ~5 min)"
    echo "  2) Podman        (rootless, daemonless · best for RHEL/Rocky/Alma · ~6 min)"
    echo "  3) Bare-metal    (systemd + nginx + mongo · full control)"
    echo "  4) Print prerequisites only (dry run)"
    echo "  q) Quit"
    read -rp "Enter choice [1-4/q]: " choice

    case "$choice" in
        1) docker_path ;;
        2) podman_path ;;
        3) baremetal_path ;;
        4) cat PREREQUISITES.md ;;
        q|Q) echo "Bye."; exit 0 ;;
        *) fail "Invalid choice." ;;
    esac
}

main "$@"
"""
    script_path = Path(archive_dir) / "install-linux.sh"
    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)


def create_enterprise_assets(archive_dir: str):
    """Generate Helm chart, environment configs, packaging scripts, and air-gap guide."""
    root = Path(archive_dir)

    # ─────────────────────────────────────────────────────
    #  configs/{dev,prod,on-prem}.env presets
    # ─────────────────────────────────────────────────────
    configs_dir = root / "configs"
    configs_dir.mkdir(exist_ok=True)

    (configs_dir / "dev.env").write_text(
        "# FalconOps AI — DEV preset (local laptop)\n"
        "ENVIRONMENT=dev\nMONGO_URL=mongodb://localhost:27017\nDB_NAME=falconops_dev\n"
        "CORS_ORIGINS=*\nLLM_PROVIDER=rule_based\nACCESS_TOKEN_EXPIRE_MINUTES=1440\n"
        "STORAGE_BACKEND=local\n"
    )
    (configs_dir / "prod.env").write_text(
        "# FalconOps AI — PROD preset (cloud / public-facing)\n"
        "ENVIRONMENT=prod\nMONGO_URL=mongodb://mongodb:27017\nDB_NAME=falconops\n"
        "CORS_ORIGINS=https://falconops.example.com\nLLM_PROVIDER=\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=720\nSTORAGE_BACKEND=s3\n"
        "REPORTS_S3_BUCKET=falconops-reports-prod\nAWS_REGION=us-east-1\n"
    )
    (configs_dir / "on-prem.env").write_text(
        "# FalconOps AI — ON-PREM preset (air-gapped / restricted enterprise)\n"
        "ENVIRONMENT=on-prem\nMONGO_URL=mongodb://mongodb:27017\nDB_NAME=falconops\n"
        "CORS_ORIGINS=https://falconops.internal.acme.com\nLLM_PROVIDER=ollama\n"
        "OLLAMA_BASE_URL=http://ollama:11434\nACCESS_TOKEN_EXPIRE_MINUTES=720\n"
        "STORAGE_BACKEND=local\n"
    )
    (configs_dir / "README.md").write_text(
        "# Environment Presets\n\n"
        "Pick a preset that matches your deployment target and overlay it on `backend/.env`:\n\n"
        "```bash\ncat configs/on-prem.env >> backend/.env  # merge\n"
        "# or\ncp configs/prod.env backend/.env  # replace\n```\n\n"
        "| Preset        | Use case                       | LLM provider   | Storage |\n"
        "|---------------|--------------------------------|----------------|---------|\n"
        "| `dev.env`     | Local laptop development       | rule-based     | local   |\n"
        "| `prod.env`    | Cloud / public-facing          | (pick any key) | s3      |\n"
        "| `on-prem.env` | Air-gapped enterprise          | ollama (local) | local   |\n"
    )

    # ─────────────────────────────────────────────────────
    #  scripts/ — packaging helpers
    # ─────────────────────────────────────────────────────
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    pkg_images = (
        "#!/usr/bin/env bash\n"
        "# scripts/package-images.sh — pull Docker images and save to images.tar\n"
        "set -euo pipefail\n"
        'IMAGES=(mongo:6.0 nginx:alpine python:3.11-slim node:18-alpine)\n'
        'echo "Pulling images…"\nfor img in "${IMAGES[@]}"; do docker pull "$img"; done\n'
        'echo "Saving to images.tar (this may take 1-2 GB)…"\ndocker save "${IMAGES[@]}" -o images.tar\n'
        'echo "Done. Ship images.tar with your bundle, then on the target:"\n'
        'echo "  docker load -i images.tar"\n'
    )
    pkg_wheels = (
        "#!/usr/bin/env bash\n"
        "# scripts/package-wheels.sh — download Python wheels into backend/vendor/\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")/.."\nmkdir -p backend/vendor\ncd backend\n'
        "pip download --dest ./vendor --python-version 3.11 \\\n"
        "  --platform manylinux2014_x86_64 --only-binary=:all: \\\n"
        "  --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \\\n"
        "  -r requirements.txt\n"
        'echo "Vendor cache ready: $(ls -1 backend/vendor | wc -l) wheels"\n'
    )
    license_mock = (
        "#!/usr/bin/env python3\n"
        "'''scripts/license-mock.py — generate a self-signed eval license offline.'''\n"
        "import argparse, hashlib, json, secrets, datetime as dt\n"
        "def gen(plan='enterprise', days=365, org='Acme Inc'):\n"
        "    payload = {'plan': plan, 'org': org,\n"
        "               'issued_at': dt.datetime.utcnow().isoformat() + 'Z',\n"
        "               'expires_at': (dt.datetime.utcnow() + dt.timedelta(days=days)).isoformat() + 'Z',\n"
        "               'nonce': secrets.token_hex(8)}\n"
        "    body = json.dumps(payload, separators=(',', ':')).encode()\n"
        "    sig = hashlib.sha256(body).hexdigest()\n"
        "    return 'FLX-' + sig[:8].upper() + '-' + sig[8:16].upper() + '-' + sig[16:24].upper(), payload\n"
        "if __name__ == '__main__':\n"
        "    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--plan', default='enterprise', choices=['starter','team','enterprise'])\n"
        "    ap.add_argument('--days', type=int, default=365)\n"
        "    ap.add_argument('--org', default='Acme Inc')\n"
        "    args = ap.parse_args()\n"
        "    key, p = gen(args.plan, args.days, args.org)\n"
        "    print('License key: ' + key)\n"
        "    print('Plan:        ' + p['plan'])\n"
        "    print('Org:         ' + p['org'])\n"
        "    print('Expires:     ' + p['expires_at'])\n"
    )
    install_systemd = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        '[[ $EUID -ne 0 ]] && { echo "Run as root"; exit 1; }\n'
        "cp scripts/systemd/*.service /etc/systemd/system/\n"
        "systemctl daemon-reload\n"
        "systemctl enable falconops-backend.service falconops-frontend.service\n"
        "systemctl start falconops-backend.service falconops-frontend.service\n"
        'echo "✓ FalconOps systemd services installed and started."\n'
    )

    for fname, content in [
        ("package-images.sh", pkg_images),
        ("package-wheels.sh", pkg_wheels),
        ("license-mock.py", license_mock),
        ("install-systemd.sh", install_systemd),
    ]:
        path = scripts_dir / fname
        path.write_text(content)
        os.chmod(path, 0o755)

    # ─────────────────────────────────────────────────────
    #  kubernetes/helm/ — Helm chart
    # ─────────────────────────────────────────────────────
    helm_dir = root / "kubernetes" / "helm" / "falconops"
    (helm_dir / "templates").mkdir(parents=True, exist_ok=True)

    (helm_dir / "Chart.yaml").write_text(
        "apiVersion: v2\nname: falconops\n"
        "description: FalconOps AI — Enterprise AIOps + SIEM + OpenTelemetry APM\n"
        "type: application\nversion: 1.0.0\nappVersion: \"1.0.0\"\n"
        "keywords: [aiops, siem, monitoring, opentelemetry, apm]\nhome: https://falconapps.com\n"
        "maintainers:\n  - name: FalconOps Team\n"
    )

    (helm_dir / "values.yaml").write_text(
        "image:\n  backend: falconops/backend:1.0.0\n  frontend: falconops/frontend:1.0.0\n"
        "  mongo: mongo:6.0\n  pullPolicy: IfNotPresent\n"
        "replicaCount:\n  backend: 2\n  frontend: 2\n"
        "resources:\n  backend:\n    requests: {cpu: 500m, memory: 512Mi}\n    limits: {cpu: 2, memory: 2Gi}\n"
        "  frontend:\n    requests: {cpu: 100m, memory: 128Mi}\n    limits: {cpu: 500m, memory: 512Mi}\n"
        "ingress:\n  enabled: true\n  host: falconops.example.com\n  tls: true\n  className: nginx\n"
        "env:\n  CORS_ORIGINS: \"https://falconops.example.com\"\n  STORAGE_BACKEND: \"local\"\n"
        "secrets:\n  LICENSE_KEY: \"\"\n  EMERGENT_LLM_KEY: \"\"\n  OPENAI_API_KEY: \"\"\n"
        "  ANTHROPIC_API_KEY: \"\"\n  RESEND_API_KEY: \"\"\n  JWT_SECRET_KEY: \"REPLACE-WITH-LONG-RANDOM\"\n"
        "mongodb:\n  persistence:\n    enabled: true\n    size: 50Gi\n    storageClass: \"\"\n"
        "autoscaling:\n  enabled: true\n  backend:\n    minReplicas: 2\n    maxReplicas: 10\n"
        "    targetCPUUtilizationPercentage: 70\n"
    )

    (helm_dir / "templates" / "backend.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ .Release.Name }}-backend\n"
        "  labels: { app: falconops-backend }\nspec:\n  replicas: {{ .Values.replicaCount.backend }}\n"
        "  selector: { matchLabels: { app: falconops-backend } }\n  template:\n"
        "    metadata: { labels: { app: falconops-backend } }\n    spec:\n      containers:\n"
        "      - name: backend\n        image: \"{{ .Values.image.backend }}\"\n"
        "        imagePullPolicy: {{ .Values.image.pullPolicy }}\n"
        "        ports: [{ containerPort: 8001 }]\n        envFrom:\n"
        "          - secretRef: { name: {{ .Release.Name }}-secrets }\n"
        "          - configMapRef: { name: {{ .Release.Name }}-config }\n"
        "        env:\n          - name: MONGO_URL\n            value: \"mongodb://{{ .Release.Name }}-mongodb:27017\"\n"
        "        readinessProbe:\n          httpGet: { path: /api/health, port: 8001 }\n"
        "          initialDelaySeconds: 30\n          periodSeconds: 10\n"
        "        livenessProbe:\n          httpGet: { path: /api/health, port: 8001 }\n"
        "          initialDelaySeconds: 60\n          periodSeconds: 20\n"
        "        resources:\n{{ toYaml .Values.resources.backend | indent 10 }}\n"
        "---\napiVersion: v1\nkind: Service\nmetadata:\n  name: {{ .Release.Name }}-backend\n"
        "spec:\n  selector: { app: falconops-backend }\n  ports: [{ port: 8001, targetPort: 8001 }]\n"
    )

    (helm_dir / "templates" / "frontend.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ .Release.Name }}-frontend\n"
        "  labels: { app: falconops-frontend }\nspec:\n  replicas: {{ .Values.replicaCount.frontend }}\n"
        "  selector: { matchLabels: { app: falconops-frontend } }\n  template:\n"
        "    metadata: { labels: { app: falconops-frontend } }\n    spec:\n      containers:\n"
        "      - name: frontend\n        image: \"{{ .Values.image.frontend }}\"\n"
        "        ports: [{ containerPort: 80 }]\n        readinessProbe:\n"
        "          httpGet: { path: /, port: 80 }\n          initialDelaySeconds: 15\n"
        "        resources:\n{{ toYaml .Values.resources.frontend | indent 10 }}\n"
        "---\napiVersion: v1\nkind: Service\nmetadata:\n  name: {{ .Release.Name }}-frontend\n"
        "spec:\n  selector: { app: falconops-frontend }\n  ports: [{ port: 80, targetPort: 80 }]\n"
    )

    (helm_dir / "templates" / "mongodb.yaml").write_text(
        "apiVersion: apps/v1\nkind: StatefulSet\nmetadata:\n  name: {{ .Release.Name }}-mongodb\n"
        "spec:\n  serviceName: {{ .Release.Name }}-mongodb\n  replicas: 1\n"
        "  selector: { matchLabels: { app: falconops-mongodb } }\n  template:\n"
        "    metadata: { labels: { app: falconops-mongodb } }\n    spec:\n      containers:\n"
        "      - name: mongo\n        image: \"{{ .Values.image.mongo }}\"\n"
        "        ports: [{ containerPort: 27017 }]\n        volumeMounts:\n"
        "          - { name: data, mountPath: /data/db }\n"
        "  volumeClaimTemplates:\n    - metadata: { name: data }\n      spec:\n"
        "        accessModes: [\"ReadWriteOnce\"]\n"
        "        resources: { requests: { storage: \"{{ .Values.mongodb.persistence.size }}\" } }\n"
        "        {{- if .Values.mongodb.persistence.storageClass }}\n"
        "        storageClassName: \"{{ .Values.mongodb.persistence.storageClass }}\"\n"
        "        {{- end }}\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: {{ .Release.Name }}-mongodb\n"
        "spec:\n  selector: { app: falconops-mongodb }\n  ports: [{ port: 27017, targetPort: 27017 }]\n"
    )

    (helm_dir / "templates" / "secrets-configmap.yaml").write_text(
        "apiVersion: v1\nkind: Secret\nmetadata: { name: {{ .Release.Name }}-secrets }\n"
        "type: Opaque\nstringData:\n"
        "  LICENSE_KEY:       \"{{ .Values.secrets.LICENSE_KEY }}\"\n"
        "  EMERGENT_LLM_KEY:  \"{{ .Values.secrets.EMERGENT_LLM_KEY }}\"\n"
        "  OPENAI_API_KEY:    \"{{ .Values.secrets.OPENAI_API_KEY }}\"\n"
        "  ANTHROPIC_API_KEY: \"{{ .Values.secrets.ANTHROPIC_API_KEY }}\"\n"
        "  RESEND_API_KEY:    \"{{ .Values.secrets.RESEND_API_KEY }}\"\n"
        "  JWT_SECRET_KEY:    \"{{ .Values.secrets.JWT_SECRET_KEY }}\"\n"
        "---\napiVersion: v1\nkind: ConfigMap\nmetadata: { name: {{ .Release.Name }}-config }\n"
        "data:\n  CORS_ORIGINS:    \"{{ .Values.env.CORS_ORIGINS }}\"\n"
        "  STORAGE_BACKEND: \"{{ .Values.env.STORAGE_BACKEND }}\"\n"
        "  DB_NAME:         \"falconops\"\n"
    )

    (helm_dir / "templates" / "ingress.yaml").write_text(
        "{{- if .Values.ingress.enabled }}\napiVersion: networking.k8s.io/v1\nkind: Ingress\n"
        "metadata:\n  name: {{ .Release.Name }}-ingress\n"
        "  annotations:\n    nginx.ingress.kubernetes.io/proxy-body-size: \"50m\"\n"
        "spec:\n  ingressClassName: {{ .Values.ingress.className }}\n"
        "  {{- if .Values.ingress.tls }}\n  tls:\n    - hosts: [\"{{ .Values.ingress.host }}\"]\n"
        "      secretName: {{ .Release.Name }}-tls\n  {{- end }}\n  rules:\n"
        "    - host: {{ .Values.ingress.host }}\n      http:\n        paths:\n"
        "          - path: /api\n            pathType: Prefix\n"
        "            backend: { service: { name: {{ .Release.Name }}-backend, port: { number: 8001 } } }\n"
        "          - path: /\n            pathType: Prefix\n"
        "            backend: { service: { name: {{ .Release.Name }}-frontend, port: { number: 80 } } }\n"
        "{{- end }}\n"
    )

    (helm_dir / "templates" / "hpa.yaml").write_text(
        "{{- if .Values.autoscaling.enabled }}\napiVersion: autoscaling/v2\n"
        "kind: HorizontalPodAutoscaler\nmetadata: { name: {{ .Release.Name }}-backend-hpa }\n"
        "spec:\n  scaleTargetRef:\n    apiVersion: apps/v1\n    kind: Deployment\n"
        "    name: {{ .Release.Name }}-backend\n"
        "  minReplicas: {{ .Values.autoscaling.backend.minReplicas }}\n"
        "  maxReplicas: {{ .Values.autoscaling.backend.maxReplicas }}\n"
        "  metrics:\n    - type: Resource\n      resource:\n        name: cpu\n"
        "        target: { type: Utilization, averageUtilization: {{ .Values.autoscaling.backend.targetCPUUtilizationPercentage }} }\n"
        "{{- end }}\n"
    )

    (helm_dir / "README.md").write_text(
        "# FalconOps AI Helm Chart\n\n"
        "## Install\n```bash\nhelm install falconops ./kubernetes/helm/falconops \\\n"
        "  --namespace falconops --create-namespace \\\n"
        "  --set-string secrets.LICENSE_KEY=YOUR-KEY \\\n"
        "  --set-string secrets.JWT_SECRET_KEY=$(openssl rand -hex 32) \\\n"
        "  --set ingress.host=falconops.acme.com\n```\n\n"
        "## Upgrade\n```bash\nhelm upgrade falconops ./kubernetes/helm/falconops -n falconops --reuse-values\n```\n\n"
        "## Uninstall\n```bash\nhelm uninstall falconops -n falconops\n```\n"
    )

    # ─────────────────────────────────────────────────────
    #  AIRGAP.md — comprehensive air-gapped install guide
    # ─────────────────────────────────────────────────────
    (root / "AIRGAP.md").write_text(
        "# FalconOps AI — Air-Gapped Installation Guide\n\n"
        "## TL;DR\n\n"
        "```bash\n"
        "# On an internet-connected staging machine:\n"
        "./scripts/package-images.sh   # → images.tar  (~1.5 GB)\n"
        "./scripts/package-wheels.sh   # → backend/vendor/*.whl\n\n"
        "# Re-tar and transfer to the air-gapped target:\n"
        "tar -czf falconops-airgap.tar.gz falconops-ai-enterprise-*  images.tar\n"
        "scp falconops-airgap.tar.gz airgap-target:/opt/\n\n"
        "# On the air-gapped target:\n"
        "tar -xzf /opt/falconops-airgap.tar.gz -C /opt/\n"
        "cd /opt/falconops-ai-enterprise-*\n"
        "./install.sh --offline\n"
        "```\n\n"
        "## Step 1 — Stage on an internet-connected machine\n\n"
        "Required: Docker, Python 3.11, network access to hub.docker.com, pypi.org, "
        "and d33sy5i8bnduwe.cloudfront.net.\n\n"
        "```bash\n./scripts/package-images.sh\n./scripts/package-wheels.sh\n```\n\n"
        "## Step 2 — Transfer\n\nShip the bundle directory + `images.tar` via scp / USB / artifact repo.\n\n"
        "## Step 3 — Install\n\n```bash\n./install.sh --offline\n```\n\n"
        "The installer will:\n"
        "1. ✅ Detect Docker / Podman + Compose\n"
        "2. ✅ Generate a strong random `JWT_SECRET_KEY`\n"
        "3. ✅ Prompt for `LICENSE_KEY` (use `scripts/license-mock.py` for demos)\n"
        "4. ✅ Prompt for any of `EMERGENT_LLM_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`\n"
        "5. ✅ Default `LLM_PROVIDER=ollama` if no external keys provided\n"
        "6. ✅ Load images from `images.tar` via `docker load`\n"
        "7. ✅ Install Python deps from `backend/vendor/` (zero network calls)\n"
        "8. ✅ Start the stack, wait for `/api/health`, print the access URL\n\n"
        "## Step 4 — Validate\n\n"
        "```bash\ncurl -fsS http://localhost:8001/api/health\ncurl -fsS http://localhost/\n```\n\n"
        "## (Optional) Step 5 — Local Ollama for free on-prem AI\n\n"
        "```bash\ndocker pull ollama/ollama:latest          # do this on STAGE\n"
        "docker save ollama/ollama:latest -o ollama.tar\n# transfer, then on target:\n"
        "docker load -i ollama.tar\ndocker run -d --name ollama -p 11434:11434 ollama/ollama\n"
        "docker exec -it ollama ollama pull llama3.1:8b\n# Update backend/.env:\n"
        "#   LLM_PROVIDER=ollama   OLLAMA_BASE_URL=http://host.docker.internal:11434\n```\n\n"
        "## Upgrades in air-gapped environments\n\n"
        "```bash\ndocker load -i images.tar   # load new images\n./upgrade.sh                # zero-data-loss rolling restart\n```\n\n"
        "## Troubleshooting\n\n"
        "| Symptom | Fix |\n|---------|-----|\n"
        "| `pip: cannot find package XYZ` | Re-run `package-wheels.sh` on a Python 3.11 / manylinux2014 host |\n"
        "| `docker: image not found` | `docker images` — re-load `images.tar` |\n"
        "| Backend not ready after 60s | `docker compose logs backend` |\n"
        "| CORS errors in browser | Set `CORS_ORIGINS=https://your-host` in `backend/.env` then `./upgrade.sh` |\n"
        "| AI features disabled | Set one LLM key OR run Ollama. Admin Console → AI Copilot shows provider health. |\n"
    )

    # ─────────────────────────────────────────────────────
    #  ENTERPRISE.md — cheat-sheet
    # ─────────────────────────────────────────────────────
    (root / "ENTERPRISE.md").write_text(
        "# FalconOps AI — Enterprise Deployment Cheat-Sheet\n\n"
        "| File                                  | Purpose                                                  |\n"
        "|---------------------------------------|----------------------------------------------------------|\n"
        "| `install.sh`                          | One-command Docker/Podman install (online or `--offline`) |\n"
        "| `uninstall.sh`                        | Remove containers; optionally wipe data volume           |\n"
        "| `upgrade.sh`                          | Zero-data-loss rolling upgrade                           |\n"
        "| `AIRGAP.md`                           | Full air-gapped install playbook                         |\n"
        "| `PREREQUISITES.md`                    | Hardware / OS / firewall / API-key matrix                |\n"
        "| `QUICKSTART.md`                       | 5-minute getting-started                                 |\n"
        "| `docker-compose.yml`                  | Production compose (healthchecks + restart + log-rotate) |\n"
        "| `podman-compose.yml`                  | Rootless-friendly compose for RHEL/Podman                |\n"
        "| `backend/Dockerfile`                  | Multi-stage non-root build, vendor-wheel aware           |\n"
        "| `backend/vendor/*.whl`                | Vendored private wheels (incl. `emergentintegrations`)   |\n"
        "| `configs/{dev,prod,on-prem}.env`      | Environment-specific presets                             |\n"
        "| `scripts/package-images.sh`           | Pre-pull Docker images → images.tar                      |\n"
        "| `scripts/package-wheels.sh`           | Pre-download Python wheels → backend/vendor/             |\n"
        "| `scripts/license-mock.py`             | Generate evaluation license keys offline                 |\n"
        "| `scripts/install-systemd.sh`          | Register systemd services for bare-metal                 |\n"
        "| `kubernetes/*.yaml`                   | Raw K8s manifests                                        |\n"
        "| `kubernetes/helm/falconops/`          | Production-grade Helm chart                              |\n\n"
        "## LLM Provider Matrix (zero hard dependency)\n\n"
        "| Provider     | Env var(s)                                    | Cost    | Offline |\n"
        "|--------------|-----------------------------------------------|---------|---------|\n"
        "| **Ollama**   | `LLM_PROVIDER=ollama` `OLLAMA_BASE_URL=…`     | Free    | ✅ Yes   |\n"
        "| OpenAI       | `OPENAI_API_KEY=…`                            | Paid    | ❌ No    |\n"
        "| Anthropic    | `ANTHROPIC_API_KEY=…`                         | Paid    | ❌ No    |\n"
        "| Gemini       | `GOOGLE_API_KEY=…`                            | Paid    | ❌ No    |\n"
        "| Emergent     | `EMERGENT_LLM_KEY=…` (uses vendor wheel)      | Credits | ❌ No    |\n"
        "| Rule-based   | none — automatic fallback                     | Free    | ✅ Yes   |\n\n"
        "Switch any time from the Admin Console → AI Copilot tab.\n"
    )



def create_podman_assets(archive_dir: str):
    """Create Podman-specific files: podman-compose.yml, Quadlet units, podman-install.sh."""
    base = Path(archive_dir)

    # podman-compose.yml — almost identical to docker-compose.yml but with Podman-friendly defaults
    pc_yml = """version: "3.9"
# FalconOps AI — Podman Compose
# Compatible with `podman-compose` and `podman compose` (Podman 4+ has built-in compose).
# Designed for rootless Podman on RHEL / Rocky / Alma / Fedora / Ubuntu.

services:
  mongo:
    image: docker.io/mongo:7
    container_name: falconops-mongo
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    networks:
      - falconops-net
    # Rootless Podman: no port publishing to host by default; uncomment if needed
    # ports:
    #   - "127.0.0.1:27017:27017"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: falconops-backend
    restart: unless-stopped
    env_file:
      - ./backend/.env
    environment:
      - MONGO_URL=mongodb://mongo:27017
      - DB_NAME=falconops
    depends_on:
      - mongo
    networks:
      - falconops-net
    # Rootless Podman networking: backend reaches mongo via the falconops-net pod network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: falconops-frontend
    restart: unless-stopped
    env_file:
      - ./frontend/.env
    depends_on:
      - backend
    ports:
      - "8080:80"      # rootless Podman cannot bind to <1024 by default
    networks:
      - falconops-net

volumes:
  mongo_data:

networks:
  falconops-net:
    driver: bridge
"""
    (base / "podman-compose.yml").write_text(pc_yml)

    # Quadlet container units — for systemd-managed rootless Podman on RHEL 9
    quadlet_dir = base / "scripts" / "quadlet"
    quadlet_dir.mkdir(parents=True, exist_ok=True)

    (quadlet_dir / "falconops-mongo.container").write_text("""[Unit]
Description=FalconOps Mongo (Podman)
After=network-online.target

[Container]
ContainerName=falconops-mongo
Image=docker.io/mongo:7
Volume=falconops-mongo:/data/db
Network=falconops.network

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target default.target
""")

    (quadlet_dir / "falconops-backend.container").write_text("""[Unit]
Description=FalconOps Backend (Podman)
After=network-online.target falconops-mongo.service
Requires=falconops-mongo.service

[Container]
ContainerName=falconops-backend
Image=localhost/falconops-backend:latest
EnvironmentFile=%h/falconops/backend/.env
Network=falconops.network
PublishPort=127.0.0.1:8001:8001

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target default.target
""")

    (quadlet_dir / "falconops-frontend.container").write_text("""[Unit]
Description=FalconOps Frontend (Podman)
After=network-online.target falconops-backend.service
Requires=falconops-backend.service

[Container]
ContainerName=falconops-frontend
Image=localhost/falconops-frontend:latest
EnvironmentFile=%h/falconops/frontend/.env
Network=falconops.network
PublishPort=8080:80

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target default.target
""")

    (quadlet_dir / "falconops.network").write_text("""[Network]
NetworkName=falconops-net
Subnet=10.89.0.0/24
""")

    # README inside the quadlet folder
    (quadlet_dir / "README.md").write_text("""# Podman Quadlet Units (rootless, systemd-managed)

For RHEL 9 / Fedora 38+ where Quadlet is built into Podman.

## Install
```bash
mkdir -p ~/.config/containers/systemd
cp *.container *.network ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user enable --now falconops-mongo.service falconops-backend.service falconops-frontend.service
```

## Verify
```bash
systemctl --user status falconops-backend.service
podman ps
```

## Logs
```bash
journalctl --user -u falconops-backend.service -f
```
""")


PREREQUISITES_PAYLOAD = {
    "hardware": [
        {"tier": "Test / Demo", "vcpu": 2, "ram_gb": 4, "disk_gb": 20, "use_case": "Single-user evaluation"},
        {"tier": "Small Prod", "vcpu": 4, "ram_gb": 8, "disk_gb": 50, "use_case": "10–50 monitors, 5 users"},
        {"tier": "Standard Prod", "vcpu": 8, "ram_gb": 16, "disk_gb": 200, "use_case": "500 monitors, 25 users"},
        {"tier": "Enterprise", "vcpu": 16, "ram_gb": 32, "disk_gb": 500, "use_case": "2000+ monitors, 100+ users"},
    ],
    "supported_os": [
        "Ubuntu 20.04 / 22.04 / 24.04 LTS (recommended)",
        "Debian 11 / 12",
        "RHEL / Rocky / AlmaLinux 8 / 9",
        "Amazon Linux 2 / 2023",
    ],
    "docker_path": {
        "summary": "Recommended — 5 min install, 4 containers",
        "install_ubuntu": "curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER",
        "install_rhel": "sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin && sudo systemctl enable --now docker",
        "run": "./install-linux.sh   # pick option 1",
    },
    "podman_path": {
        "summary": "Rootless, daemonless — best for RHEL 9 / Rocky / Alma / Fedora",
        "install_ubuntu": "sudo apt update && sudo apt install -y podman podman-compose",
        "install_rhel": "sudo dnf install -y podman podman-compose",
        "run": "./install-linux.sh   # pick option 2 (Podman)",
        "rootless_notes": "Rootless Podman cannot bind ports < 1024. Frontend runs on 8080 by default; use a reverse proxy (Caddy / nginx) on 80/443 to publish externally.",
        "quadlet_systemd": "RHEL 9+ has Quadlet built in — see scripts/quadlet/README.md for systemd-managed units.",
    },
    "baremetal_path": {
        "summary": "Full control — systemd + nginx + mongo",
        "packages": [
            {"name": "Python", "version": "3.11+", "purpose": "Backend runtime"},
            {"name": "Node.js", "version": "18 or 20 LTS", "purpose": "Frontend build"},
            {"name": "Yarn", "version": "1.22+ (classic)", "purpose": "Frontend dep manager (npm not supported)"},
            {"name": "MongoDB", "version": "6.0+ or 7.0", "purpose": "Database"},
            {"name": "nginx", "version": "1.18+", "purpose": "Reverse proxy"},
            {"name": "gcc / libffi-dev", "version": "any", "purpose": "Building Python wheels"},
        ],
    },
    "ports": [
        {"port": "80 / 443", "direction": "inbound", "purpose": "nginx gateway (UI + API)"},
        {"port": "27017", "direction": "localhost", "purpose": "MongoDB (never expose publicly)"},
        {"port": "8001", "direction": "localhost", "purpose": "Backend uvicorn"},
        {"port": "6379", "direction": "localhost", "purpose": "Redis (optional)"},
    ],
    "api_keys": [
        {"key": "EMERGENT_LLM_KEY", "required": False, "where": "Emergent → Profile → Universal Key", "purpose": "AI agents"},
        {"key": "RESEND_API_KEY", "required": False, "where": "https://resend.com/api-keys", "purpose": "Scheduled report emails + OTP"},
        {"key": "STRIPE_API_KEY", "required": False, "where": "https://dashboard.stripe.com/apikeys", "purpose": "Billing"},
        {"key": "LICENSE_KEY", "required": True, "where": "Admin → Downloads → Generate", "purpose": "Enterprise features"},
    ],
    "credentials": {
        "admin": {"email": "admin@falconapps.com", "password": "Admin@123"},
        "viewer": {"email": "test@falconapps.com", "password": "testpass123"},
    },
    "verify_commands": [
        "docker compose ps",
        "curl http://localhost/api/health",
        "sudo systemctl status falconops-backend",
    ],
}


def _stream_archive(archive_path: str, format: str):
    """Shared helper: streams an archive and cleans up the temp dir afterwards."""
    filename = os.path.basename(archive_path)
    media_type = "application/zip" if format == "zip" else "application/gzip"

    def iterfile():
        with open(archive_path, "rb") as f:
            yield from f
        try:
            os.unlink(archive_path)
            temp_dir = os.path.dirname(archive_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/download/source")
async def download_source_package(
    include_docker: bool = Query(True, description="Include Docker configuration"),
    format: str = Query("tar.gz", description="Archive format: tar.gz or zip", regex="^(tar\\.gz|zip)$"),
    admin_user: dict = Depends(require_admin)
):
    """Download the application source code as tar.gz or zip (Admin only)."""
    try:
        archive_path = create_source_archive(include_docker=include_docker, archive_format=format)
        return _stream_archive(archive_path, format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create download package: {str(e)}")


@router.get("/download-with-token")
async def download_with_token(
    token: str = Query(..., min_length=32, description="One-time bundle download token"),
    format: str = Query("tar.gz", regex="^(tar\\.gz|zip)$"),
):
    """Public token-gated download of the on-prem bundle.

    Used by leads who came in through the public `/api/licenses/request-bundle` flow.
    Validates token, increments usage counter, streams the archive.
    """
    from .monetization_routes import validate_bundle_token
    rec = await validate_bundle_token(token)
    try:
        archive_path = create_source_archive(include_docker=True, archive_format=format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build package: {str(e)}")

    # Atomic increment of uses on success
    await db.bundle_tokens.update_one(
        {"token": token},
        {"$inc": {"uses": 1}, "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Log to the lead for the CRM
    if rec.get("lead_id"):
        await db.leads.update_one(
            {"id": rec["lead_id"]},
            {"$set": {
                "status": "qualified",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
             "$inc": {"download_count": 1}},
        )
    return _stream_archive(archive_path, format)


@router.get("/download/prerequisites")
async def get_linux_prerequisites(user: dict = Depends(require_auth)):
    """Return the full Linux prerequisites matrix (for UI rendering)."""
    return PREREQUISITES_PAYLOAD


@router.get("/download/agent")
async def download_agent_script(admin_user: dict = Depends(require_admin)):
    """Download the on-premise server monitoring agent script (Admin only)"""
    agent_path = Path("/app/backend/static/agents/falcon_agent_v2.py")
    
    if not agent_path.exists():
        # Fallback to v1
        agent_path = Path("/app/backend/static/agents/falconops_agent.py")
    
    if not agent_path.exists():
        raise HTTPException(status_code=404, detail="Agent script not found")
    
    return FileResponse(
        path=str(agent_path),
        filename="falcon_server_agent.py",
        media_type="text/x-python"
    )


@router.get("/download/db-agent")
async def download_db_agent_script(admin_user: dict = Depends(require_admin)):
    """Download the database monitoring agent script (Admin only)"""
    agent_path = Path("/app/backend/static/agents/falcon_db_agent.py")
    
    if not agent_path.exists():
        raise HTTPException(status_code=404, detail="DB Agent script not found")
    
    return FileResponse(
        path=str(agent_path),
        filename="falcon_db_agent.py",
        media_type="text/x-python"
    )


@router.get("/download/agents-info")
async def get_agents_info(user: dict = Depends(require_auth)):
    """Get info about all available agents for download"""
    agents = []
    
    # Server Agent
    srv_path = Path("/app/backend/static/agents/falcon_agent_v2.py")
    if not srv_path.exists():
        srv_path = Path("/app/backend/static/agents/falconops_agent.py")
    agents.append({
        "id": "server-agent",
        "name": "Server Monitoring Agent",
        "version": "2.0.0",
        "filename": "falcon_server_agent.py",
        "size_kb": round(srv_path.stat().st_size / 1024, 1) if srv_path.exists() else 0,
        "available": srv_path.exists(),
        "download_url": "/api/licenses/download/agent",
    })
    
    # DB Agent
    db_path = Path("/app/backend/static/agents/falcon_db_agent.py")
    agents.append({
        "id": "db-agent",
        "name": "Database Monitoring Agent",
        "version": "2.0.0",
        "filename": "falcon_db_agent.py",
        "size_kb": round(db_path.stat().st_size / 1024, 1) if db_path.exists() else 0,
        "available": db_path.exists(),
        "download_url": "/api/licenses/download/db-agent",
    })
    
    return {"agents": agents}


# ======================== FEATURE ACCESS CHECK ========================

@router.get("/features/{feature}")
async def check_feature(feature: str, user: dict = Depends(require_auth)):
    """Check if a specific feature is available in the current license"""
    license_data = await get_current_license()
    
    if not license_data:
        return {"feature": feature, "available": False, "reason": "No active license"}
    
    available = feature in license_data.get("features", [])
    
    return {
        "feature": feature,
        "available": available,
        "license_type": license_data.get("type"),
        "all_features": license_data.get("features", [])
    }
