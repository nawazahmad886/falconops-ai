# FalconOps AI - Main Application Package
from .core.config import db, JWT_SECRET, JWT_ALGORITHM
from .core.database import get_database, close_database

__version__ = "1.0.0"
