"""
대구수학축제 부스 예약 및 관리 시스템 - Railway 배포용 메인 애플리케이션
"""

import os
from flask import Flask

print("🚀 Starting app initialization...")

try:
    # Get correct paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')

    print(f"📁 Project root: {project_root}")
    print(f"📁 Template directory: {template_dir}")
    print(f"📁 Templates exist: {os.path.exists(template_dir)}")

    # Create Flask app
    app = Flask(__name__, 
               template_folder=template_dir,
               static_folder=static_dir)

    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    print("✅ Basic Flask app created")
except Exception as e:
    print(f"❌ Error creating basic Flask app: {e}")
    # Create minimal fallback app
    app = Flask(__name__)
    app.secret_key = 'fallback-secret-key'

# Initialize database
try:
    from app.db import init_supabase, init_solapi
    init_supabase()
    print("✅ Supabase initialized")
    
    with app.app_context():
        init_solapi()
    print("✅ SOLAPI initialized")
except Exception as e:
    print(f"❌ Database initialization error: {e}")

# Register blueprints
try:
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)
    print(f"✅ main_bp registered")
except Exception as e:
    print(f"❌ Error registering main_bp: {e}")

try:
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    print(f"✅ admin_bp registered")
except Exception as e:
    print(f"❌ Error registering admin_bp: {e}")

try:
    from app.booth.routes import booth_bp
    app.register_blueprint(booth_bp)
    print(f"✅ booth_bp registered")
except Exception as e:
    print(f"❌ Error registering booth_bp: {e}")

try:
    from app.student.routes import student_bp
    app.register_blueprint(student_bp)
    print(f"✅ student_bp registered")
except Exception as e:
    print(f"❌ Error registering student_bp: {e}")

# Add health check
@app.route('/health')
def health_check():
    return {"status": "healthy", "message": "대구수학축제 시스템 정상 작동 중"}

# Print all routes for debugging
try:
    print("📋 All registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")
    
    print(f"Total routes registered: {len(list(app.url_map.iter_rules()))}")
    print("🎉 App setup completed successfully!")
except Exception as e:
    print(f"❌ Error listing routes: {e}")

# Ensure app object is available at module level
print(f"🔧 Setting app object in globals...")
globals()['app'] = app
print(f"✅ App object set: {type(app)}")

# Add fallback route if main blueprint failed to register
try:
    # Check if main.index route exists
    has_main_index = any(rule.endpoint == 'main.index' for rule in app.url_map.iter_rules())
    if not has_main_index:
        @app.route('/')
        def fallback_index():
            return "대구수학축제 부스 예약 및 관리 시스템 - Blueprint 로딩 실패"
        print("⚠️ Added fallback index route")
    else:
        print("✅ Main index route found, no fallback needed")
except Exception as e:
    print(f"❌ Error checking routes: {e}")
    @app.route('/')
    def emergency_fallback():
        return "시스템 로딩 중..."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)