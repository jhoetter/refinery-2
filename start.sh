#!/bin/bash
# refinery-2 dev start: API on :8000, Next.js UI on :3000 -> http://localhost:3000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv
fi
if [ ! -f projects/demo_agnews/data/records.jsonl ]; then
  .venv/bin/python projects/demo_agnews/fetch_data.py 400
fi
export PYTHONPATH=.
[ -f .env ] && set -a && source .env && set +a
export PORT=8000
.venv/bin/python -m uvicorn refinery2.server:app --host 127.0.0.1 --port 8000 &>/tmp/refinery-api.log &
echo $! > /tmp/refinery-api.pid
echo "api on :8000 (pid $(cat /tmp/refinery-api.pid))"
cd web
# same-origin: Next.js proxies /api/* to the backend (no direct browser->API traffic)
unset NEXT_PUBLIC_API_URL
exec npm run dev -- -p 3000
