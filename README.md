# AdClip AI

Automated Ad Video Editor powered by FastAPI, Next.js, OpenAI Whisper, and Claude Vision.

## Tech Stack
- **Backend:** Python 3.11+, FastAPI, Celery, Redis, FFmpeg
- **AI:** OpenAI Whisper (Audio), OpenAI GPT-4o (Vision logic)
- **Frontend:** Next.js 14, React, Tailwind CSS
- **Database:** PostgreSQL (production), SQLite (local dev fallback)
- **Infrastructure:** Docker & Docker Compose

## Prerequisites
1. **Docker & Docker Compose** installed.
2. **FFmpeg** installed locally (if running outside Docker):
   - **Mac:** `brew install ffmpeg`
   - **Ubuntu/Debian:** `sudo apt install ffmpeg`
   - **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or use `winget install ffmpeg`.
3. API Key for **OpenAI**.

## Setup Instructions

1. **Clone the repository.**
2. **Setup environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```
3. **Run with Docker Compose (Recommended):**
   ```bash
   docker-compose up --build
   ```
   This will spin up:
   - PostgreSQL Database on port `5432`
   - Redis on port `6379`
   - FastAPI Backend on `http://localhost:8000`
   - Celery Worker
   - Next.js Frontend on `http://localhost:3000`

## Local Development (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
You will also need to run a local Redis server and Celery worker:
```bash
celery -A worker.tasks.celery_app worker --loglevel=info
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Directory Structure
- `/backend`: FastAPI, Celery tasks, AI service integrations, FFmpeg utilities.
- `/frontend`: Next.js 14 Web App, UI components, WebSocket clients.
