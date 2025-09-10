# Google ADK Development Agent

Google ADK(Agent Development Kit)를 활용한 개발 계획 수립 AI Agent

## 🎯 목표
Google ADK를 이용해 간단한 AI Agent를 구현하고 실행 확인하기

## 🚀 Quick Start

### 1. 환경 설정
```bash
# 가상환경 활성화
source .venv/bin/activate

# 환경변수 파일 생성
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 설정
```

### 2. API 키 설정
[Google AI Studio](https://aistudio.google.com/apikey)에서 API 키 발급 후 `.env` 파일에 설정

### 3. Agent 실행
```bash
# Web UI로 실행
adk web

# 또는 CLI 모드로 실행  
adk run dev_agent
```

## 📁 프로젝트 구조
```
├── dev_agent/          # 메인 Agent 구현
│   ├── __init__.py
│   └── agent.py
├── tools/              # 개발 도구 함수들
│   ├── __init__.py
│   └── dev_tools.py
├── examples/           # 사용 예제
│   └── demo.py
├── tests/              # 테스트 코드
│   └── test_agent.py
├── .env.example        # 환경변수 템플릿
├── requirements.txt    # Python 의존성
└── README.md
```

## 🔧 주요 기능
- 프로젝트 요구사항 분석
- 기술 스택 추천
- 개발 계획 수립
- 프로젝트 구조 제안

## 📋 요구사항
- Python 3.10+
- Google ADK v1.13.0+
- Gemini API Key