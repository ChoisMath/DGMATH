"""
대구수학축제 부스 예약 및 관리 시스템

== 시스템 개요 ==
이 시스템은 한국 축제 부스 체크인 웹 애플리케이션을 확장하여 온라인 대기열 관리 기능을 추가한 것입니다.

== 주요 기능 ==
1. 학생 시스템:
   - 계정 생성 및 로그인 (ID, 비밀번호, 개인정보, 연락처)
   - 부스 목록 조회 (실시간 대기인원 확인)
   - 부스 상세정보 조회 (PDF 첨부파일 지원)
   - 부스 대기열 신청 및 관리
   - 대기 순번 실시간 확인
   - SMS 알림 수신 (호출 시)
   - QR 코드 체크인 및 소감 작성
   - 활동 확인증 발급 (3개 이상 부스 체험 시)

2. 부스 운영자 시스템:
   - 운영자 계정 생성 및 로그인
   - 부스 생성 및 관리 (이름, 장소, 설명, PDF 첨부)
   - 대기열 실시간 모니터링
   - 학생 호출 및 SMS 발송
   - 학생 완료 처리
   - QR 코드 생성 및 관리

3. 관리자 시스템:
   - 학생 계정 관리
   - 부스 운영자 계정 관리
   - 부스 관리 및 모니터링
   - 전체 대기 현황 확인
   - 학생 활동 기록 관리   
   - 확인증 발급 관리
   - 전체 데이터 Excel 다운로드
   - 실시간 알림 모니터링

== 기술 스택 ==
- Backend: Python Flask
- Database: Supabase (PostgreSQL)
- Frontend: HTML/CSS/JavaScript (네온 테마)
- File Storage: Local filesystem
- PDF Generation: ReportLab
- QR Code: Python qrcode
- SMS: Placeholder (Twilio 연동 준비)

== 데이터베이스 구조 ==
- students: 학생 계정 정보
- booth_operators: 부스 운영자 계정 정보
- booths: 부스 정보 (이름, 장소, 설명, PDF 파일)
- queue_entries: 대기열 엔트리 (학생-부스 매핑, 상태 관리)
- notifications: SMS 알림 로그
- files: 첨부파일 정보
- checkins: 체크인 기록 (기존 기능)
- certificates: 발급된 확인증 정보
- settings: 시스템 설정 (행사명 등)

== 사용자 플로우 ==
1. 학생: 계정 생성 → 로그인 → 부스 조회 → 대기 신청 → SMS 알림 수신 → 부스 방문 → QR 체크인 → 확인증 발급
2. 운영자: 계정 생성 → 로그인 → 부스 생성 → 대기열 관리 → 학생 호출 → 완료 처리
3. 관리자: 로그인 → 계정 관리 → 부스 관리 → 대기 현황 모니터링 → 데이터 다운로드

== 보안 기능 ==
- 사용자 인증 및 권한 관리
- 세션 기반 로그인
- 관리자 페이지 접근 제어
- 파일 업로드 보안 (안전한 파일명 생성)
- 중복 방지 (계정, 부스명, 대기 신청)

== 실시간 기능 ==
- 부스 대기인원 실시간 업데이트
- 대기 순번 실시간 확인
- 관리자 대기 현황 자동 새로고침
- 알림 상태 실시간 모니터링
"""

import os
import base64
import hashlib
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session, flash
from supabase import create_client, Client
import pandas as pd
from io import BytesIO
import qrcode
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Supabase 초기화
try:
    # Supabase 설정
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jjjbhlwcjkaukkqplppm.supabase.co")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqamJobHdjamthdWtrcXBscHBtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDczMTkwNjQsImV4cCI6MjA2Mjg5NTA2NH0.3WJqsIG-F2pZ0nZE2j0NPnLTCPd37FEgYPD_F_1aw2M")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    SUPABASE_AVAILABLE = True
    print("Supabase 연결 성공!")
except Exception as e:
    print(f"Warning: Supabase 연결 실패. {e}")
    SUPABASE_AVAILABLE = False
    supabase = None

# SOLAPI SMS 설정 - 안전한 초기화
SOLAPI_AVAILABLE = False
solapi_service = None
SOLAPI_API_KEY = ""
SOLAPI_API_SECRET = ""
SOLAPI_SENDER_PHONE = ""

try:
    # SOLAPI 모듈 import 시도
    from solapi import SolapiMessageService
    print("SOLAPI 모듈 import 성공")
    
    # SOLAPI 설정 - Railway 서비스 변수에서 가져오기
    SOLAPI_API_KEY = os.environ.get("SOLAPI_API_KEY", "") or os.environ.get("SOLAPI_API", "")
    SOLAPI_API_SECRET = os.environ.get("SOLAPI_API_SECRET", "")
    SOLAPI_SENDER_PHONE = os.environ.get("SOLAPI_SENDER_PHONE", "")
    
    print(f"SOLAPI 환경변수 확인: API_KEY={'설정됨' if SOLAPI_API_KEY else '없음'}, API_SECRET={'설정됨' if SOLAPI_API_SECRET else '없음'}, SENDER_PHONE={'설정됨' if SOLAPI_SENDER_PHONE else '없음'}")
    
    # SOLAPI 사용 가능 여부 확인
    if SOLAPI_API_KEY and SOLAPI_API_SECRET and SOLAPI_SENDER_PHONE:
        try:
            solapi_service = SolapiMessageService(SOLAPI_API_KEY, SOLAPI_API_SECRET)
            SOLAPI_AVAILABLE = True
            print("✅ SOLAPI SMS 서비스 연결 성공!")
        except Exception as service_error:
            print(f"⚠️ SOLAPI 서비스 초기화 실패: {service_error}")
            SOLAPI_AVAILABLE = False
            solapi_service = None
    else:
        print("⚠️ SOLAPI 설정이 불완전합니다. SMS 기능이 비활성화됩니다.")
        print("필요한 환경변수:")
        print("- SOLAPI_API_KEY: SOLAPI API 키")
        print("- SOLAPI_API_SECRET: SOLAPI API 시크릿")  
        print("- SOLAPI_SENDER_PHONE: 발신번호 (예: 01012345678)")
        
except ImportError as e:
    print(f"⚠️ SOLAPI 모듈을 찾을 수 없습니다. SMS 기능이 비활성화됩니다. 오류: {e}")
    print("해결방법: pip install solapi")
except Exception as e:
    print(f"⚠️ SOLAPI 초기화 중 예상치 못한 오류: {e}")

# SOLAPI 초기화 완료 메시지
if SOLAPI_AVAILABLE:
    print("📱 SMS 발송 기능이 활성화되었습니다.")
else:
    print("📱 SMS 발송 기능이 비활성화되었습니다. (개발 모드로 작동)")
print("="*50)

app = Flask(__name__)
app.secret_key = os.urandom(24)

def check_database_tables():
    """데이터베이스 테이블 존재 여부 확인"""
    if not SUPABASE_AVAILABLE:
        return
    
    # 필요한 테이블들 확인
    tables_to_check = [
        ('students', 'Students table exists!'),
        ('checkins', 'Checkins table exists!'),
        ('certificates', 'Certificates table exists!'),
        ('booths', 'Booths table exists!'),
        ('settings', 'Settings table exists!'),
        ('booth_operators', 'Booth operators table exists!'),
        ('queue_entries', 'Queue entries table exists!'),
        ('notifications', 'Notifications table exists!'),
        ('files', 'Files table exists!')
    ]
    
    for table_name, success_msg in tables_to_check:
        try:
            result = supabase.table(table_name).select('id').limit(1).execute()
            print(success_msg)
        except Exception as e:
            print(f"Warning: {table_name} table not found. Please create it manually in Supabase.")
            
            if table_name == 'students':
                print("""
CREATE TABLE students (
  id SERIAL PRIMARY KEY,
  student_id VARCHAR(20) UNIQUE NOT NULL,
  password VARCHAR(100) NOT NULL,
  school VARCHAR(100) NOT NULL,
  grade INTEGER NOT NULL,
  class INTEGER NOT NULL,
  number INTEGER NOT NULL,
  name VARCHAR(50) NOT NULL,
  phone VARCHAR(20),
  email VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);""")
            elif table_name == 'certificates':
                print("""
CREATE TABLE certificates (
  id SERIAL PRIMARY KEY,
  certificate_number VARCHAR(20) UNIQUE NOT NULL,
  school VARCHAR(100) NOT NULL,
  grade INTEGER NOT NULL,
  class INTEGER NOT NULL,
  number INTEGER NOT NULL,
  name VARCHAR(50) NOT NULL,
  booth_names TEXT[], -- 체험한 부스명 배열
  booth_count INTEGER NOT NULL,
  issued_at TIMESTAMP DEFAULT NOW()
);""")
            elif table_name == 'booths':
                print("""
CREATE TABLE booths (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  location VARCHAR(200),
  pdf_file_path VARCHAR(500),
  operator_id INTEGER,
  is_active BOOLEAN DEFAULT true,
  qr_file_path VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);""")
            elif table_name == 'settings':
                print("""
CREATE TABLE settings (
  id SERIAL PRIMARY KEY,
  key VARCHAR(100) UNIQUE NOT NULL,
  value TEXT,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default event name
INSERT INTO settings (key, value, description) VALUES 
('event_name', '대구수학축제', '행사명');
""")
            elif table_name == 'booth_operators':
                print("""
CREATE TABLE booth_operators (
  id SERIAL PRIMARY KEY,
  operator_id VARCHAR(20) UNIQUE NOT NULL,
  password VARCHAR(100) NOT NULL,
  school VARCHAR(100) NOT NULL,
  club_name VARCHAR(100) NOT NULL,
  booth_topic VARCHAR(200) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  email VARCHAR(100) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);""")
            elif table_name == 'queue_entries':
                print("""
CREATE TABLE queue_entries (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL,
  booth_id INTEGER NOT NULL,
  queue_position INTEGER NOT NULL,
  status VARCHAR(20) DEFAULT 'waiting', -- waiting, called, completed, cancelled
  applied_at TIMESTAMP DEFAULT NOW(),
  called_at TIMESTAMP,
  completed_at TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
);""")
            elif table_name == 'notifications':
                print("""
CREATE TABLE notifications (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL,
  booth_id INTEGER NOT NULL,
  message TEXT NOT NULL,
  phone VARCHAR(20) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending', -- pending, sent, failed
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
);""")
            elif table_name == 'files':
                print("""
CREATE TABLE files (
  id SERIAL PRIMARY KEY,
  booth_id INTEGER NOT NULL,
  filename VARCHAR(255) NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size INTEGER NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  uploaded_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
);""")

# 앱 시작시 데이터베이스 확인
check_database_tables()

def get_event_name():
    """행사명 가져오기"""
    if not SUPABASE_AVAILABLE:
        return "대구수학축제"
    
    try:
        result = supabase.table('settings').select('value').eq('key', 'event_name').execute()
        if result.data:
            return result.data[0]['value']
        else:
            return "대구수학축제"
    except:
        return "대구수학축제"

