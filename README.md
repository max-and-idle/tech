# Tech Codebase Indexer

AI-powered codebase indexing and semantic search system using Google ADK and PostgreSQL.

## 🎯 목표
코드베이스를 인덱싱하고 의미 기반 검색을 제공하는 AI 시스템 구현

## 🚀 Quick Start

### 1. 환경 설정
```bash
# uv를 사용한 의존성 설치 및 가상환경 설정
uv sync

# 환경변수 파일 설정
# .env 파일에 GEMINI_API_KEY와 PostgreSQL 설정 추가
```

### 2. API 키 및 데이터베이스 설정
- [Google AI Studio](https://aistudio.google.com/apikey)에서 API 키 발급 후 `.env` 파일에 설정
- PostgreSQL 데이터베이스 연결 정보를 `.env` 파일에 설정 (Supabase 등)

### 3. 서버 실행
```bash
# FastAPI 서버 실행
uv run uvicorn app:app --host 127.0.0.1 --port 8000

# 또는 개발 모드 (자동 리로드)
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## 📁 프로젝트 구조
```
├── codebase/           # 코드베이스 인덱싱 시스템
│   ├── core/          # 핵심 구성요소 (파서, 임베딩, 벡터DB)
│   ├── sources/       # 소스 핸들러 (GitHub, ZIP, 로컬)
│   ├── retrieval/     # 검색 및 컨텍스트 관리
│   └── models.py      # SQLAlchemy 데이터베이스 모델
├── routers/           # FastAPI 라우터
├── models/            # Pydantic 모델
├── dev_agent/         # Google ADK Agent
├── tools/             # 개발 도구
├── app.py             # FastAPI 애플리케이션
├── pyproject.toml     # 프로젝트 설정 및 의존성
└── .env              # 환경 변수
```

## 🔧 주요 기능
- **코드베이스 인덱싱**: 로컬/GitHub/ZIP 파일의 코드를 파싱하고 벡터화
- **의미 기반 검색**: 자연어로 코드 검색 (함수, 클래스, 메서드 등)
- **다국어 지원**: Python, JavaScript, Java, Go, Rust 등
- **PostgreSQL + pgvector**: 확장 가능한 벡터 데이터베이스
- **FastAPI**: RESTful API 인터페이스

## 📋 요구사항
- Python 3.10+
- uv (패키지 관리)
- PostgreSQL with pgvector extension
- Google Gemini API Key

## 🔍 API 사용법

### 코드베이스 인덱싱
```bash
# 로컬 디렉토리
curl -X POST "http://127.0.0.1:8000/api/codebase/index/local" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/code", "name": "my_project"}'

# GitHub 저장소
curl -X POST "http://127.0.0.1:8000/api/codebase/index/github" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/user/repo", "name": "github_project"}'
```

### 코드 검색
```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "calculate area function", "codebase_name": "my_project", "top_k": 5}'
```

### 코드베이스 목록
```bash
curl http://127.0.0.1:8000/api/codebase/list
```

## 📖 API 문서
서버 실행 후 다음 URL에서 대화형 문서를 확인할 수 있습니다:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc