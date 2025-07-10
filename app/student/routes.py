"""
대구수학축제 부스 예약 및 관리 시스템 - 학생 관련 라우트

이 모듈은 학생 관련 모든 기능을 처리합니다:
- 학생 계정 생성 및 로그인
- 학생 대시보드
- 부스 목록 조회 및 대기열 관리
- QR 체크인 및 소감 작성
- 활동 확인증 발급
- 학생 활동 기록 관리
"""

import os
import base64
import hashlib
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, session, flash
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

# Blueprint 생성
student_bp = Blueprint('student', __name__, url_prefix='/student')

# Supabase 초기화 (main app에서 전역 변수로 가져오기)
SUPABASE_AVAILABLE = False
supabase = None
SOLAPI_AVAILABLE = False
solapi_service = None
SOLAPI_API_KEY = ""
SOLAPI_API_SECRET = ""
SOLAPI_SENDER_PHONE = ""

def init_student_routes(app):
    """학생 라우트 초기화 (main app의 전역 변수들을 가져오기)"""
    global SUPABASE_AVAILABLE, supabase, SOLAPI_AVAILABLE, solapi_service
    global SOLAPI_API_KEY, SOLAPI_API_SECRET, SOLAPI_SENDER_PHONE
    
    # main app의 전역 변수들 가져오기
    SUPABASE_AVAILABLE = getattr(app, 'SUPABASE_AVAILABLE', False)
    supabase = getattr(app, 'supabase', None)
    SOLAPI_AVAILABLE = getattr(app, 'SOLAPI_AVAILABLE', False)
    solapi_service = getattr(app, 'solapi_service', None)
    SOLAPI_API_KEY = getattr(app, 'SOLAPI_API_KEY', "")
    SOLAPI_API_SECRET = getattr(app, 'SOLAPI_API_SECRET', "")
    SOLAPI_SENDER_PHONE = getattr(app, 'SOLAPI_SENDER_PHONE', "")

# === 헬퍼 함수들 ===

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
        
        # SOLAPI를 통한 SMS 발송
        response = solapi_service.send_one({
            'to': clean_phone,
            'from': SOLAPI_SENDER_PHONE,
            'text': message
        })
        
        # 발송 결과 로깅
        success = True
        error_message = None
        
        if hasattr(response, 'status_code'):
            if response.status_code == 200:
                print(f"✅ SMS 발송 성공: {phone_number}")
                success = True
            else:
                print(f"❌ SMS 발송 실패: {phone_number}, 상태코드: {response.status_code}")
                success = False
                error_message = f"HTTP {response.status_code}"
        else:
            print(f"✅ SMS 발송 완료: {phone_number}")
            success = True
        
        # 알림 로그 저장
        if SUPABASE_AVAILABLE:
            try:
                log_data = {
                    'phone_number': phone_number,
                    'message': message,
                    'success': success,
                    'error_message': error_message,
                    'booth_id': booth_id,
                    'student_id': student_id
                }
                supabase.table('notifications').insert(log_data).execute()
            except Exception as log_error:
                print(f"알림 로그 저장 실패: {log_error}")
        
        return success
        
    except Exception as e:
        print(f"SMS 발송 중 오류: {e}")
        
        # 실패 로그 저장
        if SUPABASE_AVAILABLE:
            try:
                log_data = {
                    'phone_number': phone_number,
                    'message': message,
                    'success': False,
                    'error_message': str(e),
                    'booth_id': booth_id,
                    'student_id': student_id
                }
                supabase.table('notifications').insert(log_data).execute()
            except Exception as log_error:
                print(f"실패 로그 저장 실패: {log_error}")
        
        return False

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
        font_path = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'NanumGothic.ttf')
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
    custom_seal_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'seal.png')
    default_seal_path = os.path.join(os.path.dirname(__file__), '..', 'image', 'GanIn.png')
    
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

# === 학생 라우트들 ===

# --- 학생 정보 입력 페이지 ---
@student_bp.route('/info')
def student_info():
    return render_template('student_info.html')

# --- 학생 계정 생성 API ---
@student_bp.route('/api/create-account', methods=['POST'])
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
@student_bp.route('/api/login', methods=['POST'])
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
@student_bp.route('/api/check-id-duplicate', methods=['POST'])
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
@student_bp.route('/login')
def student_login():
    booth = request.args.get('booth', '')
    return render_template('student_login.html', booth=booth)

# --- 학생 대시보드 ---
@student_bp.route('/dashboard')
def student_dashboard():
    return render_template('student_dashboard.html')

# --- 학생용 부스 목록 API ---
@student_bp.route('/api/booth-list', methods=['POST'])
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
@student_bp.route('/api/apply-to-queue', methods=['POST'])
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
@student_bp.route('/api/my-queue', methods=['POST'])
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
@student_bp.route('/api/cancel-queue', methods=['POST'])
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
@student_bp.route('/checkin', methods=['GET', 'POST'])
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
@student_bp.route('/checkin/<path:booth_param>')
def checkin_path(booth_param):
    # booth=부스명 형식에서 부스명 추출
    if booth_param.startswith('booth='):
        booth = booth_param[6:]  # 'booth=' 제거
    else:
        booth = booth_param
    return render_template('checkin.html', booth=booth)

# --- 확인증 발급 페이지 ---
@student_bp.route('/certificate')
def certificate():
    return render_template('certificate.html')

# --- 학생 체험 기록 조회 API ---
@student_bp.route('/api/records', methods=['POST'])
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
@student_bp.route('/api/certificate', methods=['POST'])
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
@student_bp.route('/api/generate-certificate-pdf', methods=['POST'])
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
@student_bp.route('/api/update-comment', methods=['POST'])
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
@student_bp.route('/api/delete-record', methods=['POST'])
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
@student_bp.route('/api/add-record', methods=['POST'])
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
            return jsonify({'ok': True, 'message': '새 기록이 추가되었습니다.', 'record': result.data[0]})
        else:
            return jsonify({'ok': False, 'message': '기록 추가에 실패했습니다.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'기록 추가 중 오류: {str(e)}'})

# === 부스 운영자가 호출하는 학생 관련 API들 (admin 권한 필요 없음) ===

# --- 학생 호출 API ---
@student_bp.route('/api/call-student', methods=['POST'])
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
@student_bp.route('/api/complete-student', methods=['POST'])
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