def set_event_name(event_name):
    """행사명 설정"""
    if not SUPABASE_AVAILABLE:
        return False
    
    try:
        # 기존 설정이 있는지 확인
        existing = supabase.table('settings').select('id').eq('key', 'event_name').execute()
        
        if existing.data:
            # 업데이트
            result = supabase.table('settings').update({
                'value': event_name,
                'updated_at': 'now()'
            }).eq('key', 'event_name').execute()
        else:
            # 새로 생성
            result = supabase.table('settings').insert({
                'key': 'event_name',
                'value': event_name,
                'description': '행사명'
            }).execute()
        
        return True
    except Exception as e:
        print(f"행사명 설정 중 오류: {str(e)}")
        # settings 테이블이 없는 경우를 체크
        if 'relation "public.settings" does not exist' in str(e):
            print("Settings 테이블이 존재하지 않습니다. 테이블을 생성해주세요.")
        return False

def generate_certificate_number():
    """대수페-25-0001 형식의 순차 인증서 번호 생성"""
    if not SUPABASE_AVAILABLE:
        return "대수페-25-TEMP"
    
    try:
        # 최신 인증서 번호 조회
        result = supabase.table('certificates').select('certificate_number').order('id', desc=True).limit(1).execute()
        
        if result.data:
            last_number = result.data[0]['certificate_number']
            # "대수페-25-0001" 형식에서 마지막 숫자 추출
            parts = last_number.split('-')
            if len(parts) == 3 and parts[0] == '대수페' and parts[1] == '25':
                last_seq = int(parts[2])
                new_seq = last_seq + 1
            else:
                new_seq = 1
        else:
            new_seq = 1
        
        return f"대수페-25-{new_seq:04d}"
    except Exception as e:
        # 오류 발생 시 현재 시간 기반 번호 생성
        return f"대수페-25-{datetime.now().strftime('%m%d%H%M')}"

def encrypt_password(password):
    """비밀번호를 암호화 (Base64 + MD5 해시)"""
    try:
        # MD5 해시 생성
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        # Base64 인코딩
        encoded = base64.b64encode(md5_hash.encode()).decode()
        return encoded
    except:
        return "***ENCRYPTED***"

def send_sms_notification(phone_number, message, booth_id=None, student_id=None):
    """SOLAPI를 사용한 SMS 알림 발송"""
    try:
        if not SOLAPI_AVAILABLE:
            print(f"SMS 발송 (개발 모드 - SOLAPI 비활성화): {phone_number} - {message}")
            return True
        
        # 전화번호 형식 정리 (하이픈 제거, 국가번호 처리)
        clean_phone = phone_number.replace('-', '').replace(' ', '')
        if clean_phone.startswith('010'):
            clean_phone = '+82' + clean_phone[1:]  # 010 -> +8210
        elif not clean_phone.startswith('+82'):
            clean_phone = '+82' + clean_phone
            
        # SOLAPI 메시지 발송
        message_data = {
            'to': clean_phone,
            'from': SOLAPI_SENDER_PHONE,
            'text': message,
            'type': 'SMS'  # SMS, LMS, MMS 중 선택
        }
        
        response = solapi_service.send_one(message_data)
        
        # 응답 확인
        if response and response.get('statusCode') == '2000':
            print(f"SMS 발송 성공: {phone_number} - {message}")
            
            # SMS 발송 로그를 notifications 테이블에 저장
            if SUPABASE_AVAILABLE and booth_id and student_id:
                try:
                    notification_data = {
                        'student_id': student_id,
                        'booth_id': booth_id,
                        'message': message,
                        'phone': phone_number,
                        'status': 'sent',
                        'solapi_message_id': response.get('messageId', ''),
                        'created_at': datetime.now().isoformat()
                    }
                    supabase.table('notifications').insert(notification_data).execute()
                except Exception as db_error:
                    print(f"SMS 로그 저장 실패: {str(db_error)}")
            
            return True
        else:
            error_msg = response.get('errorMessage', '알 수 없는 오류') if response else '응답 없음'
            print(f"SMS 발송 실패: {phone_number} - {error_msg}")
            return False
            
    except Exception as e:
        print(f"SMS 발송 중 오류 발생: {str(e)}")
        return False

def send_bulk_sms_notification(recipients, message, booth_id=None):
    """다수 수신자에게 SMS 일괄 발송"""
    try:
        if not SOLAPI_AVAILABLE:
            print(f"SMS 일괄 발송 (개발 모드 - SOLAPI 비활성화): {len(recipients)}명에게 발송")
            return True
        
        if not recipients:
            return True
            
        # 메시지 데이터 준비
        messages = []
        for recipient in recipients:
            phone_number = recipient.get('phone', '')
            student_id = recipient.get('student_id', None)
            
            # 전화번호 형식 정리
            clean_phone = phone_number.replace('-', '').replace(' ', '')
            if clean_phone.startswith('010'):
                clean_phone = '+82' + clean_phone[1:]
            elif not clean_phone.startswith('+82'):
                clean_phone = '+82' + clean_phone
                
            messages.append({
                'to': clean_phone,
                'from': SOLAPI_SENDER_PHONE,
                'text': message,
                'type': 'SMS',
                'customFields': {
                    'student_id': str(student_id) if student_id else '',
                    'booth_id': str(booth_id) if booth_id else ''
                }
            })
        
        # SOLAPI 일괄 발송
        response = solapi_service.send_many(messages)
        
        if response and response.get('statusCode') == '2000':
            print(f"SMS 일괄 발송 성공: {len(recipients)}명")
            
            # 발송 로그 저장
            if SUPABASE_AVAILABLE and booth_id:
                try:
                    notification_logs = []
                    for recipient in recipients:
                        notification_logs.append({
                            'student_id': recipient.get('student_id'),
                            'booth_id': booth_id,
                            'message': message,
                            'phone': recipient.get('phone', ''),
                            'status': 'sent',
                            'solapi_group_id': response.get('groupId', ''),
                            'created_at': datetime.now().isoformat()
                        })
                    
                    if notification_logs:
                        supabase.table('notifications').insert(notification_logs).execute()
                except Exception as db_error:
                    print(f"SMS 일괄 발송 로그 저장 실패: {str(db_error)}")
            
            return True
        else:
            error_msg = response.get('errorMessage', '알 수 없는 오류') if response else '응답 없음'
            print(f"SMS 일괄 발송 실패: {error_msg}")
            return False
            
    except Exception as e:
        print(f"SMS 일괄 발송 중 오류 발생: {str(e)}")
        return False

def create_qr_with_text(qr_img, booth_name):
    """QR 코드 위에 부스명 텍스트를 추가한 이미지 생성"""
    try:
        # QR 코드 크기
        qr_width, qr_height = qr_img.size
        
        # 텍스트 영역을 위한 여백 계산
        text_height = 80
        total_height = qr_height + text_height + 40  # 여백 포함
        
        # 새 이미지 생성 (흰색 배경)
        final_img = Image.new('RGB', (qr_width, total_height), 'white')
        
        # QR 코드를 상단에 배치
        final_img.paste(qr_img, (0, 20))
        
        # 텍스트 그리기
        draw = ImageDraw.Draw(final_img)
        
        # 폰트 설정 (기본 폰트 사용)
        try:
            # 시스템에 따라 한글 지원 폰트 시도
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("malgun.ttf", 24)  # Windows
            except:
                font = ImageFont.load_default()
        
        # 텍스트 크기 계산
        bbox = draw.textbbox((0, 0), booth_name, font=font)
        text_width = bbox[2] - bbox[0]
        
        # 중앙 정렬
        text_x = (qr_width - text_width) // 2
        text_y = qr_height + 30
        
        # 텍스트 그리기
        draw.text((text_x, text_y), booth_name, fill='black', font=font)
        
        return final_img
        
    except Exception as e:
        print(f"텍스트 추가 중 오류: {e}")
        # 오류 발생 시 원본 QR 코드 반환
        return qr_img

def save_qr_code_file(booth_name, img):
    """생성된 QR 코드를 파일로 저장"""
    try:
        # static/qr_codes 디렉토리가 없으면 생성
        import os
        static_dir = 'static'
        qr_dir = 'static/qr_codes'
        
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
        if not os.path.exists(qr_dir):
            os.makedirs(qr_dir)
        
        # 파일명에서 특수문자 제거
        safe_name = "".join(c for c in booth_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{qr_dir}/qr_{safe_name}.png"
        
        # 이미지 저장
        img.save(filename, 'PNG')
        
        # 부스 테이블에 QR 파일 경로 업데이트
        if SUPABASE_AVAILABLE:
            supabase.table('booths').update({
                'qr_file_path': filename
            }).eq('name', booth_name).execute()
            
    except Exception as e:
        print(f"QR 코드 파일 저장 중 오류: {e}")

def generate_certificate_pdf(student_info, booth_records, cert_id, event_name):
    """새로운 형식의 확인증 PDF 생성"""
    buffer = BytesIO()
    
    # A4 용지 크기로 PDF 문서 생성
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=30*mm, leftMargin=30*mm,
                          topMargin=20*mm, bottomMargin=20*mm)
    
    # 스타일 설정
    styles = getSampleStyleSheet()
    
    # 한글 폰트 등록
    font_name = 'Helvetica'  # 기본값
    try:
        # 프로젝트에 포함된 나눔고딕 폰트 사용
        font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'NanumGothic.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
            font_name = 'NanumGothic'
        else:
            # 폰트 파일이 없으면 CID 폰트 사용
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            font_name = 'HeiseiMin-W3'
    except Exception as e:
        print(f"폰트 등록 중 오류: {e}")
        # 오류 발생 시 기본 폰트 사용
        font_name = 'Helvetica'
    
    # 커스텀 스타일 정의
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName=font_name,
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.black
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=15,
        textColor=colors.black
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=12,
        alignment=TA_LEFT,
        spaceAfter=10,
        textColor=colors.black
    )
    
    center_style = ParagraphStyle(
        'CenterStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=colors.black
    )
    
    # PDF 내용 구성
    story = []
    
    # 1. 좌측 상단에 발급번호
    cert_number_text = f"발급번호: {cert_id}"
    cert_number_style = ParagraphStyle(
        'CertNumberStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.grey
    )
    story.append(Paragraph(cert_number_text, cert_number_style))
    story.append(Spacer(1, 20))
    
    # 2. 상단 가운데에 행사명
    title_text = f"{event_name} 활동 확인서"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 20))
    
    # 3. 학생 정보
    student_info_text = f"""
    <b>학교:</b> {student_info['school']}<br/>
    <b>학급:</b> {student_info['grade']}학년 {student_info['class']}반 {student_info['number']}번<br/>
    <b>이름:</b> {student_info['name']}<br/>
    <b>체험 부스 수:</b> {len(booth_records)}개
    """
    story.append(Paragraph(student_info_text, normal_style))
    story.append(Spacer(1, 20))
    
    # 4. 체험 부스 목록
    if booth_records:
        story.append(Paragraph("<b>체험한 부스 목록</b>", normal_style))
        story.append(Spacer(1, 10))
        
        # 테이블 데이터 준비
        table_data = [['번호', '부스명', '소감']]
        for i, (booth_name, record) in enumerate(booth_records.items(), 1):
            comment = record.get('comment', '소감 없음')
            if len(comment) > 50:  # 긴 소감은 줄임
                comment = comment[:47] + "..."
            table_data.append([str(i), booth_name, comment])
        
        # 테이블 생성
        table = Table(table_data, colWidths=[20*mm, 50*mm, 80*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
        story.append(Spacer(1, 30))
    
    # 5. 확인 문구
    confirmation_text = f"""
    위 학생은 대구광역시교육청이 주최•주관하고, 대구중등수학교육연구회가 운영한 
    '{event_name}'에 참여하여 창의적 체험활동을 하였으므로 위 내용을 확인합니다.
    """
    story.append(Paragraph(confirmation_text, center_style))
    story.append(Spacer(1, 30))
    
    # 6. 발급일자
    issue_date = datetime.now().strftime('%Y년 %m월 %d일')
    story.append(Paragraph(f"발급일: {issue_date}", center_style))
    story.append(Spacer(1, 40))
    
    # 7. 발급기관 및 전자관인
    story.append(Paragraph("대구중등수학교육연구회장", center_style))
    story.append(Spacer(1, 20))
    
    # 전자관인 이미지 추가
    # 1순위: 관리자가 업로드한 커스텀 관인 (static/seal.png)
    # 2순위: 기본 관인 (image/GanIn.png)
    custom_seal_path = 'static/seal.png'
    default_seal_path = 'image/GanIn.png'
    
    seal_path = None
    if os.path.exists(custom_seal_path):
        seal_path = custom_seal_path
    elif os.path.exists(default_seal_path):
        seal_path = default_seal_path
    
    if seal_path:
        try:
            seal_img = RLImage(seal_path, width=60, height=60)
            seal_img.hAlign = 'CENTER'
            story.append(seal_img)
        except:
            # 이미지 로드 실패시 텍스트로 대체
            story.append(Paragraph("(관인)", center_style))
    else:
        story.append(Paragraph("(관인)", center_style))
    
    # PDF 생성
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- 학생 정보 입력 페이지 ---
@app.route('/student_info')
def student_info():
    return render_template('student_info.html')

# --- 학생 계정 생성 API ---
@app.route('/api/create-student-account', methods=['POST'])
def api_create_student_account():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # 중복 확인: 같은 학교, 학년, 반, 번호
        existing = supabase.table('students').select('*').eq('school', data['school']).eq('grade', int(data['grade'])).eq('class', int(data['class'])).eq('number', int(data['number'])).execute()
        
        if existing.data:
            return jsonify({'ok': False, 'message': '이미 등록된 학생입니다.'})
        
        # ID 중복 확인
        existing_id = supabase.table('students').select('*').eq('student_id', data['student_id']).execute()
        
        if existing_id.data:
            return jsonify({'ok': False, 'message': '이미 사용 중인 ID입니다.'})
        
        # 새 학생 계정 생성
        student_data = {
            'student_id': data['student_id'],
            'password': data['password'],  # 실제 환경에서는 해시화 필요
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name'],
            'phone': data.get('phone', ''),
            'email': data.get('email', '')
        }
        
        result = supabase.table('students').insert(student_data).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '계정이 생성되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '계정 생성에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'계정 생성 중 오류: {str(e)}'})

