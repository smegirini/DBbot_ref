# KakaoBot Calendar Service

> Windows에서 Ubuntu 24.04 LTS로 마이그레이션된 카카오톡 기반 팀 캘린더 서비스
> **NEW**: Iris WebSocket 기반 실시간 메시지 처리

## 프로젝트 개요

이 프로젝트는 기존 Windows 환경에서 동작하던 KakaoTalk 봇 캘린더 서비스를 Ubuntu 24.04 LTS 환경으로 마이그레이션하고, 현대적인 Python 개발 패턴을 적용하여 재구현한 프로젝트입니다.

### 주요 특징

- **Iris WebSocket Integration**: 실시간 양방향 카카오톡 메시지 처리
- **Event-Driven Architecture**: 이벤트 기반 메시지 핸들링
- **3-Layer Architecture**: Presentation(API) → Service(비즈니스 로직) → Repository(데이터 접근)
- **FastAPI**: 고성능 비동기 웹 프레임워크 (웹 인터페이스 제공)
- **Pydantic v2**: 타입 안전 데이터 검증
- **Async/Await**: 비동기 프로그래밍 패턴
- **Circuit Breaker**: 외부 서비스 장애 격리
- **AI Integration**: YouTube/웹페이지 자동 요약
- **Structured Logging**: JSON 기반 구조화된 로깅
- **Type Hints**: Python 3.12+ 타입 힌트 적용

## 시스템 요구사항

- **OS**: Ubuntu 24.04 LTS
- **Python**: 3.12+
- **Database**: MariaDB 10.11+
- **Memory**: 최소 2GB RAM
- **Disk**: 최소 10GB 여유 공간

## 프로젝트 구조

```
kakaobot/
├── app/                      # 애플리케이션 코드
│   ├── main.py              # FastAPI 엔트리포인트
│   ├── config.py            # 설정 관리 (Pydantic Settings)
│   ├── models/              # Pydantic 모델
│   │   ├── base.py          # 기본 모델
│   │   ├── event.py         # 일정 모델
│   │   ├── user.py          # 사용자 모델
│   │   └── room.py          # 방 모델
│   ├── api/                 # API 라우터
│   │   ├── health.py        # 헬스 체크
│   │   └── events.py        # 일정 API
│   ├── services/            # 비즈니스 로직
│   │   ├── event_service.py # 일정 서비스
│   │   └── ai_service.py    # AI 통합 서비스
│   ├── repositories/        # 데이터 접근 계층
│   │   ├── base.py          # 기본 Repository
│   │   ├── event.py         # 일정 Repository
│   │   ├── user.py          # 사용자 Repository
│   │   └── room.py          # 방 Repository
│   └── utils/               # 유틸리티
│       ├── database.py      # DB 연결 관리
│       ├── logger.py        # 로깅 설정
│       ├── circuit_breaker.py # Circuit Breaker
│       └── exceptions.py    # 커스텀 예외
├── tests/                   # 테스트
│   ├── unit/               # 단위 테스트
│   └── integration/        # 통합 테스트
├── deploy/                  # 배포 설정
│   ├── systemd/            # systemd 서비스 파일
│   ├── cloudflared/        # Cloudflare Tunnel 설정
│   └── nginx/              # Nginx 설정
├── scripts/                 # 관리 스크립트
├── requirements.txt         # 프로덕션 의존성
├── requirements-dev.txt     # 개발 의존성
├── .env.template           # 환경 변수 템플릿
└── README.md               # 이 파일
```

## 설치 및 설정

### 1. 프로젝트 클론

```bash
cd /home/sh/Project/kakaobot
```

### 2. 가상 환경 생성 및 활성화

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
# 프로덕션 의존성
pip install -r requirements.txt

# 개발 의존성 (개발 환경에서만)
pip install -r requirements-dev.txt
```

### 4. 환경 변수 설정

```bash
# .env.template을 .env로 복사
cp .env.template .env

