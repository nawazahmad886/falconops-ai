from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class MQAdapter(MongoSeededAdapter):
    """Message queue depth/backlog readings."""
    source = "mq"
    collection_name = SOURCE_COLLECTIONS["mq"]