# --- 학생 로그인 API ---
@app.route('/api/student-login', methods=['POST'])
def api_student_login():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # 학생 계정 조회
        result = supabase.table('students').select('*').eq('student_id', data['student_id']).eq('password', data['password']).execute()
        
        if result.data:
            student = result.data[0]
            return jsonify({
                'ok': True,
                'student': {
                    'id': student['id'],
                    'school': student['school'],
                    'grade': student['grade'],
                    'class': student['class'],
                    'number': student['number'],
                    'name': student['name'],
                    'phone': student.get('phone', ''),
                    'email': student.get('email', '')
                }
            })
        else:
            return jsonify({'ok': False, 'message': 'ID 또는 비밀번호가 틀렸습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'로그인 중 오류: {str(e)}'})

# --- ID 중복 확인 API ---
@app.route('/api/check-id-duplicate', methods=['POST'])
def api_check_id_duplicate():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'available': False, 'message': 'Supabase가 설정되지 않았습니다.'}), 500
    
    data = request.get_json()
    student_id = data.get('student_id', '')
    
    if not student_id:
        return jsonify({'ok': False, 'available': False, 'message': 'ID를 입력해주세요.'})
    
    try:
        # ID 중복 확인
        result = supabase.table('students').select('id').eq('student_id', student_id).execute()
        
        if result.data:
            return jsonify({'ok': False, 'available': False, 'message': '이미 사용 중인 ID입니다.'})
        else:
            return jsonify({'ok': True, 'available': True, 'message': '사용 가능한 ID입니다.'})
            
    except Exception as e:
        error_msg = str(e)
        print(f"ID 중복확인 오류: {error_msg}")  # 서버 로그에 출력
        
        # students 테이블이 없는 경우
        if 'relation "public.students" does not exist' in error_msg:
            return jsonify({
                'ok': False, 
                'available': False, 
                'message': 'students 테이블이 생성되지 않았습니다. 관리자에게 문의하세요.'
            })
        else:
            return jsonify({'ok': False, 'available': False, 'message': f'ID 확인 중 오류: {error_msg}'})

# --- 학생 로그인 페이지 ---
@app.route('/student-login')
def student_login():
    booth = request.args.get('booth', '')
    return render_template('student_login.html', booth=booth)

# --- 부스 운영자 계정 생성 페이지 ---
@app.route('/booth-operator-register')
def booth_operator_register():
    return render_template('booth_operator_register.html')

# --- 부스 운영자 계정 생성 API ---
@app.route('/api/create-booth-operator-account', methods=['POST'])
def api_create_booth_operator_account():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # ID 중복 확인
        existing_id = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).execute()
        
        if existing_id.data:
            return jsonify({'ok': False, 'message': '이미 사용 중인 ID입니다.'})
        
        # 새 부스 운영자 계정 생성
        operator_data = {
            'operator_id': data['operator_id'],
            'password': data['password'],  # 실제 환경에서는 해시화 필요
            'school': data['school'],
            'club_name': data['club_name'],
            'booth_topic': data['booth_topic'],
            'name': data['name'],
            'phone': data['phone'],
            'email': data['email']
        }
        
        result = supabase.table('booth_operators').insert(operator_data).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '부스 운영자 계정이 생성되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '계정 생성에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'계정 생성 중 오류: {str(e)}'})

# --- 부스 운영자 ID 중복 확인 API ---
@app.route('/api/check-operator-id-duplicate', methods=['POST'])
def api_check_operator_id_duplicate():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'available': False, 'message': 'Supabase가 설정되지 않았습니다.'}), 500
    
    data = request.get_json()
    operator_id = data.get('operator_id', '')
    
    if not operator_id:
        return jsonify({'ok': False, 'available': False, 'message': 'ID를 입력해주세요.'})
    
    try:
        # ID 중복 확인
        result = supabase.table('booth_operators').select('id').eq('operator_id', operator_id).execute()
        
        if result.data:
            return jsonify({'ok': False, 'available': False, 'message': '이미 사용 중인 ID입니다.'})
        else:
            return jsonify({'ok': True, 'available': True, 'message': '사용 가능한 ID입니다.'})
            
    except Exception as e:
        error_msg = str(e)
        print(f"부스 운영자 ID 중복확인 오류: {error_msg}")
        
        if 'relation "public.booth_operators" does not exist' in error_msg:
            return jsonify({
                'ok': False, 
                'available': False, 
                'message': 'booth_operators 테이블이 생성되지 않았습니다. 관리자에게 문의하세요.'
            })
        else:
            return jsonify({'ok': False, 'available': False, 'message': f'ID 확인 중 오류: {error_msg}'})

# --- 부스 운영자 로그인 페이지 ---
@app.route('/booth-operator-login')
def booth_operator_login():
    return render_template('booth_operator_login.html')

# --- 부스 운영자 로그인 API ---
@app.route('/api/booth-operator-login', methods=['POST'])
def api_booth_operator_login():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # 부스 운영자 계정 조회
        result = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).eq('password', data['password']).execute()
        
        if result.data:
            operator = result.data[0]
            return jsonify({
                'ok': True,
                'operator': {
                    'id': operator['id'],
                    'operator_id': operator['operator_id'],
                    'school': operator['school'],
                    'club_name': operator['club_name'],
                    'booth_topic': operator['booth_topic'],
                    'phone': operator['phone'],
                    'email': operator['email']
                }
            })
        else:
            return jsonify({'ok': False, 'message': 'ID 또는 비밀번호가 틀렸습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'로그인 중 오류: {str(e)}'})

# --- 부스 운영자 대시보드 ---
@app.route('/booth-operator-dashboard')
def booth_operator_dashboard():
    return render_template('booth_operator_dashboard.html')

# --- 부스 생성 API ---
@app.route('/api/create-booth', methods=['POST'])
def api_create_booth():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        name = request.form.get('name')
        location = request.form.get('location')
        description = request.form.get('description')
        operator_id = request.form.get('operator_id')
        
        if not name or not location or not description or not operator_id:
            return jsonify({'ok': False, 'message': '필수 정보가 누락되었습니다.'})
        
        # 부스명 중복 확인
        existing_booth = supabase.table('booths').select('*').eq('name', name).execute()
        if existing_booth.data:
            return jsonify({'ok': False, 'message': '이미 존재하는 부스명입니다.'})
        
        # 부스 데이터 생성
        booth_data = {
            'name': name,
            'location': location,
            'description': description,
            'operator_id': int(operator_id),
            'is_active': True
        }
        
        # PDF 파일 처리
        pdf_file = request.files.get('pdf_file')
        if pdf_file and pdf_file.filename:
            # 업로드 디렉토리 생성
            upload_dir = 'static/uploads/booth_pdfs'
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)
            
            # 안전한 파일명 생성
            import uuid
            safe_filename = f"{uuid.uuid4()}_{pdf_file.filename}"
            file_path = os.path.join(upload_dir, safe_filename)
            
            # 파일 저장
            pdf_file.save(file_path)
            booth_data['pdf_file_path'] = file_path
        
        # 부스 생성
        result = supabase.table('booths').insert(booth_data).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '부스가 성공적으로 생성되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '부스 생성에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 생성 중 오류: {str(e)}'})

# --- 운영자 부스 목록 API ---
@app.route('/api/operator-booths', methods=['POST'])
def api_operator_booths():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    operator_id = data.get('operator_id')
    
    if not operator_id:
        return jsonify({'ok': False, 'message': '운영자 ID가 필요합니다.'})
    
    try:
        result = supabase.table('booths').select('*').eq('operator_id', operator_id).order('created_at', desc=True).execute()
        
        booths = result.data if result.data else []
        return jsonify({'ok': True, 'booths': booths})
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 목록 조회 중 오류: {str(e)}'})

# --- 부스 대기열 조회 API ---
@app.route('/api/booth-queue', methods=['POST'])
def api_booth_queue():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    booth_id = data.get('booth_id')
    
    if not booth_id:
        return jsonify({'ok': False, 'message': '부스 ID가 필요합니다.'})
    
    try:
        # 대기열 조회 (학생 정보 포함)
        result = supabase.table('queue_entries').select('''
            *, 
            students!inner(name, school, grade, class, number, phone)
        ''').eq('booth_id', booth_id).order('queue_position', desc=False).execute()
        
        queue = []
        if result.data:
            for entry in result.data:
                student = entry['students']
                queue.append({
                    'id': entry['id'],
                    'student_name': student['name'],
                    'student_school': student['school'],
                    'student_grade': student['grade'],
                    'student_class': student['class'],
                    'student_number': student['number'],
                    'student_phone': student['phone'],
                    'queue_position': entry['queue_position'],
                    'status': entry['status'],
                    'applied_at': entry['applied_at'],
                    'called_at': entry['called_at'],
                    'completed_at': entry['completed_at']
                })
        
        return jsonify({'ok': True, 'queue': queue})
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'대기열 조회 중 오류: {str(e)}'})

