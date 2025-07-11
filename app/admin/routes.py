"""
Admin routes for the Korean festival booth reservation system.
Handles all administrative functions including user management, booth management,
certificates, data exports, and system monitoring.
"""

import os
import json
import uuid
import shutil
import pandas as pd
from io import BytesIO
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, session, flash
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Import shared utilities and database connections
from app.db import get_supabase
from app.utils import (
    get_event_name, set_event_name, generate_certificate_number, encrypt_password,
    create_qr_with_text, save_qr_code_file, generate_certificate_pdf,
    generate_safe_filename
)

# Get database connection
supabase = get_supabase()
SUPABASE_AVAILABLE = supabase is not None

# Create admin blueprint
admin_bp = Blueprint('admin', __name__)

# === Authentication Middleware ===

def admin_required():
    """Check if user has admin privileges"""
    if not session.get('admin'):
        return redirect(url_for('admin.admin_login'))
    return None

# === Main Admin Routes ===

@admin_bp.route('/', methods=['GET', 'POST'])
def admin_login():
    """Admin login page with password authentication"""
    if request.method == 'POST':
        pw = request.form.get('pw', '')
        if pw == 'admin':
            session['admin'] = True
            return redirect(url_for('admin.admin_login'))
        else:
            flash('비밀번호가 틀렸습니다.', 'danger')
    return render_template('admin.html')

