"""
FalconOps AI - Server Entry Point
This file imports the FastAPI app from the modular structure.
All logic has been migrated to /app/backend/app/
"""
# Import the app from the new modular structure
from main import app

# The app is now assembled in main.py from modular components:
# - app/routes/ - All API endpoints
# - app/models/ - Pydantic schemas
# - app/services/ - Business logic
# - app/core/ - Configuration and database
# - app/utils/ - Utilities (auth, etc.)