# --- 학생 호출 API ---
@app.route('/api/call-student', methods=['POST'])
def api_call_student():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    entry_id = data.get('entry_id')
    
    if not entry_id:
        return jsonify({'ok': False, 'message': '대기열 ID가 필요합니다.'})
    
    try:
        # 대기열 엔트리 조회
        entry_result = supabase.table('queue_entries').select('''
            *, 
            students!inner(name, phone),
            booths!inner(name, location)
        ''').eq('id', entry_id).execute()
        
        if not entry_result.data:
            return jsonify({'ok': False, 'message': '대기열 엔트리를 찾을 수 없습니다.'})
        
        entry = entry_result.data[0]
        student = entry['students']
        booth = entry['booths']
        
        # 상태를 'called'로 업데이트
        update_result = supabase.table('queue_entries').update({
            'status': 'called',
            'called_at': 'now()'
        }).eq('id', entry_id).execute()
        
        if update_result.data:
            # SMS 알림 발송
            message = f"[{booth['name']}] 참가하실 시간입니다. {booth['location']}로 3분 내 방문해 주세요."
            
            # SOLAPI를 통한 실제 SMS 발송
            sms_success = send_sms_notification(
                phone_number=student['phone'],
                message=message,
                booth_id=entry['booth_id'],
                student_id=entry['student_id']
            )
            
            if sms_success:
                return jsonify({'ok': True, 'message': '학생이 호출되었고 SMS가 발송되었습니다.'})
            else:
                return jsonify({'ok': True, 'message': '학생이 호출되었지만 SMS 발송에 실패했습니다.'})
        else:
            return jsonify({'ok': False, 'message': '호출 상태 업데이트에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'학생 호출 중 오류: {str(e)}'})

# --- 학생 완료 처리 API ---
@app.route('/api/complete-student', methods=['POST'])
def api_complete_student():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    entry_id = data.get('entry_id')
    
    if not entry_id:
        return jsonify({'ok': False, 'message': '대기열 ID가 필요합니다.'})
    
    try:
        # 상태를 'completed'로 업데이트
        result = supabase.table('queue_entries').update({
            'status': 'completed',
            'completed_at': 'now()'
        }).eq('id', entry_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '학생이 완료 처리되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '완료 처리에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'완료 처리 중 오류: {str(e)}'})

# --- 학생 대시보드 ---
@app.route('/student-dashboard')
def student_dashboard():
    return render_template('student_dashboard.html')

# --- 학생용 부스 목록 API ---
@app.route('/api/student-booth-list', methods=['POST'])
def api_student_booth_list():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        # 모든 활성 부스 조회
        booths_result = supabase.table('booths').select('*').eq('is_active', True).order('created_at', desc=True).execute()
        
        booths = []
        if booths_result.data:
            for booth in booths_result.data:
                # 각 부스의 대기열 수 계산
                queue_result = supabase.table('queue_entries').select('id').eq('booth_id', booth['id']).eq('status', 'waiting').execute()
                queue_count = len(queue_result.data) if queue_result.data else 0
                
                booth_data = {
                    'id': booth['id'],
                    'name': booth['name'],
                    'location': booth['location'],
                    'description': booth['description'],
                    'pdf_file_path': booth['pdf_file_path'],
                    'queue_count': queue_count,
                    'created_at': booth['created_at']
                }
                booths.append(booth_data)
        
        return jsonify({'ok': True, 'booths': booths})
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 목록 조회 중 오류: {str(e)}'})

# --- 대기열 신청 API ---
@app.route('/api/apply-to-queue', methods=['POST'])
def api_apply_to_queue():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    booth_id = data.get('booth_id')
    student_id = data.get('student_id')
    
    if not booth_id or not student_id:
        return jsonify({'ok': False, 'message': '부스 ID와 학생 ID가 필요합니다.'})
    
    try:
        # 중복 신청 확인
        existing_queue = supabase.table('queue_entries').select('*').eq('booth_id', booth_id).eq('student_id', student_id).in_('status', ['waiting', 'called']).execute()
        
        if existing_queue.data:
            return jsonify({'ok': False, 'message': '이미 해당 부스에 대기 신청하셨습니다.'})
        
        # 현재 대기열 최대 순번 조회
        max_position_result = supabase.table('queue_entries').select('queue_position').eq('booth_id', booth_id).order('queue_position', desc=True).limit(1).execute()
        
        next_position = 1
        if max_position_result.data:
            next_position = max_position_result.data[0]['queue_position'] + 1
        
        # 대기열 엔트리 생성
        queue_data = {
            'student_id': student_id,
            'booth_id': booth_id,
            'queue_position': next_position,
            'status': 'waiting'
        }
        
        result = supabase.table('queue_entries').insert(queue_data).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '대기 신청이 완료되었습니다.', 'queue_position': next_position})
        else:
            return jsonify({'ok': False, 'message': '대기 신청에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'대기 신청 중 오류: {str(e)}'})

# --- 내 대기신청 목록 API ---
@app.route('/api/my-queue', methods=['POST'])
def api_my_queue():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    student_id = data.get('student_id')
    
    if not student_id:
        return jsonify({'ok': False, 'message': '학생 ID가 필요합니다.'})
    
    try:
        # 학생의 대기열 조회 (부스 정보 포함)
        result = supabase.table('queue_entries').select('''
            *, 
            booths!inner(name, location, description)
        ''').eq('student_id', student_id).order('applied_at', desc=True).execute()
        
        queue = []
        if result.data:
            for entry in result.data:
                booth = entry['booths']
                queue.append({
                    'id': entry['id'],
                    'booth_name': booth['name'],
                    'booth_location': booth['location'],
                    'booth_description': booth['description'],
                    'queue_position': entry['queue_position'],
                    'status': entry['status'],
                    'applied_at': entry['applied_at'],
                    'called_at': entry['called_at'],
                    'completed_at': entry['completed_at']
                })
        
        return jsonify({'ok': True, 'queue': queue})
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'대기신청 목록 조회 중 오류: {str(e)}'})

# --- 대기 취소 API ---
@app.route('/api/cancel-queue', methods=['POST'])
def api_cancel_queue():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    entry_id = data.get('entry_id')
    
    if not entry_id:
        return jsonify({'ok': False, 'message': '대기열 ID가 필요합니다.'})
    
    try:
        # 대기열 엔트리 삭제
        result = supabase.table('queue_entries').delete().eq('id', entry_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '대기 신청이 취소되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '대기 취소에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'대기 취소 중 오류: {str(e)}'})

# --- 부스 체크인 페이지 ---
@app.route('/checkin', methods=['GET', 'POST'])
def checkin():
    booth = request.args.get('booth', '')
    if request.method == 'POST':
        if not SUPABASE_AVAILABLE:
            return jsonify({'result': 'error', 'message': 'Supabase not configured'}), 500
        data = request.get_json()
        # 데이터를 Supabase에 저장
        checkin_data = {
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name'],
            'booth': data['booth'],
            'comment': data['comment']
        }
        result = supabase.table('checkins').insert(checkin_data).execute()
        if result.data:
            return jsonify({'result': 'success'})
        else:
            return jsonify({'result': 'error', 'message': 'Failed to save data'}), 500
    return render_template('checkin.html', booth=booth)

# --- 부스 체크인 페이지 (URL path 형식 지원) ---
@app.route('/checkin/<path:booth_param>')
def checkin_path(booth_param):
    # booth=부스명 형식에서 부스명 추출
    if booth_param.startswith('booth='):
        booth = booth_param[6:]  # 'booth=' 제거
    else:
        booth = booth_param
    return render_template('checkin.html', booth=booth)

# --- 확인증 발급 페이지 ---
@app.route('/certificate')
def certificate():
    return render_template('certificate.html')

# --- 학생 체험 기록 조회 API ---
@app.route('/api/student-records', methods=['POST'])
def api_student_records():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    school = data['school']
    grade = data['grade']
    class_ = data['class']
    number = data['number']
    name = data['name']
    
    # Supabase에서 해당 학생의 모든 활동 내역 조회
    result = supabase.table('checkins').select('id, booth, comment, created_at').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).order('created_at', desc=True).execute()
    
    records = []
    booth_set = set()
    
    if result.data:
        for record in result.data:
            records.append({
                'id': record['id'],
                'booth': record['booth'],
                'comment': record['comment'],
                'created_at': record['created_at']
            })
            booth_set.add(record['booth'])
    
    booth_count = len(booth_set)
    can_get_certificate = booth_count >= 3
    
    # 이미 발급된 확인증이 있는지 확인
    certificate_number = None
    if can_get_certificate:
        existing_cert = supabase.table('certificates').select('certificate_number').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).execute()
        if existing_cert.data:
            certificate_number = existing_cert.data[0]['certificate_number']
    
    return jsonify({
        'ok': True,
        'records': records,
        'booth_count': booth_count,
        'can_get_certificate': can_get_certificate,
        'certificate_number': certificate_number
    })

# --- 확인증 발급 API (학생별 활동 내역 조회) ---
@app.route('/api/certificate', methods=['POST'])
def api_certificate():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    data = request.get_json()
    school = data['school']
    grade = data['grade']
    class_ = data['class']
    number = data['number']
    name = data['name']
    
    # Supabase에서 해당 학생의 활동 내역 조회 (부스별 최신 소감 포함)
    result = supabase.table('checkins').select('booth, comment, created_at').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).order('created_at', desc=True).execute()
    
    booth_records = {}
    if result.data:
        for record in result.data:
            booth_name = record['booth']
            # 부스별로 가장 최신 기록만 저장
            if booth_name not in booth_records:
                booth_records[booth_name] = {
                    'comment': record['comment'],
                    'created_at': record['created_at']
                }
    
    booth_count = len(booth_records)
    if booth_count >= 3:
        # 이미 발급된 인증서가 있는지 확인
        existing_cert = supabase.table('certificates').select('certificate_number').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).execute()
        
        if existing_cert.data:
            # 기존 인증서 있음
            cert_id = existing_cert.data[0]['certificate_number']
        else:
            # 새 인증서 발급
            cert_id = generate_certificate_number()
            booth_names = list(booth_records.keys())
            
            # 인증서 테이블에 저장
            supabase.table('certificates').insert({
                'certificate_number': cert_id,
                'school': school,
                'grade': int(grade),
                'class': int(class_),
                'number': int(number),
                'name': name,
                'booth_names': booth_names,
                'booth_count': booth_count
            }).execute()
        
        return jsonify({
            'ok': True, 
            'booth_count': booth_count, 
            'cert_id': cert_id,
            'booth_records': booth_records,
            'event_name': get_event_name()  # 행사명 추가
        })
    else:
        return jsonify({'ok': False, 'booth_count': booth_count, 'booth_records': booth_records})

