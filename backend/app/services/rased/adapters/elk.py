from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class ELKAdapter(MongoSeededAdapter):
    """Log search — error/warning entries synthetic services emitted."""
    source = "elk"
    collection_name = SOURCE_COLLECTIONS["elk"]
