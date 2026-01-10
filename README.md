# NEURA — Where AI Comes Alive

Real-Time AI Avatar & Video Generation Platform

## Overview

NEURA is a production-grade platform for creating AI-powered videos and real-time avatar presentations. It supports:

- **Offline Video Generation**: Create high-quality AI presenter videos
- **Live Avatar Streaming**: Real-time WebRTC streaming with < 500ms latency
- **Custom TTS**: Coqui XTTS v2 voice synthesis with word-level timing for lip sync
- **Voice Profiles**: Pre-configured voices (Alex, Sarah, James, Emma, David)
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
│  LLM  │  TTS  │Avatar │Render │ Live  │
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
- Deepgram API Key (optional, for live STT)
- Gemini API Key (optional, for cloud LLM)

### Development Setup (Docker)

1. **Clone and setup environment**

```bash
cd Neura
cp .env.example .env.local
```

2. **Configure API Keys** (optional for live features)

```bash
# Edit .env.local and add:
DEEPGRAM_API_KEY=your-deepgram-key
GEMINI_API_KEY=your-gemini-key
```

3. **Start all services**

```bash
docker compose up -d
```

4. **Seed default data** (voices and avatars)

```bash
docker exec neura-backend python seed_defaults.py
```

5. **Access the application**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Next.js dashboard |
| Backend | 8000 | FastAPI gateway |
| TTS | 8001 | Coqui XTTS synthesis |
| Live | 8003 | WebRTC streaming |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache & queues |
| MinIO | 9000 | Object storage |

## Features

### 🎙️ Voice Profiles

Pre-configured voices for immediate use:

| Voice | Gender | Style | Best For |
|-------|--------|-------|----------|
| Alex | Male | Conversational | Business presentations |
| Sarah | Female | Friendly | Tutorials |
| James | Male | Authoritative | Documentaries |
| Emma | Female | Energetic | Marketing |
| David | Male | Calm | Wellness content |

Preview voices at `/voices` or via API:
```bash
GET /api/v1/tts/voices/{id}/preview
```

### 🎥 Live Avatar

Real-time AI conversation via WebRTC:

1. Go to `/live`
2. Select an avatar and voice
3. Click "Go Live"
4. Speak into microphone
5. AI responds with synthesized voice

**Pipeline**: Audio → STT (Deepgram) → LLM (Gemini) → TTS → WebRTC Stream

### 📹 Video Generation

Create pre-rendered AI presenter videos:

1. Go to `/studio`
2. Write or generate a script
3. Select avatar and voice
4. Configure settings
5. Generate video

## Project Structure

```
neura/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── routers/      # API routes
│   │   ├── models/       # SQLAlchemy models
│   │   └── workers/      # Celery tasks
│   └── seed_defaults.py  # Default data seeder
│
├── frontend/             # Next.js frontend
│   └── src/
│       ├── app/(dashboard)/  # Protected pages
│       ├── hooks/useWebRTC.ts # WebRTC logic
│       └── lib/api.ts    # API client
│
├── services/
│   ├── live/            # WebRTC live service
│   │   ├── main.py      # WebRTC offer/answer
│   │   ├── pipeline.py  # STT→LLM→TTS pipeline
│   │   └── stream_track.py # TTS audio streaming
│   ├── tts/             # Coqui XTTS synthesis
│   └── avatar/          # Wav2Lip rendering
│
└── docker-compose.yml
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token

### Videos
- `GET /api/v1/videos` - List videos
- `POST /api/v1/videos` - Create video
- `POST /api/v1/videos/{id}/generate` - Generate

### Avatars
- `GET /api/v1/avatars` - List avatars
- `POST /api/v1/avatars` - Create avatar

### Voices
- `GET /api/v1/tts/voices` - List voices
- `GET /api/v1/tts/voices/{id}/preview` - Preview voice
- `POST /api/v1/tts/generate` - Generate TTS

### Live
- `POST /api/v1/live/start` - Start session
- `POST /api/v1/live/{session_id}/stop` - Stop session
- `WS /api/v1/live/ws/{session_id}` - WebSocket for signaling

## Configuration

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://neura:neura@postgres:5432/neura

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key

# LLM (choose one)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
# OR
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1

# Live AI Features
DEEPGRAM_API_KEY=your-deepgram-key

# S3 Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Live latency | < 500ms |
| Video render | < 3 min/min |
| API response | < 200ms |
| Uptime | 99.9% |

## Tech Stack

- **Frontend**: Next.js 14, React, TailwindCSS, Zustand
- **Backend**: FastAPI, SQLAlchemy, Celery
- **Database**: PostgreSQL, Redis
- **AI/ML**: Coqui XTTS v2, Deepgram STT, Gemini LLM
- **Streaming**: aiortc (WebRTC), MediaRecorder
- **Infrastructure**: Docker, MinIO

## Troubleshooting

### TTS produces beep sounds
The XTTS model (1.87GB) may not have downloaded. Check:
```bash
docker logs neura-tts | grep -i "xtts\|error"
```

### WebRTC connection fails
The live-service uses host networking. Ensure port 8003 is free:
```bash
lsof -i :8003
```

### Logout on page refresh
Clear browser localStorage and re-login:
```javascript
localStorage.clear()
```

## License

Proprietary - All rights reserved

---

Built with ❤️ by the NEURA team
