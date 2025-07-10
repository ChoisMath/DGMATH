from supabase import create_client, Client
from app.config import Config
import base64
import hashlib

# 전역 변수들
supabase: Client = None
SUPABASE_AVAILABLE = False
SOLAPI_AVAILABLE = False
solapi_service = None

def init_supabase():
    """Supabase 클라이언트 초기화"""
    global supabase, SUPABASE_AVAILABLE
    
    try:
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        SUPABASE_AVAILABLE = True
        print("Supabase 연결 성공!")
    except Exception as e:
        print(f"Warning: Supabase 연결 실패. {e}")
        SUPABASE_AVAILABLE = False
        supabase = None

def init_solapi():
    """SOLAPI SMS 서비스 초기화"""
    global SOLAPI_AVAILABLE, solapi_service
    
    try:
        from solapi import SolapiMessageService
        print("SOLAPI 모듈 import 성공")
        
        print(f"SOLAPI 환경변수 확인: API_KEY={'설정됨' if Config.SOLAPI_API_KEY else '없음'}, API_SECRET={'설정됨' if Config.SOLAPI_API_SECRET else '없음'}, SENDER_PHONE={'설정됨' if Config.SOLAPI_SENDER_PHONE else '없음'}")
        
        if Config.SOLAPI_API_KEY and Config.SOLAPI_API_SECRET and Config.SOLAPI_SENDER_PHONE:
            try:
                solapi_service = SolapiMessageService(Config.SOLAPI_API_KEY, Config.SOLAPI_API_SECRET)
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
            
    except ImportError:
        print("⚠️ SOLAPI 모듈이 설치되지 않았습니다. pip install solapi-python 으로 설치하세요.")
        SOLAPI_AVAILABLE = False
        solapi_service = None
    except Exception as import_error:
        print(f"⚠️ SOLAPI 초기화 실패: {import_error}")
        SOLAPI_AVAILABLE = False
        solapi_service = None

def get_supabase():
    """Supabase 클라이언트 반환"""
    return supabase

def get_solapi():
    """SOLAPI 서비스 반환"""
    return solapi_service

def encrypt_password(password):
    """비밀번호 암호화 함수"""
    md5_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
    return base64.b64encode(md5_hash.encode('utf-8')).decode('utf-8')

def verify_password(stored_password, provided_password):
    """비밀번호 검증 함수"""
    return stored_password == encrypt_password(provided_password)