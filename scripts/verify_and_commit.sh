#!/usr/bin/env bash
# Engineering Agent — one-shot verification + commit + push.
# Run: bash ~/jarvis/scripts/verify_and_commit.sh
set -euo pipefail

cd ~/jarvis/backend
source ../.venv/bin/activate
echo "== backend tests =="
pytest -q

cd ~/jarvis/frontend
echo "== lint ==";  npm run lint
echo "== typecheck ==";  npm run typecheck
echo "== build ==";  npm run build

cd ~/jarvis
echo "== secrets check =="
git ls-files | grep -iE '\.env$|\.pem$|\.key$|id_rsa' && { echo "SECRET TRACKED — ABORT"; exit 1; } || echo "no secrets tracked"
git status --short

echo "== commit & push =="
git add -A
git commit -m "feat(agent): upgrade coding worker into advanced engineering agent"
git push origin main
git log --oneline -1