# --- PDF 확인증 생성 API ---
@app.route('/api/generate-certificate-pdf', methods=['POST'])
def api_generate_certificate_pdf():
    if not SUPABASE_AVAILABLE:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    data = request.get_json()
    school = data['school']
    grade = data['grade']
    class_ = data['class']
    number = data['number']
    name = data['name']
    
    try:
        # 학생의 활동 내역 조회 (부스별 최신 소감 포함)
        result = supabase.table('checkins').select('booth, comment, created_at').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).order('created_at', desc=True).execute()
        
        booth_records = {}
        if result.data:
            for record in result.data:
                booth_name = record['booth']
                # 부스별로 가장 최신 기록만 저장
                if booth_name not in booth_records:
                    booth_records[booth_name] = {
                        'comment': record['comment'],
                        'created_at': record['created_at']
                    }
        
        booth_count = len(booth_records)
        if booth_count < 3:
            return jsonify({'error': f'체험 부스가 부족합니다. (현재 {booth_count}개, 최소 3개 필요)'}), 400
        
        # 이미 발급된 인증서 확인
        existing_cert = supabase.table('certificates').select('certificate_number').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).execute()
        
        if existing_cert.data:
            cert_id = existing_cert.data[0]['certificate_number']
        else:
            # 새 인증서 발급
            cert_id = generate_certificate_number()
            booth_names = list(booth_records.keys())
            
            # 인증서 테이블에 저장
            supabase.table('certificates').insert({
                'certificate_number': cert_id,
                'school': school,
                'grade': int(grade),
                'class': int(class_),
                'number': int(number),
                'name': name,
                'booth_names': booth_names,
                'booth_count': booth_count
            }).execute()
        
        # 현재 행사명 가져오기
        event_name = get_event_name()
        
        # PDF 생성
        pdf_buffer = generate_certificate_pdf(data, booth_records, cert_id, event_name)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{name}_활동확인서.pdf'
        )
        
    except Exception as e:
        print(f"PDF 생성 중 오류: {str(e)}")
        return jsonify({'error': f'PDF 생성 중 오류: {str(e)}'}), 500

# --- 소감 수정 API ---
@app.route('/api/update-comment', methods=['POST'])
def api_update_comment():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    record_id = data['record_id']
    new_comment = data['comment']
    
    try:
        # 체크인 기록의 소감 업데이트
        result = supabase.table('checkins').update({
            'comment': new_comment
        }).eq('id', record_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '소감이 수정되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '기록을 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'수정 중 오류: {str(e)}'})

# --- 체크인 기록 삭제 API ---
@app.route('/api/delete-record', methods=['POST'])
def api_delete_record():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    record_id = data['record_id']
    
    try:
        # 체크인 기록 삭제
        result = supabase.table('checkins').delete().eq('id', record_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '기록이 삭제되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '기록을 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'삭제 중 오류: {str(e)}'})

# --- 새 체크인 기록 추가 API ---
@app.route('/api/add-record', methods=['POST'])
def api_add_record():
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # 새 체크인 기록 추가
        checkin_data = {
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name'],
            'booth': data['booth'],
            'comment': data['comment']
        }
        
        result = supabase.table('checkins').insert(checkin_data).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '새 기록이 추가되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '기록 추가에 실패했습니다.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'추가 중 오류: {str(e)}'})

# --- 관리자 페이지 (비밀번호: admin) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        pw = request.form.get('pw', '')
        if pw == 'admin':
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            flash('비밀번호가 틀렸습니다.', 'danger')
    return render_template('admin.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/qr-generator')
def qr_generator():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    return render_template('qr_generator.html')

@app.route('/admin/generate-qr', methods=['POST'])
def generate_qr():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    booth_name = request.form.get('booth_name')
    booth_description = request.form.get('booth_description', '')
    
    if not booth_name:
        return jsonify({'error': '부스명을 입력해주세요'}), 400
    
    if not SUPABASE_AVAILABLE:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        # 부스 데이터를 Supabase에 저장 (중복 시 업데이트)
        result = supabase.table('booths').select('id').eq('name', booth_name).execute()
        
        if result.data:
            # 기존 부스 업데이트
            supabase.table('booths').update({
                'description': booth_description,
                'is_active': True,
                'updated_at': 'now()'
            }).eq('name', booth_name).execute()
        else:
            # 새 부스 생성
            supabase.table('booths').insert({
                'name': booth_name,
                'description': booth_description,
                'is_active': True
            }).execute()
        
        # QR코드 URL 생성
        base_url = os.environ.get('BASE_URL', 'https://dgmathft.up.railway.app')
        qr_url = f"{base_url}/checkin?booth={booth_name}"
        
        # QR코드 생성
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # QR코드 이미지 생성
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # 부스명이 포함된 최종 이미지 생성
        final_img = create_qr_with_text(qr_img, booth_name)
        
        # 이미지를 바이트로 변환
        img_byte_arr = BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # QR 코드를 파일로도 저장 (부스 관리에서 재사용)
        save_qr_code_file(booth_name, final_img)
        
        return send_file(img_byte_arr, mimetype='image/png', download_name=f'qr_{booth_name}.png')
        
    except Exception as e:
        return jsonify({'error': f'부스 생성 중 오류: {str(e)}'}), 500

@app.route('/admin/booths')
def admin_booths():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    # 모든 부스 조회
    result = supabase.table('booths').select('*').order('created_at', desc=True).execute()
    booths = result.data if result.data else []
    
    return render_template('admin_booths.html', booths=booths)

@app.route('/admin/edit-booth/<int:booth_id>')
def admin_edit_booth(booth_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # 부스 정보 조회
        booth_result = supabase.table('booths').select('*').eq('id', booth_id).single().execute()
        booth = booth_result.data
        
        if not booth:
            flash('해당 부스를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_booths'))
        
        # 운영자 목록 조회
        operators_result = supabase.table('booth_operators').select('*').order('club_name').execute()
        operators = operators_result.data if operators_result.data else []
        
        return render_template('admin_edit_booth.html', booth=booth, operators=operators)
    except Exception as e:
        flash(f'부스 정보 로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin_booths'))

@app.route('/admin/api/update-booth', methods=['POST'])
def admin_api_update_booth():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        data = request.form
        booth_id = data.get('id')
        name = data.get('name')
        description = data.get('description')
        location = data.get('location')
        operator_id = data.get('operator_id')
        is_active = 'is_active' in data

        if not booth_id or not name or not location or not operator_id:
            return jsonify({'ok': False, 'message': '필수 정보가 누락되었습니다.'})
        
        # 부스명 중복 확인 (현재 부스 제외)
        existing_booth = supabase.table('booths').select('*').eq('name', name).neq('id', booth_id).execute()
        if existing_booth.data:
            return jsonify({'ok': False, 'message': f'부스명 "{name}"이 이미 사용중입니다.'})

        # 부스 정보 업데이트
        update_data = {
            'name': name,
            'description': description,
            'location': location,
            'operator_id': int(operator_id),
            'is_active': is_active
        }
        
        # PDF 파일 처리
        if 'pdf_file' in request.files:
            pdf_file = request.files['pdf_file']
            if pdf_file and pdf_file.filename:
                # 기존 PDF 파일 삭제
                booth_result = supabase.table('booths').select('pdf_file_path').eq('id', booth_id).single().execute()
                if booth_result.data and booth_result.data.get('pdf_file_path'):
                    old_pdf_path = booth_result.data['pdf_file_path']
                    if os.path.exists(old_pdf_path):
                        os.remove(old_pdf_path)
                
                # 새 PDF 파일 저장
                filename = secure_filename(pdf_file.filename)
                pdf_filename = f"booth_{booth_id}_{filename}"
                pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
                pdf_file.save(pdf_path)
                update_data['pdf_file_path'] = pdf_path

        result = supabase.table('booths').update(update_data).eq('id', booth_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '부스 정보가 성공적으로 업데이트되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '부스 업데이트에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 업데이트 중 오류: {str(e)}'})

@app.route('/admin/student-records')
def admin_student_records():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    # 모든 학생 목록 조회 (중복 제거)
    result = supabase.table('checkins').select('school, grade, class, number, name').execute()
    students = []
    student_set = set()
    
    if result.data:
        for record in result.data:
            student_key = f"{record['school']}-{record['grade']}-{record['class']}-{record['number']}-{record['name']}"
            if student_key not in student_set:
                students.append(record)
                student_set.add(student_key)
    
    return render_template('admin_student_records.html', students=students)

@app.route('/admin/booth-operators')
def admin_booth_operators():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    # 모든 부스 운영자 조회
    result = supabase.table('booth_operators').select('*').order('created_at', desc=True).execute()
    operators = result.data if result.data else []
    
    return render_template('admin_booth_operators.html', operators=operators)

@app.route('/admin/queue-status')
def admin_queue_status():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    return render_template('admin_queue_status.html')

@app.route('/admin/api/queue-status')
def admin_api_queue_status():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        # 전체 통계 계산
        booths_result = supabase.table('booths').select('id').execute()
        total_booths = len(booths_result.data) if booths_result.data else 0
        
        waiting_result = supabase.table('queue_entries').select('id').eq('status', 'waiting').execute()
        total_waiting = len(waiting_result.data) if waiting_result.data else 0
        
        called_result = supabase.table('queue_entries').select('id').eq('status', 'called').execute()
        total_called = len(called_result.data) if called_result.data else 0
        
        completed_result = supabase.table('queue_entries').select('id').eq('status', 'completed').execute()
        total_completed = len(completed_result.data) if completed_result.data else 0
        
        operators_result = supabase.table('booth_operators').select('id').execute()
        total_operators = len(operators_result.data) if operators_result.data else 0
        
        stats = {
            'total_booths': total_booths,
            'total_waiting': total_waiting,
            'total_called': total_called,
            'total_completed': total_completed,
            'total_operators': total_operators
        }
        
        # 부스별 대기현황
        booths_detail = supabase.table('booths').select('''
            *, 
            booth_operators(club_name)
        ''').execute()
        
        booths = []
        if booths_detail.data:
            for booth in booths_detail.data:
                # 각 부스별 대기 상태 계산
                waiting_count = supabase.table('queue_entries').select('id').eq('booth_id', booth['id']).eq('status', 'waiting').execute()
                called_count = supabase.table('queue_entries').select('id').eq('booth_id', booth['id']).eq('status', 'called').execute()
                completed_count = supabase.table('queue_entries').select('id').eq('booth_id', booth['id']).eq('status', 'completed').execute()
                
                booth_info = {
                    'id': booth['id'],
                    'name': booth['name'],
                    'location': booth['location'],
                    'operator_name': booth['booth_operators']['club_name'] if booth['booth_operators'] else None,
                    'waiting_count': len(waiting_count.data) if waiting_count.data else 0,
                    'called_count': len(called_count.data) if called_count.data else 0,
                    'completed_count': len(completed_count.data) if completed_count.data else 0
                }
                booths.append(booth_info)
        
        # 최근 알림 조회
        notifications_result = supabase.table('notifications').select('''
            *, 
            students(name),
            booths(name)
        ''').order('created_at', desc=True).limit(50).execute()
        
        notifications = []
        if notifications_result.data:
            for notification in notifications_result.data:
                notifications.append({
                    'student_name': notification['students']['name'],
                    'booth_name': notification['booths']['name'],
                    'message': notification['message'],
                    'status': notification['status'],
                    'created_at': notification['created_at']
                })
        
        return jsonify({
            'ok': True,
            'stats': stats,
            'booths': booths,
            'notifications': notifications
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'데이터 조회 중 오류: {str(e)}'})

@app.route('/admin/add-booth-operator-account', methods=['POST'])
def add_booth_operator_account():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booth_operators'))
    
    try:
        data = request.form
        
        # 중복 확인
        existing = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).execute()
        if existing.data:
            flash(f'ID "{data["operator_id"]}"가 이미 존재합니다.', 'danger')
            return redirect(url_for('admin_booth_operators'))
        
        # 새 부스 운영자 계정 생성
        operator_data = {
            'operator_id': data['operator_id'],
            'password': data['password'],
            'school': data['school'],
            'club_name': data['club_name'],
            'booth_topic': data['booth_topic'],
            'name': data['name'],
            'phone': data['phone'],
            'email': data['email'],
            'is_active': True
        }
        
        result = supabase.table('booth_operators').insert(operator_data).execute()
        
        if result.data:
            flash(f'부스 운영자 계정 "{data["operator_id"]}"이 성공적으로 생성되었습니다.', 'success')
        else:
            flash('계정 생성에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 생성 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booth_operators'))

