"""
WSGI entry point for Railway deployment
"""

import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app import create_app
from app.db import init_solapi

# Create Flask app
application = create_app()

# Initialize SOLAPI SMS service
with application.app_context():
    init_solapi()

# Alias for gunicorn
app = application

if __name__ == "__main__":
    application.run()