@admin_bp.route('/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('admin.admin_login'))

# === QR Code Management ===

@admin_bp.route('/qr-generator')
def qr_generator():
    """QR code generator page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    return render_template('qr_generator.html')

@admin_bp.route('/generate-qr', methods=['POST'])
def generate_qr():
    """Generate QR code for booth"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'error': 'Unauthorized'}), 401
    
    booth_name = request.form.get('booth_name')
    booth_description = request.form.get('booth_description', '')
    
    if not booth_name:
        return jsonify({'error': '부스명을 입력해주세요'}), 400
    
    if not SUPABASE_AVAILABLE:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        # Save booth data to Supabase (update if exists)
        result = supabase.table('booths').select('id').eq('name', booth_name).execute()
        
        if result.data:
            # Update existing booth
            supabase.table('booths').update({
                'description': booth_description,
                'is_active': True,
                'updated_at': 'now()'
            }).eq('name', booth_name).execute()
        else:
            # Create new booth
            supabase.table('booths').insert({
                'name': booth_name,
                'description': booth_description,
                'is_active': True
            }).execute()
        
        # Generate QR code URL
        base_url = os.environ.get('BASE_URL', 'https://dgmathft.up.railway.app')
        qr_url = f"{base_url}/checkin?booth={booth_name}"
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Generate QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Create final image with booth name
        final_img = create_qr_with_text(qr_img, booth_name)
        
        # Convert image to bytes
        img_byte_arr = BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Save QR code file for reuse
        save_qr_code_file(booth_name, final_img)
        
        return send_file(img_byte_arr, mimetype='image/png', download_name=f'qr_{booth_name}.png')
        
    except Exception as e:
        return jsonify({'error': f'부스 생성 중 오류: {str(e)}'}), 500

@admin_bp.route('/download-qr/<booth_name>')
def download_qr_code(booth_name):
    """Download QR code for specific booth"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    try:
        # Query booth information
        result = supabase.table('booths').select('qr_file_path').eq('name', booth_name).execute()
        
        if result.data and result.data[0]['qr_file_path']:
            qr_file_path = result.data[0]['qr_file_path']
            
            # Check if file exists
            if os.path.exists(qr_file_path):
                return send_file(qr_file_path, as_attachment=True, download_name=f'qr_{booth_name}.png')
            else:
                # Generate new QR code if file doesn't exist
                return regenerate_qr_code(booth_name)
        else:
            # Generate new QR code if not exists
            return regenerate_qr_code(booth_name)
            
    except Exception as e:
        flash(f'QR 코드 다운로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_booths'))

def regenerate_qr_code(booth_name):
    """Regenerate QR code for booth"""
    try:
        # Generate QR code URL
        base_url = os.environ.get('BASE_URL', 'https://dgmathft.up.railway.app')
        qr_url = f"{base_url}/checkin?booth={booth_name}"
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Generate QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Create final image with booth name
        final_img = create_qr_with_text(qr_img, booth_name)
        
        # Save QR code file
        save_qr_code_file(booth_name, final_img)
        
        # Convert image to bytes for download
        img_byte_arr = BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return send_file(img_byte_arr, mimetype='image/png', as_attachment=True, download_name=f'qr_{booth_name}.png')
        
    except Exception as e:
        flash(f'QR 코드 재생성 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_booths'))

# === Booth Management ===

@admin_bp.route('/booths')
def admin_booths():
    """Booth management page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    # Query all booths
    result = supabase.table('booths').select('*').order('created_at', desc=True).execute()
    booths = result.data if result.data else []
    
    return render_template('admin_booths.html', booths=booths)

@admin_bp.route('/edit-booth/<int:booth_id>')
def admin_edit_booth(booth_id):
    """Edit booth page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    try:
        # Query booth information
        booth_result = supabase.table('booths').select('*').eq('id', booth_id).single().execute()
        booth = booth_result.data
        
        if not booth:
            flash('해당 부스를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.admin_booths'))
        
        # Query operators list
        operators_result = supabase.table('booth_operators').select('*').order('club_name').execute()
        operators = operators_result.data if operators_result.data else []
        
        return render_template('admin_edit_booth.html', booth=booth, operators=operators)
    except Exception as e:
        flash(f'부스 정보 로드 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_booths'))

@admin_bp.route('/api/update-booth', methods=['POST'])
def admin_api_update_booth():
    """API endpoint to update booth information"""
    auth_check = admin_required()
    if auth_check:
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
        
        # Check for duplicate booth name (excluding current booth)
        existing_booth = supabase.table('booths').select('*').eq('name', name).neq('id', booth_id).execute()
        if existing_booth.data:
            return jsonify({'ok': False, 'message': f'부스명 "{name}"이 이미 사용중입니다.'})

        # Update booth information
        update_data = {
            'name': name,
            'description': description,
            'location': location,
            'operator_id': int(operator_id),
            'is_active': is_active
        }
        
        # Handle PDF file upload
        if 'pdf_file' in request.files:
            pdf_file = request.files['pdf_file']
            if pdf_file and pdf_file.filename:
                # Delete existing PDF file
                booth_result = supabase.table('booths').select('pdf_file_path').eq('id', booth_id).single().execute()
                if booth_result.data and booth_result.data.get('pdf_file_path'):
                    old_pdf_path = booth_result.data['pdf_file_path']
                    if os.path.exists(old_pdf_path):
                        os.remove(old_pdf_path)
                
                # Save new PDF file
                safe_filename = generate_safe_filename(pdf_file.filename)
                pdf_filename = f"booth_{booth_id}_{safe_filename}"
                pdf_path = os.path.join('static/uploads/booth_pdfs', pdf_filename)
                
                # Ensure upload directory exists
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                
                pdf_file.save(pdf_path)
                update_data['pdf_file_path'] = pdf_path

        result = supabase.table('booths').update(update_data).eq('id', booth_id).execute()
        
        if result.data:
            return jsonify({'ok': True, 'message': '부스 정보가 성공적으로 업데이트되었습니다.'})
        else:
            return jsonify({'ok': False, 'message': '부스 업데이트에 실패했습니다.'})
            
    except Exception as e:
        return jsonify({'ok': False, 'message': f'부스 업데이트 중 오류: {str(e)}'})

@admin_bp.route('/delete-booth/<booth_name>', methods=['POST'])
def delete_booth(booth_name):
    """Delete booth"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booths'))
    
    try:
        # Delete booth and related checkin records
        result = supabase.table('booths').delete().eq('name', booth_name).execute()
        
        if result.data:
            # Delete QR code file as well
            qr_file_path = f"static/qr_codes/qr_{booth_name}.png"
            if os.path.exists(qr_file_path):
                os.remove(qr_file_path)
            
            flash(f'부스 "{booth_name}"이(가) 삭제되었습니다.', 'success')
        else:
            flash(f'부스 "{booth_name}" 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'부스 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_booths'))

@admin_bp.route('/clear-all-booths', methods=['POST'])
def clear_all_booths():
    """Clear all booths"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booths'))
    
    try:
        # Delete all booths
        result = supabase.table('booths').delete().neq('id', 0).execute()
        
        # Delete QR code files as well
        qr_dir = 'static/qr_codes'
        if os.path.exists(qr_dir):
            shutil.rmtree(qr_dir)
            os.makedirs(qr_dir)
        
        flash('모든 부스가 초기화되었습니다.', 'success')
        
    except Exception as e:
        flash(f'부스 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_booths'))

# === Student Management ===

@admin_bp.route('/student-records')
def admin_student_records():
    """Student records page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    # Query all students (remove duplicates)
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

@admin_bp.route('/student-accounts')
def admin_student_accounts():
    """Student accounts management page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    # Query all student accounts
    result = supabase.table('students').select('*').order('created_at', desc=True).execute()
    students = result.data if result.data else []
    
    return render_template('admin_student_accounts.html', students=students)

@admin_bp.route('/add-student-account', methods=['POST'])
def add_student_account():
    """Add new student account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_student_accounts'))
    
    try:
        data = request.form
        
        # Check for duplicate student ID
        existing = supabase.table('students').select('*').eq('student_id', data['student_id']).execute()
        if existing.data:
            flash(f'ID "{data["student_id"]}"가 이미 존재합니다.', 'danger')
            return redirect(url_for('admin.admin_student_accounts'))
        
        # Check for duplicate student (school-grade-class-number)
        existing_student = supabase.table('students').select('*').eq('school', data['school']).eq('grade', int(data['grade'])).eq('class', int(data['class'])).eq('number', int(data['number'])).execute()
        if existing_student.data:
            flash(f'{data["school"]} {data["grade"]}학년 {data["class"]}반 {data["number"]}번 학생이 이미 존재합니다.', 'danger')
            return redirect(url_for('admin.admin_student_accounts'))
        
        # Create new student account
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
    
    return redirect(url_for('admin.admin_student_accounts'))

@admin_bp.route('/edit-student-account/<int:student_id>', methods=['POST'])
def edit_student_account(student_id):
    """Edit student account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_student_accounts'))
    
    try:
        data = request.form
        
        # Check if another student is using the same student_id
        existing = supabase.table('students').select('*').eq('student_id', data['student_id']).neq('id', student_id).execute()
        if existing.data:
            flash(f'ID "{data["student_id"]}"가 다른 학생에 의해 사용 중입니다.', 'danger')
            return redirect(url_for('admin.admin_student_accounts'))
        
        # Update student account
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
    
    return redirect(url_for('admin.admin_student_accounts'))

@admin_bp.route('/delete-student-account/<int:student_id>', methods=['POST'])
def delete_student_account(student_id):
    """Delete student account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_student_accounts'))
    
    try:
        # Query student information
        student = supabase.table('students').select('*').eq('id', student_id).execute()
        if not student.data:
            flash('학생을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.admin_student_accounts'))
        
        student_name = student.data[0]['name']
        
        # Delete student account
        result = supabase.table('students').delete().eq('id', student_id).execute()
        
        if result.data:
            flash(f'학생 계정 "{student_name}"이 삭제되었습니다.', 'success')
        else:
            flash('계정 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_student_accounts'))

