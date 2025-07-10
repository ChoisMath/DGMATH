"""
대구수학축제 부스 예약 및 관리 시스템 - 유틸리티 함수들

이 파일은 app.py에서 추출한 유틸리티 함수들을 포함합니다:
- 파일 처리 관련 함수
- SMS 발송 기능
- 인증서 생성
- 암호화 및 보안
- QR 코드 생성
- 데이터 포맷팅 함수들
"""

import os
import base64
import hashlib
import uuid
import math
from datetime import datetime, timedelta
from io import BytesIO
import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from werkzeug.utils import secure_filename
from app.db import get_solapi, get_supabase
from app.config import Config
from solapi.model import RequestMessage

def encrypt_password(password):
    """비밀번호를 암호화 (Base64 + MD5 해시)"""
    try:
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        return base64.b64encode(md5_hash.encode()).decode()
    except Exception as e:
        print(f"비밀번호 암호화 중 오류: {e}")
        return None

def generate_safe_filename(original_filename):
    """안전한 파일명 생성 (UUID 기반)"""
    try:
        filename = secure_filename(original_filename)
        name, ext = os.path.splitext(filename)
        safe_name = f"{uuid.uuid4()}{ext}"
        return safe_name
    except Exception as e:
        print(f"안전한 파일명 생성 중 오류: {e}")
        return f"{uuid.uuid4()}.unknown"

def format_phone_number(phone_number):
    """한국 전화번호 형식으로 변환 (+82 형식)"""
    try:
        phone = str(phone_number).strip()
        
        if phone.startswith('+82'):
            return phone
        elif phone.startswith('82'):
            return f'+{phone}'
        elif phone.startswith('010') or phone.startswith('011') or phone.startswith('016') or phone.startswith('017') or phone.startswith('018') or phone.startswith('019'):
            return f'+82{phone[1:]}'
        else:
            return f'+82{phone}'
    except Exception as e:
        print(f"전화번호 포맷팅 중 오류: {e}")
        return phone_number

def send_sms_notification(phone_number, message, booth_id=None, student_id=None):
    """SMS 알림 발송"""
    try:
        supabase = get_supabase()
        solapi_service = get_solapi()
        
        if not solapi_service:
            print(f"📱 [개발모드] SMS 발송: {phone_number} → {message}")
            
            if supabase:
                try:
                    notification_data = {
                        'phone_number': phone_number,
                        'message': message,
                        'status': 'dev_mode',
                        'booth_id': booth_id,
                        'student_id': student_id,
                        'sent_at': datetime.now().isoformat()
                    }
                    supabase.table('notifications').insert(notification_data).execute()
                except Exception as db_error:
                    print(f"개발모드 알림 로그 저장 실패: {db_error}")
            
            return True
        
        formatted_phone = format_phone_number(phone_number)
        
        message_obj = RequestMessage(
            from_=Config.SOLAPI_SENDER_PHONE,
            to=formatted_phone,
            text=message
        )
        
        try:
            response = solapi_service.send(message_obj)
            print(f"✅ SMS 발송 성공: {formatted_phone}")
            
            if supabase:
                try:
                    notification_data = {
                        'phone_number': formatted_phone,
                        'message': message,
                        'status': 'sent',
                        'booth_id': booth_id,
                        'student_id': student_id,
                        'sent_at': datetime.now().isoformat(),
                        'response_data': response
                    }
                    supabase.table('notifications').insert(notification_data).execute()
                except Exception as db_error:
                    print(f"SMS 발송 로그 저장 실패: {db_error}")
            
            return True
            
        except Exception as sms_error:
            print(f"❌ SMS 발송 실패: {sms_error}")
            
            if supabase:
                try:
                    notification_data = {
                        'phone_number': formatted_phone,
                        'message': message,
                        'status': 'failed',
                        'booth_id': booth_id,
                        'student_id': student_id,
                        'sent_at': datetime.now().isoformat(),
                        'error_message': str(sms_error)
                    }
                    supabase.table('notifications').insert(notification_data).execute()
                except Exception as db_error:
                    print(f"SMS 실패 로그 저장 실패: {db_error}")
            
            return False
            
    except Exception as e:
        print(f"SMS 발송 중 예상치 못한 오류: {e}")
        return False

