from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class CMDBAdapter(MongoSeededAdapter):
    """Service catalogue / dependency records."""
    source = "cmdb"
    collection_name = SOURCE_COLLECTIONS["cmdb"]
