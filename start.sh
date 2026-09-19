#!/bin/bash
# refinery-2 dev start: http://localhost:3000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv
fi
if [ ! -f projects/demo_agnews/data/records.jsonl ]; then
  .venv/bin/python projects/demo_agnews/fetch_data.py 400
fi
export PYTHONPATH=.
exec .venv/bin/python -m uvicorn refinery2.server:app --host 127.0.0.1 --port 3000
