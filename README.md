# 축제 부스 체크인 & 확인증 발급 웹앱 (Python Flask + Supabase)

## 🟢 주요 기능
- 학생 정보 입력/저장 (LocalStorage)
- 부스별 QR 체크인(소감 입력)
- 3개 이상 체크인 시 확인증 발급(고유번호)
- 관리자: 전체 기록 Excel 다운로드 (비번: admin)
- 네온 컬러 포인트 디자인

---

## 1️⃣ 설치 및 준비

### 1. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. Supabase 프로젝트 설정
1. [Supabase](https://supabase.com/) 접속 → 새 프로젝트 생성
2. Database → SQL Editor에서 다음 테이블 생성:
```sql
CREATE TABLE checkins (
    id SERIAL PRIMARY KEY,
    school TEXT NOT NULL,
    grade INTEGER NOT NULL,
    class INTEGER NOT NULL,
    number INTEGER NOT NULL,
    name TEXT NOT NULL,
    booth TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
3. Settings → API에서 Project URL과 anon public key 확인
4. app.py 파일의 SUPABASE_URL과 SUPABASE_KEY 값 업데이트

### 3. 실행
```bash
python app.py
```

---

## 2️⃣ 주요 페이지 안내
- `/student_info` : 학생 정보 입력/저장
- `/checkin?booth=부스명` : 부스 체크인(QR URL)
- `/certificate` : 확인증 발급
- `/admin` : 관리자(비번: admin, 기록 다운로드)

---

## 3️⃣ QR코드 생성법
- 각 부스별 URL 예시:  
  `http://[서버주소]/checkin?booth=VR체험관`
- [qr코드 생성기](https://www.qr-code-generator.com/) 등에서 위 URL로 QR 생성 후 출력

---

## 4️⃣ 기타
- 네온 컬러 포인트 디자인 적용
- 문의: (여기에 연락처/이메일 등) 