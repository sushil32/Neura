# NEURA — FULL SYSTEM CONTEXT
## Real-Time AI Avatar & Video Generation Platform

---

## 1. PRODUCT OVERVIEW

### Name
**NEURA**

### Tagline
**Where AI Comes Alive.**

### Description
NEURA is a real-time AI avatar and video generation platform that enables users to create lifelike digital humans capable of speaking, reacting, and presenting content in real time or via pre-rendered videos.

It supports:
- Live AI avatars (WebRTC)
- Offline video generation
- Local + cloud LLMs
- Custom TTS (no third-party dependency)
- Scalable GPU-based rendering
- PostgreSQL-backed authentication & data
- Agent-driven orchestration

---

## 2. CORE DESIGN PRINCIPLES

- Local-first development
- Production-grade scalability
- Stateless services
- PostgreSQL as system of record
- LLM-agnostic
- No vendor lock-in
- GPU-accelerated
- Works on laptop & cloud
- Same architecture for dev & prod

---

## 3. MODES OF OPERATION

### 🟢 OFFLINE VIDEO MODE
Used for:
- Explainers
- Training videos
- Marketing content

Flow:
```
Prompt → Script → Avatar → Voice → Render → MP4
```

### 🔴 LIVE AVATAR MODE
Used for:
- AI presenters
- Live demos
- Interactive assistants

Flow:
```
User Input → LLM → TTS → Lip Sync → WebRTC Stream
```

Target latency: **< 500ms**

---

## 4. HIGH-LEVEL ARCHITECTURE

```
Frontend (Next.js)
        |
API Gateway (FastAPI)
        |
AI Orchestrator
        |
------------------------------------------------
| LLM | TTS | Avatar | Renderer | WebRTC |
------------------------------------------------
        |
GPU Workers
        |
PostgreSQL | Redis | Object Storage
```

---

## 5. LLM STRATEGY

### Supported LLMs

| Environment | LLM |
|------------|-----|
| Local | LM Studio |
| Production | Gemini |
| Fallback | LM Studio |

### Local LLM Example
```bash
curl http://localhost:1234/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "model": "qwen/qwen3-vl-4b",
    "messages": [
      {"role": "system", "content": "You are NEURA"},
      {"role": "user", "content": "What day is it?"}
    ]
  }'
```

---

## 6. TTS SYSTEM (CUSTOM)

- Coqui XTTS
- HiFi-GAN
- Whisper alignment
- WebSocket streaming

---

## 7. DATABASE (POSTGRESQL)

### USERS
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE,
  password_hash TEXT,
  plan TEXT,
  credits INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### VIDEOS
```sql
CREATE TABLE videos (
  id UUID PRIMARY KEY,
  user_id UUID,
  type TEXT,
  status TEXT,
  video_url TEXT,
  created_at TIMESTAMP
);
```

---

## 8. LOCAL DEVELOPMENT

- Docker
- Docker Compose
- PostgreSQL
- Redis
- Python 3.10+
- Node.js 18+

---

## 9. DOCKER COMPOSE

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: neura
      POSTGRES_USER: neura
      POSTGRES_PASSWORD: neura
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env.local

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
```

---

## 10. ENV CONFIG

```env
ENV=local
POSTGRES_DB=neura
POSTGRES_USER=neura
POSTGRES_PASSWORD=neura
REDIS_URL=redis://localhost:6379
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
TTS_PROVIDER=neura
```

---

## 11. PERFORMANCE TARGETS

| Metric | Target |
|------|------|
| Live latency | < 500ms |
| Render time | < 3 min |
| Uptime | 99.9% |

---

## 12. FINAL NOTE

NEURA is designed to scale from a laptop to millions of users without architectural change.

