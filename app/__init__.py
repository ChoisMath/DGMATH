from flask import Flask
from app.config import Config
from app.db import init_supabase

def create_app():
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    app.config.from_object(Config)
    
    # Supabase 초기화
    init_supabase()
    
    # Blueprint 등록
    from app.admin.routes import admin_bp
    from app.booth.routes import booth_bp
    
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(booth_bp)  # 부스 운영자 라우트는 prefix 없이 등록 (하위 호환성)
    
    return app