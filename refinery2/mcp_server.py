"""MCP server (stdio, stdlib-only JSON-RPC) for agentic labeling loops.

Run:  REFINERY_PROJECT=projects/demo_agnews PYTHONPATH=. .venv/bin/python -m refinery2.mcp_server
Configure in your agent client as a stdio MCP server with that command.

Tools: project_status, list_templates, create_task, label_with_model,
       train_student, benchmark, predict.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(
    os.environ.get(
        "REFINERY_PROJECT",
        Path(__file__).resolve().parent.parent / "projects" / "demo_agnews",
    )
)

from .aggregate import aggregate_any  # noqa: E402
from .config import load_project  # noqa: E402
from .models import (  # noqa: E402
    api_predict,
    benchmark,
    get_model,
    golden_eval_split,
    load_registry,
    predict as _predict,
    train_local_model,
)
from .store import Store  # noqa: E402
from .tasks import load_tasks  # noqa: E402
from .templates import apply_template, create_task_inline, list_templates  # noqa: E402


def _ctx():
    cfg, slices = load_project(PROJECT_DIR)
    tasks = load_tasks(PROJECT_DIR / cfg.tasks_dir)
    store = Store(PROJECT_DIR / "data" / "store.db")
    return cfg, slices, tasks, store


def project_status() -> dict:
    from .aggregate import disagreement_queue

    cfg, _, tasks, store = _ctx()
    ids = [r["id"] for r in store.list_records(limit=10000)]
    out = {
        "project": cfg.name,
        "records": store.count_records(),
        "tasks": list(tasks),
        "models": [e["name"] for e in load_registry(PROJECT_DIR)],
    }
    for t in tasks:
        golden = store.golden_all(t)
        q = disagreement_queue(
            ids,
            lambda rid, t=t: store.source_labels_for(rid, t),
            lambda rid, t=t: (store.get_agg(rid, t) or {}).get("confidence"),
        )
        out[f"golden_{t}"] = len(golden)
        out[f"queue_{t}"] = len(q)
    return out


def create_task(template: str | None = None, task_def: dict | None = None, prefix: str = "") -> dict:
    cfg, _, _, _ = _ctx()
    if template:
        created = apply_template(PROJECT_DIR, cfg.tasks_dir, template, prefix)
        return {"ok": True, "tasks": created}
    if task_def:
        name = create_task_inline(PROJECT_DIR, cfg.tasks_dir, task_def)
        return {"ok": True, "tasks": [name]}
    raise ValueError("pass either template or task_def")


def label_with_model(model: str, task: str = "topic", limit: int = 200) -> dict:
    _, _, tasks, store = _ctx()
    if task not in tasks:
        raise ValueError(f"unknown task {task}")
    try:
        entry = get_model(PROJECT_DIR, model)
    except KeyError:
        entry = {"name": model, "kind": "jev" if model == "jev" else "api", "params": {}}
    if entry["kind"] not in ("api", "jev"):
        raise ValueError("label_with_model needs an api or jev model")
    from .models import jev_predict

    n, errors = 0, 0
    for r in store.list_records(limit=limit):
        try:
            if entry["kind"] == "jev":
                label, conf, _ = jev_predict(entry, tasks[task], r["text"])
            else:
                label, conf, _ = api_predict(entry, tasks[task], r["text"])
            store.add_source_label(r["id"], task, model, label, conf)
            n += 1
        except (RuntimeError, ValueError):
            errors += 1
    for r in store.list_records(limit=limit):
        votes = store.source_labels_for(r["id"], task)
        if votes:
            lab, conf = aggregate_any(votes)
            store.set_agg(r["id"], task, lab, conf)
    store.commit()
    return {"ok": True, "labeled": n, "errors": errors}


def train_student(task: str = "topic", name: str = "student-v1", min_conf: float = 0.8) -> dict:
    _, _, tasks, store = _ctx()
    if task not in tasks:
        raise ValueError(f"unknown task {task}")
    return train_local_model(PROJECT_DIR, store, tasks[task], name, min_conf)


def run_benchmark(task: str = "topic", models: list[str] | None = None) -> dict:
    _, _, tasks, store = _ctx()
    if task not in tasks:
        raise ValueError(f"unknown task {task}")
    return benchmark(PROJECT_DIR, store, tasks[task], models)


def run_predict(model: str, task: str, text: str) -> dict:
    _, _, tasks, _ = _ctx()
    if task not in tasks:
        raise ValueError(f"unknown task {task}")
    return _predict(PROJECT_DIR, model, tasks[task], text)


TOOLS = {
    "project_status": ("Project stats: records, tasks, golden counts, review queue, models.", {}),
    "list_templates": ("List task templates (gallery + bundles).", {}),
    "create_task": (
        "Create labeling task(s): from a gallery template OR inline vibecoded TaskDef. "
        "Writes versioned YAML.",
        {"template": "template name (optional)", "task_def": "inline TaskDef dict (optional)",
         "prefix": "prefix for task names (optional)"},
    ),
    "label_with_model": (
        "Label records with a registered API teacher model.",
        {"model": "registry model name", "task": "task name", "limit": "max records"},
    ),
    "train_student": (
        "Train a small local student on confident teacher consensus + golden.",
        {"task": "task name", "name": "new model name", "min_conf": "confidence threshold"},
    ),
    "benchmark": (
        "Compare registry models (teachers vs students) on golden holdout: acc/F1/latency.",
        {"task": "task name", "models": "optional list of model names"},
    ),
    "predict": (
        "Serve a prediction from any registered model.",
        {"model": "registry model name", "task": "task name", "text": "input text"},
    ),
}


def dispatch(name: str, args: dict) -> object:
    args = args or {}
    if name == "project_status":
        return project_status()
    if name == "list_templates":
        return {"templates": list_templates()}
    if name == "create_task":
        return create_task(args.get("template"), args.get("task_def"), args.get("prefix", ""))
    if name == "label_with_model":
        return label_with_model(args["model"], args.get("task", "topic"), int(args.get("limit", 200)))
    if name == "train_student":
        return train_student(args.get("task", "topic"), args.get("name", "student-v1"), float(args.get("min_conf", 0.8)))
    if name == "benchmark":
        return run_benchmark(args.get("task", "topic"), args.get("models"))
    if name == "predict":
        return run_predict(args["model"], args["task"], args["text"])
    raise ValueError(f"unknown tool {name}")


def _tool_defs() -> list[dict]:
    defs = []
    for name, (desc, props) in TOOLS.items():
        schema: dict = {"type": "object", "properties": {}}
        required = []
        if name in ("label_with_model", "predict"):
            required = ["model"]
        if name == "predict":
            required = ["model", "task", "text"]
        if name == "create_task":
            schema["properties"] = {
                "template": {"type": "string"},
                "task_def": {"type": "object"},
                "prefix": {"type": "string"},
            }
        elif name == "label_with_model":
            schema["properties"] = {
                "model": {"type": "string"}, "task": {"type": "string"}, "limit": {"type": "integer"},
            }
        elif name == "train_student":
            schema["properties"] = {
                "task": {"type": "string"}, "name": {"type": "string"}, "min_conf": {"type": "number"},
            }
        elif name == "benchmark":
            schema["properties"] = {"task": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}}}
        elif name == "predict":
            schema["properties"] = {
                "model": {"type": "string"}, "task": {"type": "string"}, "text": {"type": "string"},
            }
        if required:
            schema["required"] = required
        defs.append({"name": name, "description": desc, "inputSchema": schema})
    return defs


def serve() -> None:
    inp = sys.stdin
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "refinery-2", "version": "0.1.0"},
                }
            elif method == "tools/list":
                result = {"tools": _tool_defs()}
            elif method == "tools/call":
                result = {"content": [{"type": "text", "text": json.dumps(dispatch(msg["params"]["name"], msg["params"].get("arguments", {})))}]}
            elif method == "ping":
                result = {}
            elif method.startswith("notifications/"):
                continue
            else:
                raise ValueError(f"unknown method {method}")
            if mid is not None:
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
                sys.stdout.flush()
        except Exception as e:
            if mid is not None:
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": str(e)}}) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    serve()