# === Booth Operator Management ===

@admin_bp.route('/booth-operators')
def admin_booth_operators():
    """Booth operators management page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    # Query all booth operators
    result = supabase.table('booth_operators').select('*').order('created_at', desc=True).execute()
    operators = result.data if result.data else []
    
    return render_template('admin_booth_operators.html', operators=operators)

@admin_bp.route('/add-booth-operator-account', methods=['POST'])
def add_booth_operator_account():
    """Add new booth operator account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booth_operators'))
    
    try:
        data = request.form
        
        # Check for duplicates
        existing = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).execute()
        if existing.data:
            flash(f'ID "{data["operator_id"]}"가 이미 존재합니다.', 'danger')
            return redirect(url_for('admin.admin_booth_operators'))
        
        # Create new booth operator account
        operator_data = {
            'operator_id': data['operator_id'],
            'password': data['password'],
            'school': data['school'],
            'club_name': data['club_name'],
            'booth_topic': data['booth_topic'],
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
    
    return redirect(url_for('admin.admin_booth_operators'))

@admin_bp.route('/edit-booth-operator-account/<int:operator_id>', methods=['POST'])
def edit_booth_operator_account(operator_id):
    """Edit booth operator account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booth_operators'))
    
    try:
        data = request.form
        
        # Check if another operator is using the same operator_id
        existing = supabase.table('booth_operators').select('*').eq('operator_id', data['operator_id']).neq('id', operator_id).execute()
        if existing.data:
            flash(f'ID "{data["operator_id"]}"가 다른 운영자에 의해 사용 중입니다.', 'danger')
            return redirect(url_for('admin.admin_booth_operators'))
        
        # Update operator account
        update_data = {
            'operator_id': data['operator_id'],
            'school': data['school'],
            'club_name': data['club_name'],
            'booth_topic': data['booth_topic'],
            'phone': data['phone'],
            'email': data['email'],
            'is_active': 'is_active' in data
        }
        
        # Update password only if provided
        if data.get('password'):
            update_data['password'] = data['password']
        
        result = supabase.table('booth_operators').update(update_data).eq('id', operator_id).execute()
        
        if result.data:
            flash(f'부스 운영자 계정이 성공적으로 수정되었습니다.', 'success')
        else:
            flash('계정 수정에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 수정 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_booth_operators'))

@admin_bp.route('/delete-booth-operator-account/<int:operator_id>', methods=['POST'])
def delete_booth_operator_account(operator_id):
    """Delete booth operator account"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booth_operators'))
    
    try:
        # Query operator information
        operator = supabase.table('booth_operators').select('*').eq('id', operator_id).execute()
        if not operator.data:
            flash('운영자를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.admin_booth_operators'))
        
        operator_name = operator.data[0]['operator_id']
        
        # Delete operator account
        result = supabase.table('booth_operators').delete().eq('id', operator_id).execute()
        
        if result.data:
            flash(f'부스 운영자 계정 "{operator_name}"이 삭제되었습니다.', 'success')
        else:
            flash('계정 삭제에 실패했습니다.', 'danger')
            
    except Exception as e:
        flash(f'계정 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_booth_operators'))

