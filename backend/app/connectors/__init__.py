"""
FalconOps AI - Connector SDK

Importing this package registers every built-in connector into
CONNECTOR_REGISTRY (via each connector module's @register_connector
decorator, executed as an import side-effect). Deliberately imports only
`registry` + the connector modules here — NOT `service`/`scheduler`/
`ai_tool_bridge` (which depend on other app services and are imported
explicitly wherever they're used), so importing `app.connectors` itself can
never create an import cycle with the rest of the app.
"""
from . import registry  # noqa: F401
from .prometheus import connector as _prometheus_connector  # noqa: F401
from .aws import connector as _aws_connector  # noqa: F401
from .azure import connector as _azure_connector  # noqa: F401
from .gcp import connector as _gcp_connector  # noqa: F401
from .k8s import connector as _k8s_connector  # noqa: F401
