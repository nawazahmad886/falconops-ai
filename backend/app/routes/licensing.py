"""
FalconOps AI - Licensing & Download Routes
License management and application download for on-premise deployment
"""
import os
import uuid
import tarfile
import tempfile
import shutil
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import io

from ..core.database import db
from ..utils.auth import require_auth, require_admin
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

router = APIRouter(prefix="/api/licensing", tags=["Licensing"])


# ======================== MODELS ========================

class LicenseActivation(BaseModel):
    license_key: str

class LicenseGeneration(BaseModel):
    organization: str
    license_type: str = "trial"  # trial, standard, professional, enterprise
    valid_days: int = 365


# ======================== LICENSE MANAGEMENT ========================

@router.get("/status")
async def get_license_status(current_user: dict = Depends(require_auth)):
    """Get current license status"""
    license_info = await get_current_license()
    
    if not license_info:
        return {
            "licensed": False,
            "message": "No active license. Please activate a license to use all features.",
            "trial_available": True
        }
    
    return {
        "licensed": True,
        "license_id": license_info.get("id"),
        "organization": license_info.get("organization"),
        "type": license_info.get("type"),
        "expires_at": license_info.get("expires_at"),
        "days_remaining": license_info.get("days_remaining"),
        "max_users": license_info.get("max_users"),
        "max_servers": license_info.get("max_servers"),
        "max_monitors": license_info.get("max_monitors"),
        "features": license_info.get("features", [])
    }


@router.post("/activate")
async def activate_license(
    activation: LicenseActivation,
    current_user: dict = Depends(require_admin)
):
    """Activate a license key"""
    # Validate the license key first
    validation = validate_license_key(activation.license_key)
    
    if not validation.get("valid"):
        raise HTTPException(status_code=400, detail=validation.get("error", "Invalid license key"))
    
    # Store the license
    result = await store_license(activation.license_key)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {
        "message": "License activated successfully",
        "license": result.get("license")
    }


@router.post("/validate")
async def validate_license(
    activation: LicenseActivation,
    current_user: dict = Depends(require_auth)
):
    """Validate a license key without activating"""
    validation = validate_license_key(activation.license_key)
    return validation


@router.delete("/revoke")
async def revoke_current_license(current_user: dict = Depends(require_admin)):
    """Revoke the current license (admin only)"""
    result = await revoke_license()
    return {"message": "License revoked", **result}


@router.get("/plans")
async def get_available_plans(current_user: Optional[dict] = Depends(require_auth)):
    """Get available license plans"""
    return get_license_plans()


@router.post("/generate")
async def generate_new_license(
    request: LicenseGeneration,
    current_user: dict = Depends(require_admin)
):
    """Generate a new license key (admin only - for testing)"""
    plan = LICENSE_PLANS.get(request.license_type)
    
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid license type")
    
    license_data = generate_license_key(
        organization=request.organization,
        license_type=request.license_type,
        max_users=plan["max_users"],
        max_servers=plan["max_servers"],
        max_monitors=plan["max_monitors"],
        valid_days=request.valid_days
    )
    
    return license_data


@router.get("/check-feature/{feature}")
async def check_feature(feature: str, current_user: dict = Depends(require_auth)):
    """Check if a feature is available in current license"""
    license_info = await get_current_license()
    
    if not license_info:
        return {"feature": feature, "available": False, "reason": "No active license"}
    
    features = license_info.get("features", [])
    available = feature in features
    
    return {
        "feature": feature,
        "available": available,
        "license_type": license_info.get("type")
    }


# ======================== APPLICATION DOWNLOAD ========================

@router.get("/download/info")
async def get_download_info(current_user: dict = Depends(require_admin)):
    """Get download information for the application"""
    return {
        "version": "1.0.0",
        "release_date": "2026-03-07",
        "files": [
            {
                "name": "falconops-ai-full.tar.gz",
                "description": "Complete application package (backend + frontend)",
                "size_estimate": "~50MB"
            },
            {
                "name": "falconops-agent.py",
                "description": "Server monitoring agent (Python)",
                "size_estimate": "~15KB"
            }
        ],
        "requirements": {
            "python": "3.9+",
            "node": "18+",
            "mongodb": "5.0+",
            "os": ["Linux", "macOS", "Windows (WSL)"]
        },
        "documentation": "https://docs.falconops.ai"
    }


@router.get("/download/agent")
async def download_agent(current_user: dict = Depends(require_admin)):
    """Download the server monitoring agent"""
    agent_path = "/app/backend/static/agents/falconops_agent.py"
    
    if not os.path.exists(agent_path):
        raise HTTPException(status_code=404, detail="Agent file not found")
    
    return FileResponse(
        agent_path,
        media_type="text/x-python",
        filename="falconops_agent.py"
    )


