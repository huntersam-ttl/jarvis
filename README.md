# JARVIS

A clean personal AI control system. Jarvis is a foundation for an extensible
personal operating system that will later control autonomous trading, coding,
research, projects, world intelligence, and other automation.

This repository contains **Jarvis v0** — the foundation: a FastAPI backend with
an OmniRoute provider integration, a model router, and a polished Next.js
"Control Room" frontend.

---

## What Jarvis is

Jarvis is a personal AI control centre, not a generic admin dashboard. Normal
interaction happens through a polished Control Room UI. Technical logs and
debugging information live underneath, behind an Advanced/Developer view.

## Architecture

```
User
  ↓
Jarvis Control Room  (Next.js + TypeScript + Tailwind)
  ↓
Jarvis Backend      (FastAPI + Pydantic)
  ↓
Provider Layer      (generic provider abstraction)
  ↓
OmniRoute           (local Docker gateway, OpenAI-compatible)
  ↓
AI models
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

## Repository layout

```
jarvis/
├── backend/        FastAPI backend (app/, tests/, requirements.txt)
├── frontend/       Next.js Control Room (app/, components/, lib/, types/)
├── docs/           ARCHITECTURE, ROADMAP, SECURITY
├── .env.example    Environment template (copy to .env)
├── .gitignore
├── README.md
└── AGENTS.md
```

## Requirements

- Python 3.9+
- Node.js 18+ (developed on Node 22)
- OmniRoute running locally via Docker at `http://127.0.0.1:20128/v1`

## Install

### 1. Configure environment

```bash
cd jarvis
cp .env.example .env
# Edit .env and set OMNIROUTE_API_KEY to your real OmniRoute key
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
```

## Configure OmniRoute

OmniRoute is an OpenAI-compatible gateway running locally through Docker.

In `.env`:

```
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_API_KEY=<your real key>
OMNIROUTE_DEFAULT_MODEL=auto/glm
```

The API key is read only from `.env`, never printed, never logged, and never
exposed to the frontend.

## Run

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

Open <http://localhost:3000>.

## Run tests

### Backend

```bash
cd backend
source .venv/bin/activate
pytest -v
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
```

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Security

See [`docs/SECURITY.md`](docs/SECURITY.md). Never commit `.env`. The API key is
treated as a secret at all times.
