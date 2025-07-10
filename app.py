"""
대구수학축제 부스 예약 및 관리 시스템 - 리팩토링된 메인 애플리케이션

== 새로운 모듈 구조 ==
- app/__init__.py: Flask 앱 팩토리 및 Blueprint 등록
- app/config.py: 환경설정 및 상수
- app/db.py: 데이터베이스 연결 및 기본 함수들
- app/utils.py: 공통 유틸리티 함수들
- app/admin/: 관리자 관련 라우트 및 기능
- app/booth/: 부스 운영자 관련 라우트 및 기능
- app/student/: 학생 관련 라우트 및 기능
- app/main/: 메인 페이지 및 공통 라우트

이 구조로 기존 3187줄의 거대한 app.py를 여러 모듈로 분리하여
유지보수성과 가독성을 크게 향상시켰습니다.
"""

from app import create_app
from app.db import init_solapi

# Flask 앱 생성
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