@router.get("/download/application")
async def download_application(current_user: dict = Depends(require_admin)):
    """Download the complete application as tar.gz"""
    
    # Check license
    license_info = await get_current_license()
    if not license_info:
        raise HTTPException(
            status_code=403, 
            detail="Active license required for application download. Please activate a license first."
        )
    
    # Create tar file in memory
    tar_buffer = io.BytesIO()
    
    try:
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            # Add backend files
            backend_path = "/app/backend"
            for root, dirs, files in os.walk(backend_path):
                # Skip cache and unnecessary directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules', '.pytest_cache', 'venv']]
                
                for file in files:
                    if file.endswith(('.pyc', '.pyo', '.log')):
                        continue
                    
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, "/app")
                    
                    try:
                        tar.add(file_path, arcname=f"falconops-ai/{arcname}")
                    except Exception as e:
                        continue
            
            # Add frontend files (source only, not node_modules)
            frontend_path = "/app/frontend"
            for root, dirs, files in os.walk(frontend_path):
                dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'build', 'dist']]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, "/app")
                    
                    try:
                        tar.add(file_path, arcname=f"falconops-ai/{arcname}")
                    except Exception as e:
                        continue
            
            # Add README and setup files
            readme_content = generate_readme()
            readme_info = tarfile.TarInfo(name="falconops-ai/README.md")
            readme_bytes = readme_content.encode('utf-8')
            readme_info.size = len(readme_bytes)
            tar.addfile(readme_info, io.BytesIO(readme_bytes))
            
            # Add docker-compose.yml
            docker_compose = generate_docker_compose()
            docker_info = tarfile.TarInfo(name="falconops-ai/docker-compose.yml")
            docker_bytes = docker_compose.encode('utf-8')
            docker_info.size = len(docker_bytes)
            tar.addfile(docker_info, io.BytesIO(docker_bytes))
            
            # Add setup script
            setup_script = generate_setup_script()
            setup_info = tarfile.TarInfo(name="falconops-ai/setup.sh")
            setup_bytes = setup_script.encode('utf-8')
            setup_info.size = len(setup_bytes)
            setup_info.mode = 0o755
            tar.addfile(setup_info, io.BytesIO(setup_bytes))
            
            # Add license info
            license_content = f"""# FalconOps AI License
Organization: {license_info.get('organization')}
License Type: {license_info.get('type')}
Expires: {license_info.get('expires_at')}
License Key: {license_info.get('license_key', 'N/A')}

Downloaded: {datetime.now(timezone.utc).isoformat()}
"""
            license_info_tar = tarfile.TarInfo(name="falconops-ai/LICENSE.txt")
            license_bytes = license_content.encode('utf-8')
            license_info_tar.size = len(license_bytes)
            tar.addfile(license_info_tar, io.BytesIO(license_bytes))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create archive: {str(e)}")
    
    tar_buffer.seek(0)
    
    return StreamingResponse(
        tar_buffer,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f"attachment; filename=falconops-ai-v1.0.0.tar.gz"
        }
    )


def generate_readme() -> str:
    """Generate README content for the download package"""
    return """# FalconOps AI - Enterprise AIOps Platform

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB 5.0+

### Installation

1. **Extract the archive:**
   ```bash
   tar -xzf falconops-ai-v1.0.0.tar.gz
   cd falconops-ai
   ```

2. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Or manual setup:**

   **Backend:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your MongoDB URL
   uvicorn server:app --host 0.0.0.0 --port 8001
   ```

   **Frontend:**
   ```bash
   cd frontend
   npm install  # or yarn install
   cp .env.example .env
   # Edit .env with your backend URL
   npm start  # or yarn start
   ```

### Docker Deployment

```bash
docker-compose up -d
```

### Configuration

Edit the `.env` files in both `backend/` and `frontend/` directories:

**Backend (.env):**
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=falconops
JWT_SECRET=your-secret-key
EMERGENT_LLM_KEY=your-llm-key  # Optional, for AI features
```

**Frontend (.env):**
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

### Default Credentials
- Email: admin@falconops.com
- Password: Admin@123

### Support
- Documentation: https://docs.falconops.ai
- Email: support@falconops.ai

---
FalconOps AI - Saudi Enterprise AI NOC Copilot
"""


def generate_docker_compose() -> str:
    """Generate docker-compose.yml content"""
    return """version: '3.8'

services:
  mongodb:
    image: mongo:5.0
    container_name: falconops-mongo
    restart: always
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=falconops

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: falconops-backend
    restart: always
    ports:
      - "8001:8001"
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=falconops
      - JWT_SECRET=${JWT_SECRET:-falconops-secret-2026}
    depends_on:
      - mongodb

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: falconops-frontend
    restart: always
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_BACKEND_URL=http://localhost:8001
    depends_on:
      - backend

volumes:
  mongo_data:
"""


def generate_setup_script() -> str:
    """Generate setup.sh script"""
    return """#!/bin/bash

echo "======================================"
echo "FalconOps AI - Setup Script"
echo "======================================"

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not installed."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is required but not installed."
    exit 1
fi

echo "Prerequisites OK!"

# Setup Backend
echo ""
echo "Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || echo "MONGO_URL=mongodb://localhost:27017
DB_NAME=falconops
JWT_SECRET=falconops-secret-$(date +%s)
ACCESS_TOKEN_EXPIRE_MINUTES=1440" > .env
fi

echo "Backend setup complete!"

# Setup Frontend
echo ""
echo "Setting up frontend..."
cd ../frontend

npm install || yarn install

if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
fi

echo "Frontend setup complete!"

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To start the application:"
echo ""
echo "1. Start MongoDB:"
echo "   mongod --dbpath /data/db"
echo ""
echo "2. Start Backend:"
echo "   cd backend && source venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8001"
echo ""
echo "3. Start Frontend:"
echo "   cd frontend && npm start"
echo ""
echo "Or use Docker:"
echo "   docker-compose up -d"
echo ""
"""
