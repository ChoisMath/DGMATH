"""
대구수학축제 부스 예약 및 관리 시스템 - 학생 모듈

이 패키지는 학생 관련 모든 기능을 포함합니다:
- 학생 계정 생성 및 로그인
- 학생 대시보드
- 부스 목록 조회 및 대기열 관리
- QR 체크인 및 소감 작성
- 활동 확인증 발급
- 학생 활동 기록 관리
"""

from .routes import student_bp, init_student_routes

__all__ = ['student_bp', 'init_student_routes']