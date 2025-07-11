"""
부스 운영자 관련 라우트 및 API 처리
대구수학축제 부스 예약 및 관리 시스템 - 부스 운영자 Blueprint
"""

import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash

# Import shared utilities and database connections
from app.db import get_supabase
from app.utils import send_sms_notification, generate_safe_filename

# Get database connection
supabase = get_supabase()
SUPABASE_AVAILABLE = supabase is not None

# Create booth operator blueprint
booth_bp = Blueprint('booth', __name__)

# =============================================================================
# 부스 운영자 계정 생성 및 인증 관련 라우트
# =============================================================================

# 하위 호환성을 위한 비-prefix 라우트들
@booth_bp.route('/booth-operator-register')
def booth_operator_register():
    """부스 운영자 계정 생성 페이지 (비-prefix 라우트)"""
    return render_template('booth_operator_register.html')

@booth_bp.route('/register')
def register():
    """부스 운영자 계정 생성 페이지"""
    return render_template('booth_operator_register.html')

@booth_bp.route('/api/create-account', methods=['POST'])
def api_create_account():
    """부스 운영자 계정 생성 API"""
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

@booth_bp.route('/api/check-id-duplicate', methods=['POST'])
def api_check_id_duplicate():
    """부스 운영자 ID 중복 확인 API"""
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

@booth_bp.route('/login')
def login():
    """부스 운영자 로그인 페이지"""
    return render_template('booth_operator_login.html')

@booth_bp.route('/api/login', methods=['POST'])
def api_login():
    """부스 운영자 로그인 API"""
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    
    try:
        # 부스 운영자 계정 조회
        result = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).eq('password', data['password']).execute()
        
        if result.data:
            operator = result.data[0]
            
            # 서버 세션에 부스운영자 정보 저장
            session['boothOperatorInfo'] = json.dumps({
                'id': operator['id'],
                'operator_id': operator['operator_id'],
                'school': operator['school'],
                'club_name': operator['club_name'],
                'booth_topic': operator['booth_topic'],
                'phone': operator['phone'],
                'email': operator['email']
            })
            
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

@booth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """부스 운영자 로그아웃 API"""
    session.pop('boothOperatorInfo', None)
    return jsonify({'ok': True, 'message': '로그아웃되었습니다.'})

# =============================================================================
# 부스 운영자 대시보드 및 부스 관리
# =============================================================================

@booth_bp.route('/dashboard')
def dashboard():
    """부스 운영자 대시보드"""
    return render_template('booth_operator_dashboard.html')

@booth_bp.route('/api/create-booth', methods=['POST'])
def api_create_booth():
    """부스 생성 API"""
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
            safe_filename = generate_safe_filename(pdf_file.filename)
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

@booth_bp.route('/api/operator-booths', methods=['POST'])
def api_operator_booths():
    """운영자 부스 목록 API"""
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

