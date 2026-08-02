from .base import MongoSeededAdapter
from ..config import SOURCE_COLLECTIONS


class ChangesAdapter(MongoSeededAdapter):
    """Deployment/change feed — what shipped, when, to which service, by whom.
    Without this, Phase 2 RCA and scenario S4 have nothing to correlate a
    root cause against."""
    source = "changes"
    collection_name = SOURCE_COLLECTIONS["changes"]
