"""
대구수학축제 부스 예약 및 관리 시스템 - Railway 배포용 메인 애플리케이션
"""

import os
from flask import Flask
from app.config import Config
from app.db import init_supabase, init_solapi

def create_app():
    """Flask 애플리케이션 팩토리"""
    flask_app = Flask(__name__, 
                     template_folder='templates',
                     static_folder='static')
    
    flask_app.config.from_object(Config)
    
    # Supabase 초기화
    init_supabase()
    
    # Blueprint 등록
    from app.main.routes import main_bp
    from app.admin.routes import admin_bp
    from app.booth.routes import booth_bp
    from app.student.routes import student_bp
    
    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(admin_bp, url_prefix='/admin')
    flask_app.register_blueprint(booth_bp)
    flask_app.register_blueprint(student_bp)
    
    return flask_app

# Railway/gunicorn을 위한 app 객체 생성
try:
    app = create_app()
    print("✅ App created successfully")
    
    # SOLAPI SMS 서비스 초기화
    with app.app_context():
        init_solapi()
        print("✅ SOLAPI initialized")
        
except Exception as e:
    print(f"❌ Error creating app: {e}")
    import traceback
    traceback.print_exc()
    
    # Fallback minimal app
    app = Flask(__name__)
    
    @app.route('/')
    def error_page():
        return f"Error: {e}"

if __name__ == '__main__':
    print("="*50)
    print("🚀 대구수학축제 부스 예약 및 관리 시스템 시작")
    print("📁 새로운 모듈 구조로 실행 중...")
    print("="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)