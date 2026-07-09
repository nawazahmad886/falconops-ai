"""
FalconOps AI - Monitoring Agent Routes
Agent download, registration, and management API
"""
import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..utils.auth import require_auth

router = APIRouter(prefix="/api/agent", tags=["Monitoring Agent"])

AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static", "agents")


@router.get("/download/python")
async def download_python_agent(current_user: dict = Depends(require_auth)):
    """Download the FalconOps monitoring agent (Python)"""
    path = os.path.join(AGENT_DIR, "falcon_agent_v2.py")
    return FileResponse(path, filename="falcon_agent_v2.py", media_type="text/x-python")


@router.get("/install-script")
async def get_install_script(current_user: dict = Depends(require_auth)):
    """Get installation commands for the monitoring agent"""
    api_url = os.environ.get("REACT_APP_BACKEND_URL", "https://your-falconops-api.com")
    return {
        "install_steps": [
            {
                "step": 1,
                "title": "Download the agent",
                "command": f"curl -o falcon_agent.py {api_url}/api/agent/download/python -H 'Authorization: Bearer YOUR_TOKEN'"
            },
            {
                "step": 2,
                "title": "Install dependencies (optional, agent works without them)",
                "command": "pip install psutil requests"
            },
            {
                "step": 3,
                "title": "Run the agent",
                "command": f"python falcon_agent.py --api-url {api_url} --token YOUR_TOKEN --interval 30"
            },
            {
                "step": 4,
                "title": "Run as systemd service (Linux)",
                "command": "# Create /etc/systemd/system/falcon-agent.service with the config below"
            }
        ],
        "systemd_config": f"""[Unit]
Description=FalconOps Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
Environment=FALCON_API_URL={api_url}
Environment=FALCON_TOKEN=YOUR_TOKEN
ExecStart=/usr/bin/python3 /opt/falcon/falcon_agent.py --interval 30
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target""",
        "docker_command": f"docker run -d --name falcon-agent -e FALCON_API_URL={api_url} -e FALCON_TOKEN=YOUR_TOKEN falcon-agent:latest",
        "env_vars": {
            "FALCON_API_URL": "FalconOps API URL",
            "FALCON_TOKEN": "JWT authentication token",
            "FALCON_AGENT_TOKEN": "Pre-registered agent token (optional)",
        }
    }