@app.route('/admin/edit-booth-operator-account/<int:operator_id>', methods=['POST'])
def edit_booth_operator_account(operator_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booth_operators'))
    
    try:
        data = request.form
        
        # 다른 운영자가 같은 operator_id를 사용하는지 확인
        existing = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).neq('id', operator_id).execute()
        if existing.data:
            flash(f'ID "{data["operator_id"]}"가 다른 운영자에 의해 사용 중입니다.', 'danger')
            return redirect(url_for('admin_booth_operators'))
        
        # 운영자 계정 수정
        update_data = {
            'operator_id': data['operator_id'],
            'school': data['school'],
            'club_name': data['club_name'],
            'booth_topic': data['booth_topic'],
            'phone': data['phone'],
            'email': data['email'],
            'is_active': 'is_active' in data
        }
        
        # 비밀번호가 입력된 경우에만 업데이트
        if data.get('password'):
            update_data['password'] = data['password']
        
        result = supabase.table('booth_operators').update(update_data).eq('id', operator_id).execute()
        
        if result.data:
            flash(f'부스 운영자 계정이 성공적으로 수정되었습니다.', 'success')
        else:
            flash('계정 수정에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 수정 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booth_operators'))

@app.route('/admin/delete-booth-operator-account/<int:operator_id>', methods=['POST'])
def delete_booth_operator_account(operator_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booth_operators'))
    
    try:
        # 운영자 정보 조회
        operator = supabase.table('booth_operators').select('*').eq('id', operator_id).execute()
        if not operator.data:
            flash('운영자를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_booth_operators'))
        
        operator_name = operator.data[0]['operator_id']
        
        # 운영자 계정 삭제
        result = supabase.table('booth_operators').delete().eq('id', operator_id).execute()
        
        if result.data:
            flash(f'부스 운영자 계정 "{operator_name}"이 삭제되었습니다.', 'success')
        else:
            flash('계정 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booth_operators'))

@app.route('/admin/toggle-booth-operator-status/<int:operator_id>', methods=['POST'])
def toggle_booth_operator_status(operator_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booth_operators'))
    
    try:
        # 현재 상태 조회
        operator = supabase.table('booth_operators').select('*').eq('id', operator_id).execute()
        if not operator.data:
            flash('운영자를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_booth_operators'))
        
        current_status = operator.data[0]['is_active']
        new_status = not current_status
        
        # 상태 변경
        result = supabase.table('booth_operators').update({
            'is_active': new_status
        }).eq('id', operator_id).execute()
        
        if result.data:
            status_text = '활성화' if new_status else '비활성화'
            flash(f'운영자 상태가 {status_text}되었습니다.', 'success')
        else:
            flash('상태 변경에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'상태 변경 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booth_operators'))

@app.route('/admin/clear-all-booth-operators', methods=['POST'])
def clear_all_booth_operators():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booth_operators'))
    
    try:
        # 모든 부스 운영자 삭제
        result = supabase.table('booth_operators').delete().neq('id', 0).execute()
        
        flash('모든 부스 운영자가 삭제되었습니다.', 'success')
        
    except Exception as e:
        flash(f'부스 운영자 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booth_operators'))

@app.route('/admin/student-accounts')
def admin_student_accounts():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    # 모든 학생 계정 조회
    result = supabase.table('students').select('*').order('created_at', desc=True).execute()
    students = result.data if result.data else []
    
    return render_template('admin_student_accounts.html', students=students)

@app.route('/admin/certificates')
def admin_certificates():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    # 현재 행사명 가져오기
    current_event_name = get_event_name()
    
    # 발급된 확인증 목록 조회
    certificates_result = supabase.table('certificates').select('*').order('issued_at', desc=True).execute()
    certificates = certificates_result.data if certificates_result.data else []
    
    # 확인증 발급 대상 학생 조회 (3개 이상 부스 체험)
    checkins_result = supabase.table('checkins').select('school, grade, class, number, name, booth').execute()
    
    # 학생별 부스 체험 수 계산
    student_booth_count = {}
    total_participants = set()
    
    if checkins_result.data:
        for record in checkins_result.data:
            student_key = f"{record['school']}-{record['grade']}-{record['class']}-{record['number']}-{record['name']}"
            total_participants.add(student_key)
            
            if student_key not in student_booth_count:
                student_booth_count[student_key] = {
                    'school': record['school'],
                    'grade': record['grade'],
                    'class': record['class'],
                    'number': record['number'],
                    'name': record['name'],
                    'booths': set()
                }
            student_booth_count[student_key]['booths'].add(record['booth'])
    
    # 3개 이상 부스 체험한 학생 필터링
    eligible_students = []
    for student_key, student_data in student_booth_count.items():
        booth_count = len(student_data['booths'])
        if booth_count >= 3:
            # 이미 발급된 확인증이 있는지 확인
            existing_cert = next((cert for cert in certificates if 
                cert['school'] == student_data['school'] and
                cert['grade'] == student_data['grade'] and
                cert['class'] == student_data['class'] and
                cert['number'] == student_data['number'] and
                cert['name'] == student_data['name']), None)
            
            eligible_students.append({
                'school': student_data['school'],
                'grade': student_data['grade'],
                'class': student_data['class'],
                'number': student_data['number'],
                'name': student_data['name'],
                'booth_count': booth_count,
                'certificate_number': existing_cert['certificate_number'] if existing_cert else None
            })
    
    # 정렬 (미발급 -> 발급완료 순)
    eligible_students.sort(key=lambda x: (x['certificate_number'] is not None, x['name']))
    
    return render_template('admin_certificates.html', 
                         certificates=certificates,
                         eligible_students=eligible_students,
                         eligible_count=len(eligible_students),
                         total_participants=len(total_participants),
                         current_event_name=current_event_name)

@app.route('/admin/add-student-account', methods=['POST'])
def add_student_account():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_student_accounts'))
    
    try:
        data = request.form
        
        # 중복 확인
        existing = supabase.table('students').select('*').eq('student_id', data['student_id']).execute()
        if existing.data:
            flash(f'ID "{data["student_id"]}"가 이미 존재합니다.', 'danger')
            return redirect(url_for('admin_student_accounts'))
        
        # 학교-학년-반-번호 중복 확인
        existing_student = supabase.table('students').select('*').eq('school', data['school']).eq('grade', int(data['grade'])).eq('class', int(data['class'])).eq('number', int(data['number'])).execute()
        if existing_student.data:
            flash(f'{data["school"]} {data["grade"]}학년 {data["class"]}반 {data["number"]}번 학생이 이미 존재합니다.', 'danger')
            return redirect(url_for('admin_student_accounts'))
        
        # 새 학생 계정 생성
        student_data = {
            'student_id': data['student_id'],
            'password': data['password'],
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name']
        }
        
        result = supabase.table('students').insert(student_data).execute()
        
        if result.data:
            flash(f'학생 계정 "{data["name"]}"이 성공적으로 생성되었습니다.', 'success')
        else:
            flash('계정 생성에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 생성 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_student_accounts'))

@app.route('/admin/issue-certificate', methods=['POST'])
def admin_issue_certificate():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    school = data['school']
    grade = data['grade']
    class_ = data['class']
    number = data['number']
    name = data['name']
    
    try:
        # 학생의 체험 기록 확인
        result = supabase.table('checkins').select('booth, comment, created_at').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).order('created_at', desc=True).execute()
        
        booth_records = {}
        if result.data:
            for record in result.data:
                booth_name = record['booth']
                # 부스별로 가장 최신 기록만 저장
                if booth_name not in booth_records:
                    booth_records[booth_name] = {
                        'comment': record['comment'],
                        'created_at': record['created_at']
                    }
        
        booth_count = len(booth_records)
        if booth_count < 3:
            return jsonify({'ok': False, 'message': f'체험 부스가 부족합니다. (현재 {booth_count}개, 최소 3개 필요)'})
        
        # 이미 발급된 인증서가 있는지 확인
        existing_cert = supabase.table('certificates').select('certificate_number').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).execute()
        
        if existing_cert.data:
            return jsonify({'ok': False, 'message': '이미 확인증이 발급되었습니다.', 'certificate_number': existing_cert.data[0]['certificate_number']})
        
        # 새 인증서 발급
        cert_id = generate_certificate_number()
        booth_names = list(booth_records.keys())
        
        # 인증서 테이블에 저장
        supabase.table('certificates').insert({
            'certificate_number': cert_id,
            'school': school,
            'grade': int(grade),
            'class': int(class_),
            'number': int(number),
            'name': name,
            'booth_names': booth_names,
            'booth_count': booth_count
        }).execute()
        
        return jsonify({
            'ok': True, 
            'certificate_number': cert_id,
            'booth_count': booth_count
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'확인증 발급 중 오류: {str(e)}'})

@app.route('/admin/update-event-name', methods=['POST'])
def admin_update_event_name():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    event_name = data.get('event_name', '').strip()
    
    if not event_name:
        return jsonify({'ok': False, 'message': '행사명을 입력해주세요.'})
    
    try:
        # settings 테이블 존재 여부 확인
        test_query = supabase.table('settings').select('id').limit(1).execute()
    except Exception as e:
        if 'relation "public.settings" does not exist' in str(e):
            return jsonify({'ok': False, 'message': 'settings 테이블이 존재하지 않습니다. 관리자에게 문의하세요.'})
    
    if set_event_name(event_name):
        return jsonify({'ok': True, 'message': '행사명이 업데이트되었습니다.'})
    else:
        return jsonify({'ok': False, 'message': '행사명 업데이트에 실패했습니다. 서버 로그를 확인하세요.'})

@app.route('/admin/upload-seal', methods=['POST'])
def admin_upload_seal():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    if 'seal_image' not in request.files:
        return jsonify({'ok': False, 'message': '이미지 파일이 필요합니다.'})
    
    file = request.files['seal_image']
    if file.filename == '':
        return jsonify({'ok': False, 'message': '파일이 선택되지 않았습니다.'})
    
    if file and file.filename:
        try:
            # static 디렉토리가 없으면 생성
            static_dir = 'static'
            if not os.path.exists(static_dir):
                os.makedirs(static_dir)
            
            # 기존 관인 파일 삭제
            seal_path = 'static/seal.png'
            if os.path.exists(seal_path):
                os.remove(seal_path)
            
            # 새 관인 파일 저장 (항상 seal.png로 저장)
            file.save(seal_path)
            
            return jsonify({
                'ok': True, 
                'message': '커스텀 관인 이미지가 업로드되었습니다. 기본 관인 대신 사용됩니다.',
                'seal_url': '/static/seal.png',
                'seal_type': 'custom'
            })
            
        except Exception as e:
            return jsonify({'ok': False, 'message': f'파일 업로드 중 오류: {str(e)}'})
    
    return jsonify({'ok': False, 'message': '올바르지 않은 파일입니다.'})

