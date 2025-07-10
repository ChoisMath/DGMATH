"""
대구수학축제 부스 예약 및 관리 시스템 - Railway 배포용 메인 애플리케이션

Railway gunicorn이 찾을 수 있도록 app 객체를 최상위에 노출합니다.
"""

from app import create_app
from app.db import init_solapi

# Flask 앱 생성 - Railway/gunicorn에서 찾을 수 있도록 app 변수로 노출
app = create_app()

# SOLAPI SMS 서비스 초기화
with app.app_context():
    init_solapi()

if __name__ == '__main__':
    print("="*50)
    print("🚀 대구수학축제 부스 예약 및 관리 시스템 시작")
    print("📁 새로운 모듈 구조로 실행 중...")
    print("="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
