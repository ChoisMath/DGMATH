"""
Main routes for the Korean festival booth reservation system.
Handles general application routes that don't belong to specific modules.
"""

import os
from flask import Blueprint, render_template, send_file, request, jsonify

# Import shared utilities and database connections
from app.db import get_supabase

# Get database connection
supabase = get_supabase()
SUPABASE_AVAILABLE = supabase is not None

# Create main blueprint
main_bp = Blueprint('main', __name__)

# === Main Application Routes ===

@main_bp.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')

@main_bp.route('/image/<filename>')
def serve_image(filename):
    """Serve images from the image folder"""
    try:
        return send_file(f'image/{filename}')
    except FileNotFoundError:
        return "파일을 찾을 수 없습니다.", 404

# === Public QR Code Routes ===

@main_bp.route('/checkin', methods=['GET', 'POST'])
def checkin():
    """QR code booth check-in page"""
    booth = request.args.get('booth', '')
    
    if request.method == 'POST':
        if not SUPABASE_AVAILABLE:
            return jsonify({'result': 'error', 'message': 'Supabase not configured'}), 500
        
        data = request.get_json()
        
        # Save check-in data to Supabase
        checkin_data = {
            'school': data['school'],
            'grade': int(data['grade']),
            'class': int(data['class']),
            'number': int(data['number']),
            'name': data['name'],
            'booth': data['booth'],
            'comment': data['comment']
        }
        
        try:
            result = supabase.table('checkins').insert(checkin_data).execute()
            if result.data:
                return jsonify({'result': 'success'})
            else:
                return jsonify({'result': 'error', 'message': 'Failed to save data'}), 500
        except Exception as e:
            return jsonify({'result': 'error', 'message': f'Error: {str(e)}'}), 500
    
    return render_template('checkin.html', booth=booth)

@main_bp.route('/checkin/<path:booth_param>')
def checkin_path(booth_param):
    """QR code booth check-in page with URL path format support"""
    # Extract booth name from booth=booth_name format
    if booth_param.startswith('booth='):
        booth = booth_param[6:]  # Remove 'booth=' prefix
    else:
        booth = booth_param
    return render_template('checkin.html', booth=booth)

@main_bp.route('/certificate')
def certificate():
    """Certificate issuance page"""
    return render_template('certificate.html')

# === Student Page Redirects ===

@main_bp.route('/student-login')
def student_login_redirect():
    """Redirect to proper student login route"""
    from flask import redirect, url_for
    return redirect(url_for('student.student_login'))

@main_bp.route('/student_info')  
def student_info_redirect():
    """Redirect to proper student info route"""
    from flask import redirect, url_for
    return redirect(url_for('student.student_info'))

# === Health Check Route ===

@main_bp.route('/health')
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Korean Festival Booth Reservation System',
        'database': 'connected' if SUPABASE_AVAILABLE else 'disconnected'
    })

# === Static File Serving ===

@main_bp.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (fallback for when static files aren't served by web server)"""
    try:
        return send_file(f'static/{filename}')
    except FileNotFoundError:
        return "파일을 찾을 수 없습니다.", 404