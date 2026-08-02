from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class DBAdapter(MongoSeededAdapter):
    """Database health — connection-pool usage, slow-query counts."""
    source = "db"
    collection_name = SOURCE_COLLECTIONS["db"]