@admin_bp.route('/toggle-booth-operator-status/<int:operator_id>', methods=['POST'])
def toggle_booth_operator_status(operator_id):
    """Toggle booth operator active status"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booth_operators'))
    
    try:
        # Query current status
        operator = supabase.table('booth_operators').select('*').eq('id', operator_id).execute()
        if not operator.data:
            flash('운영자를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.admin_booth_operators'))
        
        current_status = operator.data[0]['is_active']
        new_status = not current_status
        
        # Update status
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
    
    return redirect(url_for('admin.admin_booth_operators'))

@admin_bp.route('/clear-all-booth-operators', methods=['POST'])
def clear_all_booth_operators():
    """Clear all booth operators"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_booth_operators'))
    
    try:
        # Delete all booth operators
        result = supabase.table('booth_operators').delete().neq('id', 0).execute()
        
        flash('모든 부스 운영자가 삭제되었습니다.', 'success')
        
    except Exception as e:
        flash(f'부스 운영자 삭제 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_booth_operators'))

# === Queue Status Monitoring ===

@admin_bp.route('/queue-status')
def admin_queue_status():
    """Queue status monitoring page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    return render_template('admin_queue_status.html')

@admin_bp.route('/api/queue-status')
def admin_api_queue_status():
    """API endpoint for queue status data"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    if not SUPABASE_AVAILABLE:
        return jsonify({'ok': False, 'message': 'Supabase not configured'}), 500
    
    try:
        # Calculate overall statistics
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
        
        # Booth-specific queue status
        booths_detail = supabase.table('booths').select('''
            *, 
            booth_operators(club_name)
        ''').execute()
        
        booths = []
        if booths_detail.data:
            for booth in booths_detail.data:
                # Calculate queue status for each booth
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
        
        # Recent notifications
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

# === Certificate Management ===

