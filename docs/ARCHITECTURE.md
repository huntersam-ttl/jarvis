# Architecture

Jarvis is a personal AI control system. This document describes the v0
foundation architecture.

## High-level flow

```
User
  ↓
Jarvis Control Room   (Next.js + TypeScript + Tailwind)
  ↓  (REST)
Jarvis Backend       (FastAPI + Pydantic)
  ↓
Provider Layer       (generic Provider abstraction)
  ↓
OpenRouter            (local Docker gateway, OpenAI-compatible)
  ↓
AI models
```

## Backend (`backend/app/`)

```
app/
├── main.py            FastAPI app, CORS, router wiring, lifespan
├── config.py         Settings via pydantic-settings + python-dotenv
├── api/              HTTP route layer (system, providers, chat)
├── core/             Cross-cutting: logging, timing, exceptions
├── providers/        Provider abstraction + OpenRouter implementation
├── services/         Use-case orchestration (chat service, model router)
└── models/           Pydantic schemas (request/response DTOs)
```

### Layers

- **API layer** (`api/`): thin HTTP handlers. Validate input, call a service,
  return normalized DTOs. No business logic, no raw provider JSON leaked.
- **Services** (`services/`): orchestration. The `ChatService` resolves the
  provider/model via the `ModelRouter`, calls the provider, records run
  metadata, and returns a normalized response.
- **Providers** (`providers/`): a generic `Provider` interface plus the
  `OpenRouterProvider` implementation. New OpenAI-compatible providers are
  added by implementing the interface — Jarvis core does not change.
- **Models** (`models/`): Pydantic schemas for API contracts and internal
  normalized structures.
- **Core** (`core/`): logging, timing, and shared exceptions.

### Model router (v0)

v0 is intentionally simple:

- Default provider: OpenRouter.
- Default model: from environment (`OPENROUTER_DEFAULT_MODEL`).
- Each request records: requested model, provider, duration, success/failure.

Later phases will add cost-aware routing, quality routing, and task-specific
model selection — without changing the provider interface.

## Frontend (`frontend/`)

Next.js App Router with TypeScript and Tailwind CSS.

```
app/                 Routes (Home, Jarvis, Tasks, Trading, Projects, Memory, Providers, System)
components/          Reusable UI (cards, status indicators, chat, layout)
lib/                 API client + helpers
types/               Shared TypeScript types mirroring backend DTOs
```

The UI is a polished dark "Control Room". Technical logs are behind an
Advanced/Developer view; normal interaction stays clean.

## Communication

- REST for v0.
- Code is structured so SSE/WebSockets can be added later for streaming chat
  and live task updates.

## Security boundaries

- The API key lives only in backend `.env`. It is never sent to the frontend.
- The Providers screen shows "Configured / Missing" — never the secret.
- CORS is restricted to configured origins (`JARVIS_CORS_ORIGINS`).

## Trading Bridge (Phase 2 entry point)

Jarvis wraps an existing, separately developed trading agent. Jarvis does not
contain trading intelligence — it is the control and monitoring layer.

- `app/trading/base.py` — generic `TradingAdapter` interface
- `app/trading/mock.py` — in-memory mock adapter for development
- `app/trading/http_adapter.py` — HTTP adapter for the real agent
  (`TRADING_AGENT_BASE_URL` + `TRADING_AGENT_API_KEY`, env-only)
- `app/trading/service.py` — adapter selection + normalized failures
- `app/api/trading.py` — `/api/trading/{status,positions,activity,performance}`
  and `POST /api/trading/{start,pause,resume,stop}`

The HTTP adapter expects the trading agent to expose normalized JSON at
`/status`, `/positions`, `/activity`, `/performance` and `/commands/{cmd}`.
Only `http_adapter.py` needs to change if the real agent's API differs.
