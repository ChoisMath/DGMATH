"""
Railway deployment entry point
"""

import os
import sys

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("Starting Railway deployment...")
print(f"Current directory: {current_dir}")
print(f"Python path: {sys.path[:3]}")

try:
    from app import create_app
    from app.db import init_solapi
    
    print("✅ Imports successful")
    
    # Create Flask app
    app = create_app()
    print("✅ App created successfully")
    
    # Initialize SOLAPI SMS service
    with app.app_context():
        init_solapi()
    print("✅ SOLAPI initialized")
    
except Exception as e:
    print(f"❌ Error during setup: {e}")
    import traceback
    traceback.print_exc()
    
    # Create minimal fallback app
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        return f"Setup Error: {e}"
    
    @app.route('/health')
    def health():
        return "OK"

if __name__ == "__main__":
    print("Running in development mode...")
    app.run(debug=True, host='0.0.0.0', port=5000)