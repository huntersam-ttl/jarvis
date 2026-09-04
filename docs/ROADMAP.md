# Roadmap

Jarvis is built in phases. Each phase expands capability without breaking the
foundation.

## Phase 1 — Jarvis Core ✅ (this release)

- FastAPI backend with clean layering (api / services / providers / models / core)
- Generic provider abstraction
- OpenRouter provider integration (health, models, chat, model info)
- Model router v0 (default provider + default model, run metadata)
- Control Room UI: Home, Jarvis chat, Tasks, Trading, Projects, Memory, Providers, System
- Configuration via `.env`, health monitoring, permission foundation
- Git/GitHub backup workflow
- Tests (pytest) + frontend lint/typecheck

## Phase 2 — Trading Engine

- TradingAgents integration
- Strategy management and backtesting
- Risk controls and position limits
- Paper trading first; live connections only after explicit approval

## Phase 3 — Memory + Coding Worker

- Persistent memory store (conversations, context, decisions)
- Coding worker: repo-aware code generation and execution
- Task/run history and replay

## Phase 4 — World Intelligence

- God's Eye: news, market, and signal aggregation
- TimesFM-style forecasting hooks
- Research and summarization pipelines

## Phase 5 — Broader Automation

- Schedulers and long-running workflows
- Multi-provider cost-aware and quality-aware model routing
- Plugin/extension system for new capabilities