# .env 파일 편집 (데이터베이스, AI API 키 등 설정)
nano .env
```

필수 환경 변수:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` (또는 Gemini/Claude)
- `SECRET_KEY` (32자 이상의 무작위 문자열)

### 5. 데이터베이스 설정

MariaDB 데이터베이스와 사용자를 생성합니다:

```sql
CREATE DATABASE calendar_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'calendar_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON calendar_db.* TO 'calendar_user'@'localhost';
FLUSH PRIVILEGES;
```

## 실행

### 개발 모드

```bash
# Uvicorn 직접 실행 (자동 리로드)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 또는 Python 스크립트로 실행
python -m app.main
```

### 프로덕션 모드

```bash
# Gunicorn + Uvicorn workers
gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000
```

### systemd 서비스로 실행

```bash
# 서비스 파일 복사
sudo cp deploy/systemd/calendar-service.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl enable calendar-service
sudo systemctl start calendar-service

# 상태 확인
sudo systemctl status calendar-service
```

## API 문서

애플리케이션 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 주요 엔드포인트

#### Health Check
```bash
GET /health
```

#### Events (일정 관리)
```bash
# 일정 생성
POST /api/v1/events
Content-Type: application/json
{
  "title": "팀 회의",
  "event_date": "2025-10-25",
  "event_time": "14:00:00",
  "created_by": "user1"
}

# 일정 조회
GET /api/v1/events/{event_id}

# 일정 목록
GET /api/v1/events?page=1&page_size=20

# 다가오는 일정
GET /api/v1/events/upcoming/list?limit=10

# 일정 통계
GET /api/v1/events/statistics/summary
```

## 개발

### 코드 품질 도구

```bash
# Black (코드 포맷팅)
black app/ tests/

# isort (import 정렬)
isort app/ tests/

# Flake8 (린팅)
flake8 app/ tests/

# MyPy (타입 체크)
mypy app/

# 전체 실행
black app/ && isort app/ && flake8 app/ && mypy app/
```

### 테스트

```bash
# 모든 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app --cov-report=html

# 특정 테스트 실행
pytest tests/unit/test_event_service.py
```

## 모니터링

### 로그 확인

```bash
# systemd 서비스 로그
sudo journalctl -u calendar-service -f

# 애플리케이션 로그 (설정된 경우)
tail -f /var/log/kakaobot/app.log
```

### 헬스 체크

```bash
# 헬스 체크
curl http://localhost:8000/health

# 응답 예시
{
  "status": "healthy",
  "timestamp": "2025-10-20T10:30:00",
  "app_name": "KakaoBot Calendar Service",
  "app_env": "production",
  "checks": {
    "database": "ok"
  }
}
```

## 배포

### Cloudflare Tunnel 설정

```bash
# Cloudflare Tunnel 설정
sudo cloudflared tunnel create kakaobot-calendar
sudo cloudflared tunnel route dns kakaobot-calendar calendar.yourdomain.com

# 설정 파일 복사
sudo cp deploy/cloudflared/config.yml /etc/cloudflared/

# 서비스 시작
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 트러블슈팅

### 데이터베이스 연결 실패

1. MariaDB 서비스 확인: `sudo systemctl status mariadb`
2. 연결 정보 확인: `.env` 파일의 `DB_*` 변수들
3. 방화벽 확인: `sudo ufw status`

### 포트 충돌

```bash
# 8000 포트 사용 중인 프로세스 확인
sudo lsof -i :8000

# 프로세스 종료
sudo kill -9 <PID>
```

### AI API 오류

1. API 키 확인: `.env` 파일의 `*_API_KEY` 변수들
2. Circuit Breaker 상태 확인: 로그에서 "circuit_breaker" 검색
3. 폴백 체인 확인: Azure OpenAI → Gemini → Claude 순서

## 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic 공식 문서](https://docs.pydantic.dev/)
- [PRD 문서](../PRD_KakaoTalk_Calendar_Migration.md)
- [CLAUDE.md](../CLAUDE.md)

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

## 기여자

- Migration & Refactoring: Claude Code + User
- Original Windows Implementation: [ref_file/](../ref_file/)
