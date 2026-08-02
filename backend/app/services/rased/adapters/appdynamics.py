from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class AppDynamicsAdapter(MongoSeededAdapter):
    """APM — exit-span latency/failure-rate metrics between services."""
    source = "appdynamics"
    collection_name = SOURCE_COLLECTIONS["appdynamics"]
