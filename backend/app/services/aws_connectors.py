"""
FalconOps AI - AWS CloudTrail & VPC Flow Logs Connector

Thin backward-compatible adapter over the Connector SDK's migrated AWS
connectors (app/connectors/aws/connector.py) — same discipline as the
broadcast_manager.py migration: existing callers (aws_connector_routes.py)
keep working against the same names/signatures, with zero external behavior
change to this module's own fetch_aws_events() orchestrator.

Note: fetch_aws_events() still funnels into security_service.ingest_security_event()
(db.security_events) — this is the legacy, manually-triggered path
(POST /api/aws/fetch). It is intentionally separate from the new Connector SDK
scheduler, which (once these connectors are enabled) polls automatically into
soc_ingestion_service (db.soc_events) instead. See the Connector SDK plan for
the flagged trade-off this creates if both paths are used for the same
integration.
"""
import logging
from typing import Dict

from ..core.database import db
from ..connectors.aws.connector import CloudTrailConnector, VPCFlowLogConnector

logger = logging.getLogger(__name__)

__all__ = ["CloudTrailConnector", "VPCFlowLogConnector", "fetch_aws_events"]


# ======================== CONNECTOR ORCHESTRATOR ========================

async def fetch_aws_events() -> Dict:
    """Fetch events from all configured AWS connectors and ingest them.

    Unchanged external behavior from before the SDK migration: still reads
    db.integrations directly (filtered on enabled:True, same as before), still
    ingests via security_service (not the new SDK's soc_ingestion_service
    path). Only the connectors' internals changed (no more simulated-data
    fallback when unconfigured — see connectors/aws/connector.py).

    Config secrets are decrypted here before use (connectors/crypto.py) —
    required now that aws_secret_key may be stored encrypted at rest; passing
    the raw stored value straight to boto3 would silently pass ciphertext as
    the credential."""
    from .security_service import ingest_security_event
    from .integration_management_service import INTEGRATION_CATALOG
    from ..connectors.crypto import decrypt_config_secrets

    catalog_by_id = {c["id"]: c for c in INTEGRATION_CATALOG}
    results = {"cloudtrail": 0, "vpc_flow": 0, "errors": []}

    ct_config = await db.integrations.find_one({"integration_id": "aws_cloudtrail", "enabled": True}, {"_id": 0})
    if ct_config:
        config = await decrypt_config_secrets(ct_config.get("config", {}), catalog_by_id.get("aws_cloudtrail"))
        connector = CloudTrailConnector(config)
        await connector.connect()
        events = await connector.fetch_events(50)
        for ev in events:
            await ingest_security_event(ev)
        results["cloudtrail"] = len(events)

    vpc_config = await db.integrations.find_one({"integration_id": "aws_vpc_flowlogs", "enabled": True}, {"_id": 0})
    if vpc_config:
        config = await decrypt_config_secrets(vpc_config.get("config", {}), catalog_by_id.get("aws_vpc_flowlogs"))
        connector = VPCFlowLogConnector(config)
        await connector.connect()
        logs = await connector.fetch_logs(50)
        for ev in logs:
            await ingest_security_event(ev)
        results["vpc_flow"] = len(logs)

    return results
