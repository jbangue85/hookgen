# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AdClip AI** — automated AI video editor that takes a voiceover audio + B-roll clips and produces a 9:16 short-form video (TikTok/Reels/Shorts). The pipeline uses Whisper for transcription, GPT-4o-mini for AIDA phase analysis, Gemini 2.5 Flash for video analysis, and cosine similarity for clip matching.

## Services & Ports

| Service      | Port | Notes                              |
|-------------|------|------------------------------------|
| Frontend    | 3000 | Next.js                            |
| Backend     | 8000 | FastAPI + WebSocket                |
| PostgreSQL  | 5432 | `adclip_db`                        |
| Redis       | 6379 | Celery broker + cache              |

## Commands

### Full stack (recommended)
```bash
docker-compose up --build
```

### Frontend only
```bash
cd frontend
npm run dev       # dev server
npm run build     # production build
npm run lint      # ESLint
```

### Backend only
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload            # API server (port 8000)

# In a separate terminal:
celery -A worker.tasks.celery_app worker --loglevel=info
```

### Database migrations
```bash
cd backend
alembic upgrade head
```

## Architecture

### Processing Pipeline (Celery task chain)

```
1. transcribe_audio_task
   Whisper → word-level timestamps, tone, keywords, speech rhythm

2. analyze_video_task (per video, parallel)
   Gemini 2.5 Flash → segments with descriptions, mood, keywords, ad_role

3. match_clips_task
   GPT-4o-mini → break transcript into AIDA phases (Attention→Interest→Desire→Action)
   text-embedding-3-small → cosine similarity matching of AIDA phases to video segments
   Rules: product visibility constraints, reuse penalties, cascading

4. export_video_task
   FFmpeg → cut/crop/scale to 9:16, concatenate, mux audio
```

### Project Status Flow
`created → transcribing → analyzing → matching → exporting → completed | failed`

Two modes: **AUTO** (export immediately after matching) and **REVIEW** (user approves clips before export).

### Key Backend Files
- `backend/api/routes.py` — all REST endpoints + multipart upload handling
- `backend/services/ai_services.py` — Whisper, GPT-4o-mini, Gemini wrappers; AIDA analysis
- `backend/services/matching.py` — `select_best_clips()` core algorithm
- `backend/services/ffmpeg_utils.py` — FFmpeg subprocess wrappers
- `backend/worker/tasks.py` — Celery task definitions and chain orchestration
- `backend/db/models.py` — SQLAlchemy models: `Project`, `VideoFile`, `SegmentAnalysis`, `SelectedClip`, `AudioKeyword`

### Key Frontend Files
- `frontend/src/app/page.tsx` — upload form (audio, videos, optional product image, mode)
- `frontend/src/app/layout.tsx` — root layout
- Uses Framer Motion for animations, TailwindCSS 4, lucide-react icons

### WebSocket
Real-time progress: `/ws/project/{project_id}`. Internal broadcast endpoint: `POST /api/internal/ws_broadcast`.

## Next.js Version Note

This uses a recent Next.js version that may have breaking changes from older training data. Read `frontend/node_modules/next/dist/docs/` before writing frontend code. Heed deprecation notices.

## Required Environment Variables
Set in `.env` at repo root (used by docker-compose):
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `DATABASE_URL`
- `REDIS_URL`
