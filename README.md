# refinery-2

Slim LLM-first rethink of refinery: label data with strong models, combine sources, review only disagreements, distill into small cheap models.

Second attempt, deliberately boring architecture: one Python service, SQLite, parquet/JSONL, git-versioned project folders.

## Quickstart

```bash
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
python projects/demo_agnews/fetch_data.py 400
python scripts/sync_demo.py
python -m refinery2.server_boot   # serves UI + API on :3000
```

Then open http://localhost:3000.

(Offline note: `fetch_data.py` falls back to a synthetic sample when
HuggingFace is unreachable, so the demo always boots.)

## Concept

- `projects/<name>/` is as-code and git-versioned: `refinery.yaml`, `tasks/*.yaml`, `slices.yaml`, `sources/*.py`, `golden/golden.jsonl`.
- Same records, multiple tasks: `topic` (classification), `entities` (spans/NER), `brief` (extraction).
- Sources: `heuristic` (regex), `mock-llm` (expensive teacher stand-in; swap for `LLM_BASE_URL` endpoint), `jev-fast` (cheap typed decisions with calibrated probs).
- Aggregation: confidence-weighted vote; quality measured per source vs golden set.
- Review UI: only disagreements / low confidence. Human labels become golden ground truth.
- Distill: Naive-Bayes student (stdlib-only) on aggregated labels, eval overall + per slice (`POST /api/distill`).

## API

- `GET /api/project`, `GET /api/records?task=topic`, `GET /api/record/{id}?task=topic`
- `POST /api/labels` {record_id, task, label} — human golden label
- `POST /api/run-sources` {limit} — run heuristic/mock-llm/jev-fast + aggregate
- `GET /api/quality?task=topic` — per-source accuracy vs golden
- `GET /api/queue?task=topic` — disagreement/low-conf review queue
- `POST /api/distill` {task, train_on} — train student, slice eval
