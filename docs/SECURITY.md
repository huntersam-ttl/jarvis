# Security

## Secrets

- The OpenRouter API key is stored **only** in `.env` as `OPENROUTER_API_KEY`.
- `.env` is git-ignored (see [`.gitignore`](../.gitignore)).
- `.env.example` contains placeholders only — never real values.
- The key is never hard-coded, printed, logged, or sent to the frontend.
- The Providers screen reports `Configured` / `Missing` — never the secret.

## Pre-commit checklist

Before every commit:

1. Run backend tests (`pytest`).
2. Run frontend lint/typecheck when applicable.
3. `git status` — confirm `.env` is ignored and not staged.
4. Verify no secret/token is staged. If detected, **STOP** and remove it.

You can scan for accidental secrets:

```bash
git diff --cached | grep -iE "api[_-]?key|secret|token|password" || true
```

## CORS

- Allowed origins are configured via `JARVIS_CORS_ORIGINS` (comma-separated).
- In development: `http://localhost:3000,http://127.0.0.1:3000`.
- Do not use wildcard origins in production.

## Provider boundaries

- The backend is the only component that holds credentials and talks to
  providers. The frontend never contacts OpenRouter directly.

## Git / GitHub

- Primary branch: `main`.
- Never force-push. Never delete history.
- The GitHub repository should be **PRIVATE** unless explicitly stated.
- If no remote exists, complete local commits and report the exact command
  needed before pushing.
