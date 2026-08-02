from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class SolarWindsAdapter(MongoSeededAdapter):
    """Infra metrics — host/network-level counters (CPU, network flap events)."""
    source = "solarwinds"
    collection_name = SOURCE_COLLECTIONS["solarwinds"]
