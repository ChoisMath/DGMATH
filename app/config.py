import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Supabase 설정
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jjjbhlwcjkaukkqplppm.supabase.co")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqamJobHdjamthdWtrcXBscHBtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDczMTkwNjQsImV4cCI6MjA2Mjg5NTA2NH0.3WJqsIG-F2pZ0nZE2j0NPnLTCPd37FEgYPD_F_1aw2M")
    
    # SOLAPI 설정
    SOLAPI_API_KEY = os.environ.get("SOLAPI_API_KEY")
    SOLAPI_API_SECRET = os.environ.get("SOLAPI_API_SECRET") 
    SOLAPI_SENDER_PHONE = os.environ.get("SOLAPI_SENDER_PHONE")
    
    # 파일 업로드 설정
    UPLOAD_FOLDER = 'static/uploads/booth_pdfs'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # 관리자 비밀번호
    ADMIN_PASSWORD = 'admin'