@app.route('/admin/get-current-seal')
def admin_get_current_seal():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    custom_seal_path = 'static/seal.png'
    default_seal_path = 'image/GanIn.png'
    
    # 1순위: 커스텀 관인
    if os.path.exists(custom_seal_path):
        return jsonify({
            'ok': True, 
            'seal_url': '/static/seal.png',
            'is_custom': True,
            'seal_type': 'custom'
        })
    # 2순위: 기본 관인
    elif os.path.exists(default_seal_path):
        return jsonify({
            'ok': True, 
            'seal_url': '/image/GanIn.png',
            'is_custom': False,
            'seal_type': 'default'
        })
    else:
        return jsonify({
            'ok': True, 
            'seal_url': None,
            'is_custom': False,
            'seal_type': 'none'
        })

@app.route('/admin/reset-seal', methods=['POST'])
def admin_reset_seal():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    try:
        # 커스텀 관인 파일 삭제
        custom_seal_path = 'static/seal.png'
        if os.path.exists(custom_seal_path):
            os.remove(custom_seal_path)
        
        # 기본 관인 확인
        default_seal_path = 'image/GanIn.png'
        if os.path.exists(default_seal_path):
            return jsonify({
                'ok': True, 
                'message': '커스텀 관인이 삭제되었습니다. 기본 관인을 사용합니다.',
                'seal_url': '/image/GanIn.png',
                'seal_type': 'default'
            })
        else:
            return jsonify({
                'ok': True, 
                'message': '커스텀 관인이 삭제되었지만 기본 관인을 찾을 수 없습니다.',
                'seal_url': None,
                'seal_type': 'none'
            })
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'관인 리셋 중 오류: {str(e)}'})

@app.route('/admin/edit-student-account/<int:student_id>', methods=['POST'])
def edit_student_account(student_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_student_accounts'))
    
    try:
        data = request.form
        
        # 다른 학생이 같은 student_id를 사용하는지 확인
        existing = supabase.table('students').select('*').eq('student_id', data['student_id']).neq('id', student_id).execute()
        if existing.data:
            flash(f'ID "{data["student_id"]}"가 다른 학생에 의해 사용 중입니다.', 'danger')
            return redirect(url_for('admin_student_accounts'))
        
        # 학생 계정 수정
        update_data = {
            'student_id': data['student_id'],
            'password': data['password'],
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name']
        }
        
        result = supabase.table('students').update(update_data).eq('id', student_id).execute()
        
        if result.data:
            flash(f'학생 계정이 성공적으로 수정되었습니다.', 'success')
        else:
            flash('계정 수정에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 수정 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_student_accounts'))

@app.route('/admin/delete-student-account/<int:student_id>', methods=['POST'])
def delete_student_account(student_id):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_student_accounts'))
    
    try:
        # 학생 정보 조회
        student = supabase.table('students').select('*').eq('id', student_id).execute()
        if not student.data:
            flash('학생을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_student_accounts'))
        
        student_name = student.data[0]['name']
        
        # 학생 계정 삭제
        result = supabase.table('students').delete().eq('id', student_id).execute()
        
        if result.data:
            flash(f'학생 계정 "{student_name}"이 삭제되었습니다.', 'success')
        else:
            flash('계정 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_student_accounts'))

@app.route('/admin/download-qr/<booth_name>')
def download_qr_code(booth_name):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    try:
        # 부스 정보 조회
        result = supabase.table('booths').select('qr_file_path').eq('name', booth_name).execute()
        
        if result.data and result.data[0]['qr_file_path']:
            qr_file_path = result.data[0]['qr_file_path']
            
            # 파일이 존재하는지 확인
            if os.path.exists(qr_file_path):
                return send_file(qr_file_path, as_attachment=True, download_name=f'qr_{booth_name}.png')
            else:
                # 파일이 없으면 새로 생성
                return regenerate_qr_code(booth_name)
        else:
            # QR 코드가 없으면 새로 생성
            return regenerate_qr_code(booth_name)
            
    except Exception as e:
        flash(f'QR 코드 다운로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin_booths'))

@app.route('/admin/delete-booth/<booth_name>', methods=['POST'])
def delete_booth(booth_name):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booths'))
    
    try:
        # 부스와 관련된 체크인 기록도 함께 삭제
        result = supabase.table('booths').delete().eq('name', booth_name).execute()
        
        if result.data:
            # QR 코드 파일도 삭제
            qr_file_path = f"static/qr_codes/qr_{booth_name}.png"
            if os.path.exists(qr_file_path):
                os.remove(qr_file_path)
            
            flash(f'부스 "{booth_name}"이(가) 삭제되었습니다.', 'success')
        else:
            flash(f'부스 "{booth_name}" 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'부스 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booths'))

@app.route('/admin/clear-all-booths', methods=['POST'])
def clear_all_booths():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin_booths'))
    
    try:
        # 모든 부스 삭제
        result = supabase.table('booths').delete().neq('id', 0).execute()
        
        # QR 코드 파일들도 삭제
        import shutil
        qr_dir = 'static/qr_codes'
        if os.path.exists(qr_dir):
            shutil.rmtree(qr_dir)
            os.makedirs(qr_dir)
        
        flash('모든 부스가 초기화되었습니다.', 'success')
        
    except Exception as e:
        flash(f'부스 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin_booths'))

@app.route('/admin/clear-all-data', methods=['POST'])
def clear_all_data():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # 모든 테이블의 데이터 삭제
        # 1. 체크인 기록 삭제
        supabase.table('checkins').delete().neq('id', 0).execute()
        
        # 2. 인증서 삭제
        supabase.table('certificates').delete().neq('id', 0).execute()
        
        # 3. 부스 삭제
        supabase.table('booths').delete().neq('id', 0).execute()
        
        # 4. 학생 계정 삭제
        supabase.table('students').delete().neq('id', 0).execute()
        
        # 5. QR 코드 파일들 삭제
        import shutil
        qr_dir = 'static/qr_codes'
        if os.path.exists(qr_dir):
            shutil.rmtree(qr_dir)
            os.makedirs(qr_dir)
        
        flash('모든 데이터가 초기화되었습니다.', 'success')
        
    except Exception as e:
        flash(f'데이터 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/init-database', methods=['POST'])