def generate_qr_code(text, booth_name=None):
    """QR 코드 생성"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if booth_name:
            img = create_qr_with_text(img, booth_name)
        
        return img
    except Exception as e:
        print(f"QR 코드 생성 중 오류: {e}")
        return None

def create_qr_with_text(qr_img, booth_name):
    """QR 코드에 텍스트 라벨 추가"""
    try:
        img_width, img_height = qr_img.size
        new_height = img_height + 60
        
        new_img = Image.new('RGB', (img_width, new_height), 'white')
        new_img.paste(qr_img, (0, 0))
        
        draw = ImageDraw.Draw(new_img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        text_width = draw.textlength(booth_name, font=font)
        text_x = (img_width - text_width) // 2
        text_y = img_height + 10
        
        draw.text((text_x, text_y), booth_name, fill='black', font=font)
        
        return new_img
    except Exception as e:
        print(f"QR 코드 텍스트 추가 중 오류: {e}")
        return qr_img

def save_qr_code_file(booth_name, img):
    """QR 코드 파일 저장"""
    try:
        qr_dir = 'static/qr_codes'
        os.makedirs(qr_dir, exist_ok=True)
        
        safe_name = "".join(c for c in booth_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        qr_filename = f"{safe_name}_qr.png"
        qr_path = os.path.join(qr_dir, qr_filename)
        
        img.save(qr_path)
        return qr_path
        
    except Exception as e:
        print(f"QR 코드 파일 저장 중 오류: {e}")
        return None

def generate_certificate_number():
    """순차적 인증서 번호 생성 (대수페-25-XXXX 형식)"""
    try:
        supabase = get_supabase()
        if not supabase:
            return f"대수페-25-{datetime.now().strftime('%m%d%H%M')}"
        
        try:
            result = supabase.table('certificates').select('certificate_number').order('id', desc=True).limit(1).execute()
            
            if result.data:
                last_number = result.data[0]['certificate_number']
                if last_number.startswith('대수페-25-'):
                    try:
                        last_num = int(last_number.split('-')[-1])
                        new_num = last_num + 1
                        return f"대수페-25-{new_num:04d}"
                    except:
                        return f"대수페-25-{datetime.now().strftime('%m%d%H%M')}"
            
            return "대수페-25-0001"
            
        except Exception as db_error:
            print(f"인증서 번호 조회 실패: {db_error}")
            return f"대수페-25-{datetime.now().strftime('%m%d%H%M')}"
            
    except Exception as e:
        print(f"인증서 번호 생성 중 오류: {e}")
        return f"대수페-25-{datetime.now().strftime('%m%d%H%M')}"

def generate_certificate_pdf(student_info, booth_records, cert_id, event_name):
    """PDF 인증서 생성"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        
        story = []
        styles = getSampleStyleSheet()
        
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
            korean_font = 'HeiseiKakuGo-W5'
        except:
            korean_font = 'Helvetica'
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=korean_font
        )
        
        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName=korean_font
        )
        
        center_style = ParagraphStyle(
            'CustomCenter',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName=korean_font
        )
        
        story.append(Paragraph(f"{event_name} 활동 확인증", title_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph(f"확인증 번호: {cert_id}", content_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph(f"학교: {student_info.get('school', '')}", content_style))
        story.append(Paragraph(f"학년: {student_info.get('grade', '')}학년", content_style))
        story.append(Paragraph(f"반: {student_info.get('class', '')}반", content_style))
        story.append(Paragraph(f"번호: {student_info.get('number', '')}번", content_style))
        story.append(Paragraph(f"이름: {student_info.get('name', '')}", content_style))
        story.append(Spacer(1, 20))
        
        booth_names = [record.get('booth_name', '') for record in booth_records]
        story.append(Paragraph(f"체험 부스: {', '.join(booth_names)}", content_style))
        story.append(Paragraph(f"총 체험 부스 수: {len(booth_names)}개", content_style))
        story.append(Spacer(1, 30))
        
        story.append(Paragraph("위 학생은 수학축제 부스 체험 활동을 성실히 이수하였음을 확인합니다.", center_style))
        story.append(Spacer(1, 40))
        
        story.append(Paragraph(f"발급일: {datetime.now().strftime('%Y년 %m월 %d일')}", content_style))
        story.append(Paragraph(f"{event_name} 운영위원회", content_style))
        
        doc.build(story)
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"PDF 인증서 생성 중 오류: {e}")
        return None

def get_event_name():
    """행사명 조회"""
    try:
        supabase = get_supabase()
        if not supabase:
            return "대구수학축제"
        
        result = supabase.table('settings').select('value').eq('key', 'event_name').execute()
        
        if result.data:
            return result.data[0]['value']
        else:
            return "대구수학축제"
            
    except Exception as e:
        print(f"행사명 조회 중 오류: {e}")
        return "대구수학축제"

def set_event_name(event_name):
    """행사명 설정"""
    try:
        supabase = get_supabase()
        if not supabase:
            return False
        
        result = supabase.table('settings').upsert({
            'key': 'event_name',
            'value': event_name,
            'description': '행사명'
        }).execute()
        
        return True
        
    except Exception as e:
        print(f"행사명 설정 중 오류: {e}")
        return False

def create_upload_directory(directory_path):
    """업로드 디렉토리 생성"""
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        print(f"디렉토리 생성 실패: {e}")
        return False

def validate_file_extension(filename, allowed_extensions=None):
    """파일 확장자 검증"""
    if allowed_extensions is None:
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    
    try:
        _, ext = os.path.splitext(filename.lower())
        return ext in allowed_extensions
    except Exception:
        return False