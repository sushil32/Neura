# NEURA — Where AI Comes Alive

Real-Time AI Avatar & Video Generation Platform

## Overview

NEURA is a production-grade platform for creating AI-powered videos and real-time avatar presentations. It supports:

- **Offline Video Generation**: Create high-quality AI presenter videos
- **Live Avatar Streaming**: Real-time WebRTC streaming with < 500ms latency
- **Custom TTS**: Voice synthesis with word-level timing for lip sync
- **LLM Integration**: Local (LM Studio) and cloud (Gemini) support

## Architecture

```
Frontend (Next.js 14)
        │
API Gateway (FastAPI)
        │
AI Orchestrator
        │
┌───────┼───────┬───────┬───────┬───────┐
│  LLM  │  TTS  │Avatar │Render │WebRTC │
└───────┴───────┴───────┴───────┴───────┘
        │
GPU Workers (Celery)
        │
PostgreSQL │ Redis │ MinIO
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- LM Studio (optional, for local LLM)

### Development Setup

1. **Clone and setup environment**

```bash
cd Neura
cp .env.example .env.local
```

2. **Start infrastructure**

```bash
docker compose up -d postgres redis minio
```

3. **Run database migrations**

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
```

4. **Start backend**

```bash
uvicorn app.main:app --reload --port 8000
```

5. **Start frontend**

```bash
cd frontend
npm install
npm run dev
```

6. **Access the application**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Full Docker Development

```bash
docker compose up --build
```

## Project Structure

```
neura/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py       # Application entry
│   │   ├── config.py     # Configuration
│   │   ├── database.py   # Database connection
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── routers/      # API routes
│   │   ├── services/     # Business logic
│   │   ├── workers/      # Celery tasks
│   │   └── utils/        # Utilities
│   ├── alembic/          # DB migrations
│   └── requirements.txt
│
├── frontend/             # Next.js frontend
│   ├── src/
│   │   ├── app/         # App router pages
│   │   ├── components/  # React components
│   │   └── lib/         # Utilities & API
│   └── package.json
│
├── services/            # AI services
│   ├── llm/            # LLM providers
│   ├── tts/            # Text-to-speech
│   ├── avatar/         # Avatar rendering
│   └── webrtc/         # Live streaming
│
├── docker-compose.yml   # Development
└── docker-compose.prod.yml  # Production
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - Logout

### Videos
- `GET /api/v1/videos` - List videos
- `POST /api/v1/videos` - Create video
- `GET /api/v1/videos/{id}` - Get video
- `PATCH /api/v1/videos/{id}` - Update video
- `POST /api/v1/videos/{id}/generate` - Start generation

### Avatars
- `GET /api/v1/avatars` - List avatars
- `POST /api/v1/avatars` - Create avatar
- `PATCH /api/v1/avatars/{id}` - Update avatar

### Live
- `POST /api/v1/live/start` - Start live session
- `POST /api/v1/live/{session_id}/stop` - Stop session
- `WS /api/v1/live/ws/{session_id}` - WebSocket stream

### LLM
- `POST /api/v1/llm/chat` - Chat completion
- `POST /api/v1/llm/script/generate` - Generate script

## Configuration

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/neura

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
GEMINI_API_KEY=your-api-key

# S3
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Live latency | < 500ms |
| Video render time | < 3 min per minute |
| API response time | < 200ms |
| Uptime | 99.9% |

## Tech Stack

- **Frontend**: Next.js 14, React, TailwindCSS, Zustand
- **Backend**: FastAPI, SQLAlchemy, Celery
- **Database**: PostgreSQL, Redis
- **AI/ML**: Coqui XTTS, Whisper, Custom avatar models
- **Infrastructure**: Docker, Traefik, MinIO

## License

Proprietary - All rights reserved

---

Built with ❤️ by the NEURA team

