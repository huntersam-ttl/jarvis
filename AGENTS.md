# AGENTS.md

Operating notes for AI agents (and humans) working on Jarvis.

## Workspace

- Work **only** inside `~/jarvis` (`/Users/cc/jarvis`).
- Do not modify other repositories or directories.

## Secrets

- The OpenRouter API key is read **only** from `.env` via `OPENROUTER_API_KEY`.
- Never hard-code, print, log, or expose the key to the frontend.
- `.env` is git-ignored. `.env.example` contains placeholders only.
- Before every commit, verify no secret is staged. If a secret is detected,
  STOP and remove it before committing.

## Architecture rules

- Keep the provider layer generic. New OpenAI-compatible providers
  (OpenAI, DeepSeek, MiniMax, Anthropic, etc.) must be addable without
  rewriting Jarvis — implement the `Provider` interface.
- Do not expose raw provider JSON to the frontend. Normalize responses.
- Structure backend code so SSE/WebSockets can be added later (REST first).
- Do not over-engineer. Do not add random open-source repositories.
- Do not build a giant agent framework.

## v0 scope (do NOT build yet)

- TradingAgents
- God's Eye
- TimesFM
- Real trading account connections

## Git

- Primary branch: `main`.
- Meaningful milestone commits. Never force-push. Never delete history.
- If no GitHub remote exists, complete local commits and report the exact
  command needed; wait before pushing. The repo should be PRIVATE unless
  explicitly stated otherwise.

## Completion criteria

Do not claim completion until: backend starts, frontend starts, `/health`
works, OpenRouter connection works, models endpoint works, Jarvis chat works,
UI sends a message and displays a response, tests pass, secrets are not
tracked, and work is committed locally. Do not fake results.
