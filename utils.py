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
from datetime import datetime
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

# SOLAPI SMS 관련 변수들 (app.py에서 가져올 예정)
SOLAPI_AVAILABLE = False
solapi_service = None
SOLAPI_SENDER_PHONE = ""

def init_sms_service(available, service, sender_phone):
    """SMS 서비스 초기화 - app.py에서 호출"""
    global SOLAPI_AVAILABLE, solapi_service, SOLAPI_SENDER_PHONE
    SOLAPI_AVAILABLE = available
    solapi_service = service
    SOLAPI_SENDER_PHONE = sender_phone

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

def generate_certificate_number(supabase=None):
    """대수페-25-0001 형식의 순차 인증서 번호 생성"""
    if not supabase:
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

def format_phone_number(phone_number):
    """전화번호를 한국 형식으로 포맷팅"""
    # 전화번호 형식 정리 (하이픈 제거, 국가번호 처리)
    clean_phone = phone_number.replace('-', '').replace(' ', '')
    if clean_phone.startswith('010'):
        clean_phone = '+82' + clean_phone[1:]  # 010 -> +8210
    elif not clean_phone.startswith('+82'):
        clean_phone = '+82' + clean_phone
    return clean_phone

def send_sms_notification(phone_number, message, booth_id=None, student_id=None, supabase=None):
    """SOLAPI를 사용한 SMS 알림 발송"""
    try:
        if not SOLAPI_AVAILABLE:
            print(f"SMS 발송 (개발 모드 - SOLAPI 비활성화): {phone_number} - {message}")
            return True
        
        # 전화번호 형식 정리
        clean_phone = format_phone_number(phone_number)
        
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
            if supabase and booth_id and student_id:
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

def send_bulk_sms_notification(recipients, message, booth_id=None, supabase=None):
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
            clean_phone = format_phone_number(phone_number)
                
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
            if supabase and booth_id:
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

def generate_safe_filename(original_filename):
    """UUID를 사용하여 안전한 파일명 생성"""
    return f"{uuid.uuid4()}_{original_filename}"

def create_upload_directory(directory_path):
    """업로드 디렉토리 생성"""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)

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

def save_qr_code_file(booth_name, img, supabase=None):
    """생성된 QR 코드를 파일로 저장"""
    try:
        # static/qr_codes 디렉토리가 없으면 생성
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
        if supabase:
            supabase.table('booths').update({
                'qr_file_path': filename
            }).eq('name', booth_name).execute()
            
        return filename
            
    except Exception as e:
        print(f"QR 코드 파일 저장 중 오류: {e}")
        return None

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
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # 부스명이 있으면 텍스트 추가
        if booth_name:
            qr_img = create_qr_with_text(qr_img, booth_name)
        
        return qr_img
    except Exception as e:
        print(f"QR 코드 생성 중 오류: {e}")
        return None

def get_event_name(supabase=None):
    """행사명 가져오기"""
    if not supabase:
        return "대구수학축제"
    
    try:
        result = supabase.table('settings').select('value').eq('key', 'event_name').execute()
        if result.data:
            return result.data[0]['value']
        else:
            return "대구수학축제"
    except:
        return "대구수학축제"

def set_event_name(event_name, supabase=None):
    """행사명 설정"""
    if not supabase:
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

def cleanup_filename(filename):
    """파일명에서 특수문자 제거하여 안전한 파일명 생성"""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).rstrip()

def save_uploaded_file(file, upload_dir, booth_id=None, use_uuid=True):
    """업로드된 파일을 안전하게 저장"""
    try:
        if not file or not file.filename:
            return None
            
        # 업로드 디렉토리 생성
        create_upload_directory(upload_dir)
        
        # 안전한 파일명 생성
        if use_uuid:
            safe_filename = generate_safe_filename(file.filename)
        else:
            filename = secure_filename(file.filename)
            safe_filename = f"booth_{booth_id}_{filename}" if booth_id else filename
        
        file_path = os.path.join(upload_dir, safe_filename)
        
        # 파일 저장
        file.save(file_path)
        
        return file_path
        
    except Exception as e:
        print(f"파일 저장 중 오류: {e}")
        return None

def delete_file_if_exists(file_path):
    """파일이 존재하면 삭제"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"파일 삭제 중 오류: {e}")
    return False

def validate_file_extension(filename, allowed_extensions):
    """파일 확장자 검증"""
    if not filename:
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    """파일 확장자 추출"""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()

def format_file_size(size_bytes):
    """파일 크기를 읽기 쉬운 형태로 포맷팅"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"