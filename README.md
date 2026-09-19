# refinery-2

Slim LLM-first rethink of refinery: label data with strong models, match them
with small local students, serve the student via API. Agentic by design (MCP).

One Python service (API :8000), one Next.js UI (:3000), one MCP stdio server.

## Quickstart

```bash
./start.sh   # API on :8000, UI on http://localhost:3000
```

Manual:

```bash
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
python projects/demo_agnews/fetch_data.py 400
python scripts/sync_demo.py
PORT=8000 PYTHONPATH=. python -m uvicorn refinery2.server:app --host 127.0.0.1 --port 8000
cd web && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev -- -p 3000
```

(Offline note: `fetch_data.py` falls back to a synthetic sample when
HuggingFace is unreachable, so the demo always boots.)

## MCP (agentic)

```bash
REFINERY_PROJECT=projects/demo_agnews PYTHONPATH=. .venv/bin/python -m refinery2.mcp_server
```

Tools: `project_status`, `list_templates`, `create_task` (gallery template or
vibecoded inline TaskDef → versioned YAML), `label_with_model`, `train_student`,
`benchmark`, `predict`. Typical agent loop: template → teacher labels → review
queue → student → benchmark → serve.

## Concept

- `projects/<name>/` is as-code and git-versioned: `refinery.yaml`, `tasks/*.yaml`, `slices.yaml`, `golden/golden.jsonl`, `models/models.yaml`.
- Same records, multiple tasks: classification, spans/NER, extraction – incl. complex bundles (see `refinery2/templates/`, e.g. `support-ticket-bundle`).
- Teachers: `heuristic`, `mock-llm`, `jev-fast` built in; any OpenAI-compatible endpoint registrable (`POST /api/models/api`, key via env).
- Students: tiny local models distilled from confident teacher consensus + golden (`POST /api/models/train`, artifacts in `models/`).
- Benchmark: teacher vs student on golden holdout – accuracy/F1 + latency (`POST /api/models/benchmark`).
- Serve: `POST /api/predict {model, task, text}`.
- Weak supervision stays a simple confidence-weighted vote; no further investment – LLMs are usually right, the game is matching them cheaply.

## API (selection)

- `GET /api/project`, `GET /api/records?task=topic`, `GET /api/record/{id}?task=topic`
- `POST /api/labels` {record_id, task, label} — human golden label
- `GET /api/templates`, `POST /api/tasks/from-template`, `POST /api/tasks` (vibecode)
- `GET /api/models`, `POST /api/models/api`, `POST /api/models/train`
- `POST /api/models/benchmark`, `POST /api/predict`, `POST /api/run-teacher`
- `GET /api/quality?task=topic`, `GET /api/queue?task=topic`, `POST /api/distill`