@admin_bp.route('/certificates')
def admin_certificates():
    """Certificate management page"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    # Get current event name
    current_event_name = get_event_name()
    
    # Query issued certificates
    certificates_result = supabase.table('certificates').select('*').order('issued_at', desc=True).execute()
    certificates = certificates_result.data if certificates_result.data else []
    
    # Query eligible students (3+ booth experiences)
    checkins_result = supabase.table('checkins').select('school, grade, class, number, name, booth').execute()
    
    # Calculate booth experience count per student
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
    
    # Filter students with 3+ booth experiences
    eligible_students = []
    for student_key, student_data in student_booth_count.items():
        booth_count = len(student_data['booths'])
        if booth_count >= 3:
            # Check if certificate already exists
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
    
    # Sort (unissued -> issued)
    eligible_students.sort(key=lambda x: (x['certificate_number'] is not None, x['name']))
    
    return render_template('admin_certificates.html', 
                         certificates=certificates,
                         eligible_students=eligible_students,
                         eligible_count=len(eligible_students),
                         total_participants=len(total_participants),
                         current_event_name=current_event_name)

@admin_bp.route('/issue-certificate', methods=['POST'])
def admin_issue_certificate():
    """Issue certificate for student"""
    auth_check = admin_required()
    if auth_check:
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
        # Verify student's experience records
        result = supabase.table('checkins').select('booth, comment, created_at').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).order('created_at', desc=True).execute()
        
        booth_records = {}
        if result.data:
            for record in result.data:
                booth_name = record['booth']
                # Store only the latest record per booth
                if booth_name not in booth_records:
                    booth_records[booth_name] = {
                        'comment': record['comment'],
                        'created_at': record['created_at']
                    }
        
        booth_count = len(booth_records)
        if booth_count < 3:
            return jsonify({'ok': False, 'message': f'체험 부스가 부족합니다. (현재 {booth_count}개, 최소 3개 필요)'})
        
        # Check if certificate already exists
        existing_cert = supabase.table('certificates').select('certificate_number').eq('school', school).eq('grade', int(grade)).eq('class', int(class_)).eq('number', int(number)).eq('name', name).execute()
        
        if existing_cert.data:
            return jsonify({'ok': False, 'message': '이미 확인증이 발급되었습니다.', 'certificate_number': existing_cert.data[0]['certificate_number']})
        
        # Issue new certificate
        cert_id = generate_certificate_number()
        booth_names = list(booth_records.keys())
        
        # Save certificate to database
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

@admin_bp.route('/certificate-view/<certificate_number>')
def admin_certificate_view(certificate_number):
    """View certificate PDF"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    try:
        # Query certificate information
        cert_result = supabase.table('certificates').select('*').eq('certificate_number', certificate_number).execute()
        
        if not cert_result.data:
            flash('인증서를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.admin_certificates'))
        
        certificate = cert_result.data[0]
        
        # Query student's detailed experience records
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
        
        # Construct student information
        student_info = {
            'school': certificate['school'],
            'grade': certificate['grade'],
            'class': certificate['class'],
            'number': certificate['number'],
            'name': certificate['name']
        }
        
        # Get current event name
        event_name = get_event_name()
        
        # Generate PDF
        pdf_buffer = generate_certificate_pdf(student_info, booth_records, certificate_number, event_name)
        
        # Show PDF directly in browser (not download)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,  # False = show in browser
            download_name=f'{certificate["name"]}_활동확인서.pdf'
        )
        
    except Exception as e:
        flash(f'인증서 조회 중 오류: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_certificates'))

@admin_bp.route('/email-certificate', methods=['POST'])
def admin_email_certificate():
    """Email certificate (placeholder implementation)"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    # Email functionality to be implemented later (requires SMTP setup)
    data = request.get_json()
    certificate_number = data.get('certificate_number')
    student_name = data.get('student_name')
    email_address = data.get('email_address')
    message = data.get('message', '')
    
    try:
        # TODO: Implement actual email sending logic
        # - SMTP server configuration
        # - Certificate PDF generation
        # - Email with PDF attachment
        
        # Currently returns success response only (no actual sending)
        return jsonify({
            'ok': True,
            'message': f'{student_name} 학생의 확인증을 {email_address}로 발송했습니다. (개발 모드: 실제 발송 안됨)'
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'message': f'이메일 발송 중 오류: {str(e)}'})

# === Event Settings ===

@admin_bp.route('/update-event-name', methods=['POST'])
def admin_update_event_name():
    """Update event name"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    event_name = data.get('event_name', '').strip()
    
    if not event_name:
        return jsonify({'ok': False, 'message': '행사명을 입력해주세요.'})
    
    try:
        # Check if settings table exists
        test_query = supabase.table('settings').select('id').limit(1).execute()
    except Exception as e:
        if 'relation "public.settings" does not exist' in str(e):
            return jsonify({'ok': False, 'message': 'settings 테이블이 존재하지 않습니다. 관리자에게 문의하세요.'})
    
    if set_event_name(event_name):
        return jsonify({'ok': True, 'message': '행사명이 업데이트되었습니다.'})
    else:
        return jsonify({'ok': False, 'message': '행사명 업데이트에 실패했습니다. 서버 로그를 확인하세요.'})

