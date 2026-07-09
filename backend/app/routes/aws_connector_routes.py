"""
FalconOps AI - AWS Connector Routes
CloudTrail & VPC Flow Logs configuration and event fetching
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.aws_connectors import fetch_aws_events, CloudTrailConnector, VPCFlowLogConnector
from ..core.database import db

router = APIRouter(prefix="/api/aws", tags=["AWS Connectors"])


class AWSConnectorConfig(BaseModel):
    connector_type: str  # cloudtrail or vpc_flowlogs
    aws_access_key: Optional[str] = ""
    aws_secret_key: Optional[str] = ""
    aws_region: Optional[str] = "us-east-1"
    log_group: Optional[str] = "vpc-flow-logs"
    enabled: bool = True


@router.get("/connectors")
async def list_connectors(current_user: dict = Depends(require_auth)):
    """List configured AWS connectors"""
    ct = await db.integrations.find_one({"integration_id": "aws_cloudtrail"}, {"_id": 0})
    vpc = await db.integrations.find_one({"integration_id": "aws_vpc_flowlogs"}, {"_id": 0})
    return {
        "connectors": [
            {
                "id": "aws_cloudtrail",
                "name": "AWS CloudTrail",
                "type": "cloudtrail",
                "enabled": ct.get("enabled", False) if ct else False,
                "region": ct.get("config", {}).get("aws_region", "us-east-1") if ct else "us-east-1",
                "status": "configured" if ct else "not_configured",
            },
            {
                "id": "aws_vpc_flowlogs",
                "name": "AWS VPC Flow Logs",
                "type": "vpc_flowlogs",
                "enabled": vpc.get("enabled", False) if vpc else False,
                "region": vpc.get("config", {}).get("aws_region", "us-east-1") if vpc else "us-east-1",
                "status": "configured" if vpc else "not_configured",
            },
        ]
    }


@router.post("/connectors")
async def configure_connector(config: AWSConnectorConfig, current_user: dict = Depends(require_admin)):
    """Configure an AWS connector"""
    integration_id = f"aws_{config.connector_type}"
    doc = {
        "integration_id": integration_id,
        "enabled": config.enabled,
        "config": {
            "aws_access_key": config.aws_access_key,
            "aws_secret_key": config.aws_secret_key,
            "aws_region": config.aws_region,
            "log_group": config.log_group,
        },
    }
    await db.integrations.update_one(
        {"integration_id": integration_id},
        {"$set": doc},
        upsert=True,
    )
    return {"message": f"Connector {integration_id} configured", "enabled": config.enabled}


@router.post("/fetch")
async def fetch_events(current_user: dict = Depends(require_auth)):
    """Fetch events from all enabled AWS connectors"""
    results = await fetch_aws_events()
    return results


@router.get("/events/cloudtrail")
async def get_cloudtrail_events(
    limit: int = Query(20, le=50),
    current_user: dict = Depends(require_auth),
):
    """Fetch CloudTrail events (uses simulation if no AWS creds)"""
    config = await db.integrations.find_one({"integration_id": "aws_cloudtrail"}, {"_id": 0})
    connector = CloudTrailConnector(config.get("config", {}) if config else {})
    return await connector.fetch_events(limit)


@router.get("/events/vpc")
async def get_vpc_events(
    limit: int = Query(20, le=50),
    current_user: dict = Depends(require_auth),
):
    """Fetch VPC Flow Log events (uses simulation if no AWS creds)"""
    config = await db.integrations.find_one({"integration_id": "aws_vpc_flowlogs"}, {"_id": 0})
    connector = VPCFlowLogConnector(config.get("config", {}) if config else {})
    return await connector.fetch_logs(limit)