@booth_bp.route('/edit-booth/<int:booth_id>')
def edit_booth(booth_id):
    """부스 수정 페이지"""
    if not session.get('boothOperatorInfo'):
        return redirect(url_for('booth.login'))
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('booth.dashboard'))
    
    try:
        current_operator = json.loads(session.get('boothOperatorInfo'))

        booth_result = supabase.table('booths').select('*').eq('id', booth_id).single().execute()
        booth = booth_result.data
        
        if not booth or booth['operator_id'] != current_operator['id']:
            flash('해당 부스를 수정할 권한이 없습니다.', 'danger')
            return redirect(url_for('booth.dashboard'))

        return render_template('booth_operator_edit_booth.html', booth=booth)
    except Exception as e:
        flash(f'부스 정보 로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('booth.dashboard'))

@booth_bp.route('/api/update-booth', methods=['POST'])
def api_update_booth():
    """부스 정보 수정 API"""
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
            
            safe_filename = generate_safe_filename(pdf_file.filename)
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
# 부스 대기열 관리 및 학생 호출
# =============================================================================

@booth_bp.route('/api/booth-queue', methods=['POST'])
def api_booth_queue():
    """부스 대기열 조회 API"""
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

@booth_bp.route('/api/call-student', methods=['POST'])
def api_call_student():
    """학생 호출 API"""
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

@booth_bp.route('/api/complete-student', methods=['POST'])
def api_complete_student():
    """학생 완료 처리 API"""
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

@booth_bp.route('/api/recall-student', methods=['POST'])
def api_recall_student():
    """학생 재호출 API"""
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
            message = f"[{booth['name']}] 재호출입니다. {booth['location']}로 3분 내 방문해 주세요."
            
            # SOLAPI를 통한 실제 SMS 발송
            sms_success = send_sms_notification(
                phone_number=student['phone'],
                message=message,
                booth_id=entry['booth_id'],
                student_id=entry['student_id']
            )
            
            if sms_success:
                return jsonify({'ok': True, 'message': '학생이 재호출되었고 SMS가 발송되었습니다.'})
            else:
                return jsonify({'ok': True, 'message': '학생이 재호출되었지만 SMS 발송에 실패했습니다.'})
        else:
            return jsonify({'ok': False, 'message': '재호출 상태 업데이트에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'학생 재호출 중 오류: {str(e)}'})

@booth_bp.route('/api/revert-student', methods=['POST'])
def api_revert_student():
    """학생 대기 상태로 되돌리기 API"""
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    data = request.get_json()
    entry_id = data.get('entry_id')
    
    if not entry_id:
        return jsonify({'ok': False, 'message': '대기열 ID가 필요합니다.'})
    
    try:
        # 상태를 'waiting'로 되돌리기
        result = supabase.table('queue_entries').update({
            'status': 'waiting',
            'called_at': None,
            'completed_at': None
        }).eq('id', entry_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '학생이 대기 상태로 되돌려졌습니다.'})
        else:
            return jsonify({'ok': False, 'message': '되돌리기에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'되돌리기 중 오류: {str(e)}'})

# =============================================================================
# 하위 호환성을 위한 비-prefix 라우트들 (기존 app.py에서 마이그레이션)
# =============================================================================

@booth_bp.route('/api/create-booth-operator-account', methods=['POST'])
def api_create_booth_operator_account():
    """부스 운영자 계정 생성 API (비-prefix 라우트)"""
    return api_create_account()

@booth_bp.route('/api/check-operator-id-duplicate', methods=['POST'])
def api_check_operator_id_duplicate():
    """부스 운영자 ID 중복 확인 API (비-prefix 라우트)"""
    return api_check_id_duplicate()

@booth_bp.route('/booth-operator-login')
def booth_operator_login():
    """부스 운영자 로그인 페이지 (비-prefix 라우트)"""
    return render_template('booth_operator_login.html')

@booth_bp.route('/api/booth-operator-login', methods=['POST'])
def api_booth_operator_login():
    """부스 운영자 로그인 API (비-prefix 라우트)"""
    return api_login()

@booth_bp.route('/booth-operator-dashboard')
def booth_operator_dashboard():
    """부스 운영자 대시보드 (비-prefix 라우트)"""
    return render_template('booth_operator_dashboard.html')

@booth_bp.route('/api/create-booth', methods=['POST'])
def api_create_booth_legacy():
    """부스 생성 API (비-prefix 라우트)"""
    return api_create_booth()

@booth_bp.route('/api/operator-booths', methods=['POST'])
def api_operator_booths_legacy():
    """운영자 부스 목록 API (비-prefix 라우트)"""
    return api_operator_booths()

@booth_bp.route('/api/booth-queue', methods=['POST'])
def api_booth_queue_legacy():
    """부스 대기열 조회 API (비-prefix 라우트)"""
    return api_booth_queue()

@booth_bp.route('/api/call-student', methods=['POST'])
def api_call_student_legacy():
    """학생 호출 API (비-prefix 라우트)"""
    return api_call_student()

@booth_bp.route('/api/complete-student', methods=['POST'])
def api_complete_student_legacy():
    """학생 완료 처리 API (비-prefix 라우트)"""
    return api_complete_student()

@booth_bp.route('/booth-operator/edit-booth/<int:booth_id>')
def booth_operator_edit_booth(booth_id):
    """부스 수정 페이지 (비-prefix 라우트)"""
    return edit_booth(booth_id)

@booth_bp.route('/api/update-booth-by-operator', methods=['POST'])
def api_update_booth_by_operator():
    """부스 정보 수정 API (비-prefix 라우트)"""
    return api_update_booth()