# === Seal Management ===

@admin_bp.route('/upload-seal', methods=['POST'])
def admin_upload_seal():
    """Upload custom seal image"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    if 'seal_image' not in request.files:
        return jsonify({'ok': False, 'message': '이미지 파일이 필요합니다.'})
    
    file = request.files['seal_image']
    if file.filename == '':
        return jsonify({'ok': False, 'message': '파일이 선택되지 않았습니다.'})
    
    if file and file.filename:
        try:
            # Create static directory if it doesn't exist
            static_dir = 'static'
            if not os.path.exists(static_dir):
                os.makedirs(static_dir)
            
            # Delete existing seal file
            seal_path = 'static/seal.png'
            if os.path.exists(seal_path):
                os.remove(seal_path)
            
            # Save new seal file (always as seal.png)
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

@admin_bp.route('/get-current-seal')
def admin_get_current_seal():
    """Get current seal information"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    custom_seal_path = 'static/seal.png'
    default_seal_path = 'image/GanIn.png'
    
    # Priority 1: Custom seal
    if os.path.exists(custom_seal_path):
        return jsonify({
            'ok': True, 
            'seal_url': '/static/seal.png',
            'is_custom': True,
            'seal_type': 'custom'
        })
    # Priority 2: Default seal
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

@admin_bp.route('/reset-seal', methods=['POST'])
def admin_reset_seal():
    """Reset to default seal"""
    auth_check = admin_required()
    if auth_check:
        return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Delete custom seal file
        custom_seal_path = 'static/seal.png'
        if os.path.exists(custom_seal_path):
            os.remove(custom_seal_path)
        
        # Check default seal
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

# === Data Management ===

@admin_bp.route('/download')
def admin_download():
    """Download all data as Excel file"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured. Cannot download data.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        # 1. Checkin records
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
        
        # 2. Booth information
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
        
        # 3. Issued certificates
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
        
        # 4. Student accounts
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
        
        # 5. Summary statistics
        summary_data = []
        
        # Total unique students (remove duplicates)
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

@admin_bp.route('/clear-all-data', methods=['POST'])
def clear_all_data():
    """Clear all system data"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    try:
        # Delete data from all tables
        # 1. Delete checkin records
        supabase.table('checkins').delete().neq('id', 0).execute()
        
        # 2. Delete certificates
        supabase.table('certificates').delete().neq('id', 0).execute()
        
        # 3. Delete booths
        supabase.table('booths').delete().neq('id', 0).execute()
        
        # 4. Delete student accounts
        supabase.table('students').delete().neq('id', 0).execute()
        
        # 5. Delete QR code files
        qr_dir = 'static/qr_codes'
        if os.path.exists(qr_dir):
            shutil.rmtree(qr_dir)
            os.makedirs(qr_dir)
        
        flash('모든 데이터가 초기화되었습니다.', 'success')
        
    except Exception as e:
        flash(f'데이터 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/init-database', methods=['POST'])
def init_database_tables():
    """Initialize database tables (provides SQL for manual execution)"""
    auth_check = admin_required()
    if auth_check:
        return auth_check
    
    if not SUPABASE_AVAILABLE:
        flash('Supabase not configured.', 'danger')
        return redirect(url_for('admin.admin_login'))
    
    try:
        # SQL statements for table creation
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
        
        # Try to access tables to check if they exist
        try:
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
            # Tables don't exist, provide creation guide
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
            # ... (other table creation SQL would be printed)
            print("=" * 60)
        
    except Exception as e:
        flash(f'데이터베이스 초기화 중 오류: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_login'))