def init_database_tables():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # students 테이블 생성
        create_students_sql = """
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            student_id VARCHAR(20) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            school VARCHAR(100) NOT NULL,
            grade INTEGER NOT NULL,
            class INTEGER NOT NULL,
            number INTEGER NOT NULL,
            name VARCHAR(50) NOT NULL,
            phone VARCHAR(20),
            email VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        # certificates 테이블 생성
        create_certificates_sql = """
        CREATE TABLE IF NOT EXISTS certificates (
            id SERIAL PRIMARY KEY,
            certificate_number VARCHAR(20) UNIQUE NOT NULL,
            school VARCHAR(100) NOT NULL,
            grade INTEGER NOT NULL,
            class INTEGER NOT NULL,
            number INTEGER NOT NULL,
            name VARCHAR(50) NOT NULL,
            booth_names TEXT[],
            booth_count INTEGER NOT NULL,
            issued_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        # booths 테이블 생성
        create_booths_sql = """
        CREATE TABLE IF NOT EXISTS booths (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            location VARCHAR(200),
            detailed_description TEXT,
            pdf_file_path VARCHAR(500),
            operator_id INTEGER,
            is_active BOOLEAN DEFAULT true,
            qr_file_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        # booth_operators 테이블 생성
        create_booth_operators_sql = """
        CREATE TABLE IF NOT EXISTS booth_operators (
            id SERIAL PRIMARY KEY,
            operator_id VARCHAR(20) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            school VARCHAR(100) NOT NULL,
            club_name VARCHAR(100) NOT NULL,
            name VARCHAR(100) NOT NULL,
            booth_topic VARCHAR(200) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            email VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        # queue_entries 테이블 생성
        create_queue_entries_sql = """
        CREATE TABLE IF NOT EXISTS queue_entries (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            booth_id INTEGER NOT NULL,
            queue_position INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'waiting',
            applied_at TIMESTAMP DEFAULT NOW(),
            called_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
        );
        """
        
        # notifications 테이블 생성
        create_notifications_sql = """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            booth_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            phone VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
        );
        """
        
        # files 테이블 생성
        create_files_sql = """
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            booth_id INTEGER NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            uploaded_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (booth_id) REFERENCES booths(id) ON DELETE CASCADE
        );
        """
        
        # 인덱스 생성
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id);
        CREATE INDEX IF NOT EXISTS idx_students_school_grade_class_number ON students(school, grade, class, number);
        CREATE INDEX IF NOT EXISTS idx_certificates_number ON certificates(certificate_number);
        CREATE INDEX IF NOT EXISTS idx_certificates_student ON certificates(school, grade, class, number, name);
        CREATE INDEX IF NOT EXISTS idx_booths_name ON booths(name);
        CREATE INDEX IF NOT EXISTS idx_booth_operators_operator_id ON booth_operators(operator_id);
        CREATE INDEX IF NOT EXISTS idx_queue_entries_student_booth ON queue_entries(student_id, booth_id);
        CREATE INDEX IF NOT EXISTS idx_queue_entries_booth_status ON queue_entries(booth_id, status);
        CREATE INDEX IF NOT EXISTS idx_notifications_student_booth ON notifications(student_id, booth_id);
        CREATE INDEX IF NOT EXISTS idx_files_booth_id ON files(booth_id);
        """
        
        # 직접 execute를 시도 (일부 Supabase 클라이언트는 raw SQL 지원)
        # 이 방법이 작동하지 않으면 Supabase 대시보드에서 수동으로 실행해야 함
        try:
            from supabase.client import Client
            # 임시로 핵심 테이블들 접근 시도해서 존재 여부 확인
            result = supabase.table('students').select('id').limit(1).execute()
            result = supabase.table('certificates').select('id').limit(1).execute()
            result = supabase.table('booths').select('id').limit(1).execute()
            result = supabase.table('booth_operators').select('id').limit(1).execute()
            result = supabase.table('queue_entries').select('id').limit(1).execute()
            result = supabase.table('notifications').select('id').limit(1).execute()
            result = supabase.table('files').select('id').limit(1).execute()
            result = supabase.table('settings').select('id').limit(1).execute()
            flash('모든 필요한 테이블이 이미 존재합니다.', 'info')
        except:
            # 테이블이 없으면 생성 안내
            flash('수동으로 Supabase에서 테이블을 생성해야 합니다. 콘솔 로그를 확인하세요.', 'warning')
            print("=" * 60)
            print("다음 SQL들을 Supabase SQL Editor에서 실행하세요:")
            print("=" * 60)
            print("-- 1. Students Table")
            print(create_students_sql)
            print("\n-- 2. Certificates Table")
            print(create_certificates_sql)
            print("\n-- 3. Booths Table")
            print(create_booths_sql)
            print("\n-- 4. Booth Operators Table")
            print(create_booth_operators_sql)
            print("\n-- 5. Queue Entries Table")
            print(create_queue_entries_sql)
            print("\n-- 6. Notifications Table")
            print(create_notifications_sql)
            print("\n-- 7. Files Table")
            print(create_files_sql)
            print("\n-- 8. Settings Table")
            print("""
CREATE TABLE IF NOT EXISTS settings (
  id SERIAL PRIMARY KEY,
  key VARCHAR(100) UNIQUE NOT NULL,
  value TEXT,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default event name
INSERT INTO settings (key, value, description) VALUES 
('event_name', '대구수학축제', '행사명') 
ON CONFLICT (key) DO NOTHING;
            """)
            print("\n-- 9. Indexes")
            print(create_indexes_sql)
            print("=" * 60)
        
    except Exception as e:
        flash(f'데이터베이스 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin'))

def regenerate_qr_code(booth_name):
    """QR 코드 재생성"""
    try:
        # QR코드 URL 생성
        base_url = os.environ.get('BASE_URL', 'https://dgmathft.up.railway.app')
        qr_url = f"{base_url}/checkin?booth={booth_name}"
        
        # QR코드 생성
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # QR코드 이미지 생성
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # 부스명이 포함된 최종 이미지 생성
        final_img = create_qr_with_text(qr_img, booth_name)
        
        # QR 코드를 파일로 저장
        save_qr_code_file(booth_name, final_img)
        
        # 이미지를 바이트로 변환하여 다운로드
        img_byte_arr = BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return send_file(img_byte_arr, mimetype='image/png', as_attachment=True, download_name=f'qr_{booth_name}.png')
        
    except Exception as e:
        flash(f'QR 코드 재생성 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin_booths'))

@app.route('/admin/download')
def admin_download():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured. Cannot download data.', 'danger')
        return redirect(url_for('admin'))
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        # 1. 체크인 기록 (checkins 테이블)
        checkins_result = supabase.table('checkins').select('*').order('created_at', desc=True).execute()
        if checkins_result.data:
            checkins_records = []
            for record in checkins_result.data:
                checkins_records.append({
                    'ID': record['id'],
                    '학교명': record['school'],
                    '학년': record['grade'],
                    '반': record['class'],
                    '번호': record['number'],
                    '이름': record['name'],
                    '부스명': record['booth'],
                    '소감': record['comment'],
                    '체크인시각': record['created_at']
                })
            df_checkins = pd.DataFrame(checkins_records)
        else:
            df_checkins = pd.DataFrame()
        df_checkins.to_excel(writer, index=False, sheet_name='체크인기록')
        
        # 2. 부스 정보 (booths 테이블)
        booths_result = supabase.table('booths').select('*').order('created_at', desc=True).execute()
        if booths_result.data:
            booths_records = []
            for record in booths_result.data:
                booths_records.append({
                    'ID': record['id'],
                    '부스명': record['name'],
                    '설명': record['description'] or '',
                    '활성상태': '활성' if record['is_active'] else '비활성',
                    '생성일시': record['created_at'],
                    '수정일시': record['updated_at']
                })
            df_booths = pd.DataFrame(booths_records)
        else:
            df_booths = pd.DataFrame()
        df_booths.to_excel(writer, index=False, sheet_name='부스정보')
        
        # 3. 발급된 인증서 (certificates 테이블)
        certificates_result = supabase.table('certificates').select('*').order('issued_at', desc=True).execute()
        if certificates_result.data:
            cert_records = []
            for record in certificates_result.data:
                booth_names_str = ', '.join(record['booth_names']) if record['booth_names'] else ''
                cert_records.append({
                    'ID': record['id'],
                    '발급번호': record['certificate_number'],
                    '학교명': record['school'],
                    '학년': record['grade'],
                    '반': record['class'],
                    '번호': record['number'],
                    '이름': record['name'],
                    '체험부스수': record['booth_count'],
                    '체험부스명': booth_names_str,
                    '발급일시': record['issued_at']
                })
            df_certificates = pd.DataFrame(cert_records)
        else:
            df_certificates = pd.DataFrame()
        df_certificates.to_excel(writer, index=False, sheet_name='발급인증서')
        
        # 4. 학생 계정 정보 (students 테이블)
        students_result = supabase.table('students').select('*').order('created_at', desc=True).execute()
        if students_result.data:
            student_records = []
            for record in students_result.data:
                student_records.append({
                    'ID': record['id'],
                    '학생ID': record['student_id'],
                    '비밀번호(암호화)': encrypt_password(record['password']),
                    '학교명': record['school'],
                    '학년': record['grade'],
                    '반': record['class'],
                    '번호': record['number'],
                    '이름': record['name'],
                    '계정생성일시': record['created_at']
                })
            df_students = pd.DataFrame(student_records)
        else:
            df_students = pd.DataFrame()
        df_students.to_excel(writer, index=False, sheet_name='학생계정목록')
        
        # 5. 요약 통계
        summary_data = []
        
        # 전체 학생 수 (중복 제거)
        unique_students = set()
        if checkins_result.data:
            for record in checkins_result.data:
                unique_students.add(f"{record['school']}-{record['grade']}-{record['class']}-{record['number']}-{record['name']}")
        
        summary_data.append(['전체 참여 학생 수', len(unique_students)])
        summary_data.append(['전체 체크인 횟수', len(checkins_result.data) if checkins_result.data else 0])
        summary_data.append(['등록된 부스 수', len(booths_result.data) if booths_result.data else 0])
        summary_data.append(['발급된 인증서 수', len(certificates_result.data) if certificates_result.data else 0])
        summary_data.append(['등록된 학생 계정 수', len(students_result.data) if students_result.data else 0])
        summary_data.append(['데이터 추출 시각', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        
        df_summary = pd.DataFrame(summary_data, columns=['항목', '값'])
        df_summary.to_excel(writer, index=False, sheet_name='요약통계')
    
    output.seek(0)
    return send_file(output, download_name='festival_complete_data.xlsx', as_attachment=True)

@app.route('/admin/certificate-view/<certificate_number>')
def admin_certificate_view(certificate_number):
    if not session.get('admin'):
        return redirect(url_for('admin'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # 인증서 정보 조회
        cert_result = supabase.table('certificates').select('*').eq('certificate_number', certificate_number).execute()
        
        if not cert_result.data:
            flash('인증서를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_certificates'))
        
        certificate = cert_result.data[0]
        
        # 학생의 상세 체험 기록 조회
        records_result = supabase.table('checkins').select('booth, comment, created_at').eq('school', certificate['school']).eq('grade', certificate['grade']).eq('class', certificate['class']).eq('number', certificate['number']).eq('name', certificate['name']).order('created_at', desc=True).execute()
        
        booth_records = {}
        if records_result.data:
            for record in records_result.data:
                booth_name = record['booth']
                if booth_name not in booth_records:
                    booth_records[booth_name] = {
                        'comment': record['comment'],
                        'created_at': record['created_at']
                    }
        
        # 학생 정보 구성
        student_info = {
            'school': certificate['school'],
            'grade': certificate['grade'],
            'class': certificate['class'],
            'number': certificate['number'],
            'name': certificate['name']
        }
        
        # 현재 행사명 가져오기
        event_name = get_event_name()
        
        # PDF 생성
        pdf_buffer = generate_certificate_pdf(student_info, booth_records, certificate_number, event_name)
        
        # PDF를 브라우저에서 직접 보여주기 (다운로드 하지 않음)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,  # False로 설정하면 브라우저에서 직접 열림
            download_name=f'{certificate["name"]}_활동확인서.pdf'
        )
        
    except Exception as e:
        flash(f'인증서 조회 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin_certificates'))

@app.route('/admin/email-certificate', methods=['POST'])
def admin_email_certificate():
    if not session.get('admin'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    # 이메일 기능은 추후 구현 (SMTP 설정 필요)
    # 현재는 기본 응답만 반환
    data = request.get_json()
    certificate_number = data.get('certificate_number')
    student_name = data.get('student_name')
    email_address = data.get('email_address')
    message = data.get('message', '')
    
    try:
        # TODO: 실제 이메일 발송 로직 구현
        # - SMTP 서버 설정
        # - 인증서 PDF 생성
        # - 이메일에 PDF 첨부하여 발송
        
        # 현재는 성공 응답만 반환 (실제 발송은 하지 않음)
        return jsonify({
            'ok': True,
            'message': f'{student_name} 학생의 확인증을 {email_address}로 발송했습니다. (개발 모드: 실제 발송 안됨)'
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'이메일 발송 중 오류: {str(e)}'})

# --- 이미지 폴더 정적 파일 서빙 ---
@app.route('/image/<filename>')
def serve_image(filename):
    """image 폴더의 파일들을 서빙"""
    try:
        return send_file(f'image/{filename}')
    except FileNotFoundError:
        return "파일을 찾을 수 없습니다.", 404

# --- 메인 페이지 ---
@app.route('/')
def index():
    return render_template('index.html')

# =============================================================================
# 부스 운영자 부스 수정 관련 라우트 (올바른 위치로 이동됨)
# =============================================================================

@app.route('/booth-operator/edit-booth/<int:booth_id>')
def booth_operator_edit_booth(booth_id):
    if not session.get('boothOperatorInfo'):
        return redirect(url_for('booth_operator_login'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('booth_operator_dashboard'))
    
    try:
        current_operator = json.loads(session.get('boothOperatorInfo'))

        booth_result = supabase.table('booths').select('*').eq('id', booth_id).single().execute()
        booth = booth_result.data
        
        if not booth or booth['operator_id'] != current_operator['id']:
            flash('해당 부스를 수정할 권한이 없습니다.', 'danger')
            return redirect(url_for('booth_operator_dashboard'))

        return render_template('booth_operator_edit_booth.html', booth=booth)
    except Exception as e:
        flash(f'부스 정보 로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('booth_operator_dashboard'))

@app.route('/api/update-booth-by-operator', methods=['POST'])
def api_update_booth_by_operator():
    if not session.get('boothOperatorInfo'):
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        current_operator = json.loads(session.get('boothOperatorInfo'))
        data = request.form
        booth_id = data.get('id')
        name = data.get('name')
        description = data.get('description')
        location = data.get('location')
        is_active = 'is_active' in data

        if not booth_id or not name or not location or not description:
            return jsonify({'ok': False, 'message': '필수 정보가 누락되었습니다.'})
        
        # 해당 부스가 현재 운영자의 부스인지 다시 확인
        existing_booth_check = supabase.table('booths').select('operator_id').eq('id', booth_id).single().execute()
        if not existing_booth_check.data or existing_booth_check.data['operator_id'] != current_operator['id']:
            return jsonify({'ok': False, 'message': '부스 수정 권한이 없습니다.'}), 403

        # 부스명 중복 확인 (현재 부스 제외)
        existing_booth = supabase.table('booths').select('*').eq('name', name).neq('id', booth_id).execute()
        if existing_booth.data:
            return jsonify({'ok': False, 'message': '이미 존재하는 부스명입니다.'})

        update_data = {
            'name': name,
            'description': description,
            'location': location,
            'is_active': is_active,
            'updated_at': 'now()'
        }

        # PDF 파일 처리
        pdf_file = request.files.get('pdf_file')
        if pdf_file and pdf_file.filename:
            upload_dir = 'static/uploads/booth_pdfs'
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)
            
            import uuid
            safe_filename = f"{uuid.uuid4()}_{pdf_file.filename}"
            file_path = os.path.join(upload_dir, safe_filename)
            pdf_file.save(file_path)
            update_data['pdf_file_path'] = file_path
        
        result = supabase.table('booths').update(update_data).eq('id', booth_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '부스 정보가 성공적으로 업데이트되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '부스 정보 업데이트에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 정보 업데이트 중 오류: {str(e)}'})

# =============================================================================
# Flask 앱 시작점 (반드시 모든 라우트 정의 후에 위치해야 함)
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)