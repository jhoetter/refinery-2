"""FastAPI server: project API + static review UI on a single port."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import os

from .aggregate import aggregate_any, disagreement_queue, source_quality
from .config import apply_slices, load_project
from .distill import evaluate, evaluate_slices, train_classifier
from .sources import run_sources_for_record
from .store import Store
from .tasks import load_tasks, validate_label

PROJECT_DIR = Path(
    os.environ.get(
        "REFINERY_PROJECT",
        Path(__file__).resolve().parent.parent / "projects" / "demo_agnews",
    )
)

app = FastAPI(title="refinery-2")


def _ctx():
    cfg, slices = load_project(PROJECT_DIR)
    tasks = load_tasks(PROJECT_DIR / cfg.tasks_dir)
    store = Store(PROJECT_DIR / "data" / "store.db")
    return cfg, slices, tasks, store


@app.get("/api/project")
def project():
    cfg, slices, tasks, store = _ctx()
    return {
        "name": cfg.name,
        "dataset": cfg.dataset,
        "n_records": store.count_records(),
        "tasks": {k: v.model_dump() for k, v in tasks.items()},
        "slices": slices,
    }


@app.get("/api/records")
def records(task: str = "topic", limit: int = 30, offset: int = 0, q: str = ""):
    _, _, _, store = _ctx()
    recs = store.list_records(limit=500 if q else limit, offset=0 if q else offset)
    if q:
        ql = q.lower()
        recs = [r for r in recs if ql in r["text"].lower()][offset : offset + limit]
    out = []
    for r in recs:
        votes = store.source_labels_for(r["id"], task)
        agg = store.get_agg(r["id"], task)
        out.append(
            {
                "id": r["id"],
                "text": r["text"][:600],
                "meta": r["meta"],
                "votes": votes,
                "agg": agg,
                "golden": store.get_golden(r["id"], task),
            }
        )
    return {"records": out}


@app.get("/api/record/{rid}")
def record(rid: str, task: str = "topic"):
    _, _, _, store = _ctx()
    r = store.get_record(rid)
    if not r:
        raise HTTPException(404, "record not found")
    return {
        "record": r,
        "votes": store.source_labels_for(rid, task),
        "agg": store.get_agg(rid, task),
        "golden": store.get_golden(rid, task),
    }


class LabelIn(BaseModel):
    record_id: str
    task: str
    label: object


@app.post("/api/labels")
def set_label(body: LabelIn):
    _, _, tasks, store = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    try:
        label = validate_label(tasks[body.task], body.label)
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.set_golden(body.record_id, body.task, label)
    return {"ok": True}


class RunIn(BaseModel):
    limit: int = 200


@app.post("/api/run-sources")
def run_sources(body: RunIn):
    from .aggregate import aggregate_any

    _, _, tasks, store = _ctx()
    recs = store.list_records(limit=body.limit)
    n = 0
    for r in recs:
        out = run_sources_for_record(r["text"])
        for task, sources in out.items():
            for source, v in sources.items():
                store.add_source_label(r["id"], task, source, v["label"], v["confidence"])
    # re-aggregate every task that exists in the project
    for r in recs:
        for task in tasks:
            votes = store.source_labels_for(r["id"], task)
            if votes:
                label, conf = aggregate_any(votes)
                store.set_agg(r["id"], task, label, conf)
    store.commit()
    return {"ok": True, "n_records": len(recs)}


@app.get("/api/quality")
def quality(task: str = "topic"):
    _, _, _, store = _ctx()
    golden = store.golden_all(task)
    labels = store.all_source_labels(task)
    return {"golden_n": len(golden), "sources": source_quality(labels, golden)}


@app.get("/api/stats")
def stats(task: str = "topic"):
    """Distributions for the dashboard: label dist, confidence histogram, slices."""
    cfg, slices, tasks, store = _ctx()
    if task not in tasks:
        raise HTTPException(400, f"unknown task {task}")
    recs = store.list_records(limit=10000)
    golden = store.golden_all(task)
    agg = store.agg_all(task)
    dist_agg: dict[str, int] = {}
    hist = [0] * 10
    for rid, v in agg.items():
        dist_agg[str(v["label"])] = dist_agg.get(str(v["label"]), 0) + 1
        hist[min(9, int(v["confidence"] * 10))] += 1
    dist_golden: dict[str, int] = {}
    for lab in golden.values():
        dist_golden[str(lab)] = dist_golden.get(str(lab), 0) + 1
    slice_n: dict[str, int] = {}
    for r in recs:
        for s in apply_slices(r, slices) or ["all"]:
            slice_n[s] = slice_n.get(s, 0) + 1
    labels = store.all_source_labels(task)
    return {
        "task": task,
        "n_records": len(recs),
        "n_golden": len(golden),
        "coverage": round(len(golden) / max(len(recs), 1), 3),
        "dist_agg": dist_agg,
        "dist_golden": dist_golden,
        "conf_hist": hist,
        "sources": source_quality(labels, golden),
        "slices": slice_n,
    }


# ---- views: saved complex filters (as-code YAML) ----
@app.get("/api/views")
def views_list():
    from .views import list_views

    return {"views": list_views(PROJECT_DIR)}


@app.post("/api/views")
def view_save(body: dict):
    from .views import save_view

    try:
        name = save_view(PROJECT_DIR, body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "view": name}


@app.delete("/api/views/{name}")
def view_delete(name: str):
    from .views import delete_view

    try:
        delete_view(PROJECT_DIR, name)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


class ViewRunIn(BaseModel):
    view: str | None = None      # saved view name
    definition: dict | None = None  # inline view (preview before saving)
    task: str = "topic"
    limit: int = 200


@app.post("/api/views/run")
def view_run(body: ViewRunIn):
    from .views import eval_view, get_view

    _, slices, _, store = _ctx()
    if body.view:
        try:
            view = get_view(PROJECT_DIR, body.view)
        except KeyError as e:
            raise HTTPException(404, str(e))
    elif body.definition:
        view = body.definition
    else:
        raise HTTPException(400, "pass view or definition")
    try:
        ids = eval_view(store, slices, view)
    except ValueError as e:
        raise HTTPException(400, str(e))
    out = []
    for rid in ids[: body.limit]:
        r = store.get_record(rid)
        votes = store.source_labels_for(rid, body.task)
        agg = store.get_agg(rid, body.task)
        out.append(
            {
                "id": r["id"],
                "text": r["text"][:600],
                "meta": r["meta"],
                "votes": votes,
                "agg": agg,
                "golden": store.get_golden(rid, body.task),
            }
        )
    return {"records": out, "n": len(ids)}


@app.get("/api/queue")
def queue(task: str = "topic", threshold: float = 0.65):
    _, _, _, store = _ctx()
    ids = [r["id"] for r in store.list_records(limit=10000)]
    q = disagreement_queue(
        ids,
        lambda rid: store.source_labels_for(rid, task),
        lambda rid: (store.get_agg(rid, task) or {}).get("confidence"),
        threshold,
    )
    return {"queue": q[:200], "n": len(q)}


class DistillIn(BaseModel):
    task: str = "topic"
    train_on: str = "agg"  # agg | golden
    min_conf: float = 0.8  # only distill confident consensus + golden


@app.post("/api/distill")
def distill(body: DistillIn):
    _, slices, _, store = _ctx()
    if body.task != "topic":
        raise HTTPException(400, "MVP distills the classification task only")
    agg = store.agg_all(body.task)
    golden = store.golden_all(body.task)
    if body.train_on == "agg":
        pool = {
            rid: v["label"] for rid, v in agg.items() if v["confidence"] >= body.min_conf
        }
        pool.update(golden)  # golden ground truth always wins
    else:
        pool = dict(golden)
    # stratified holdout: 30% of golden per class for eval
    by_label: dict[str, list[str]] = {}
    for rid, lab in golden.items():
        by_label.setdefault(str(lab), []).append(rid)
    eval_ids = [rid for lab_ids in by_label.values() for rid in sorted(lab_ids)[int(len(lab_ids) * 0.7):]]
    eval_set = set(eval_ids)
    pairs = [
        (store.get_record(rid)["text"], lab)
        for rid, lab in pool.items()
        if rid not in eval_set and store.get_record(rid)
    ]
    texts = [t for t, _ in pairs]
    labels = [lab for _, lab in pairs]
    if len(set(labels)) < 2 or len(texts) < 10:
        raise HTTPException(400, "not enough training data (need >=10 rows, >=2 classes)")
    clf = train_classifier(texts, labels)
    eval_recs = [store.get_record(i) for i in eval_ids if store.get_record(i)]
    eval_labels = [golden[i] for i in eval_ids if store.get_record(i)]
    overall = evaluate(clf, [r["text"] for r in eval_recs], eval_labels)
    by_slice = evaluate_slices(
        clf, eval_recs, {r["id"]: golden[r["id"]] for r in eval_recs},
        lambda rid: apply_slices(store.get_record(rid), slices) or ["all"],
    )
    return {
        "train_n": len(texts),
        "eval_n": len(eval_recs),
        "min_conf": body.min_conf if body.train_on == "agg" else None,
        "overall": overall,
        "by_slice": by_slice,
        "note": "Naive-Bayes student trained on confident teacher consensus + golden",
    }


# ---- templates: gallery + vibecoded creation (all as-code) ----
@app.get("/api/templates")
def templates_list():
    from .templates import list_templates

    return {"templates": list_templates()}


@app.get("/api/templates/{name}")
def template_get(name: str):
    from .templates import get_template

    try:
        return get_template(name)
    except KeyError as e:
        raise HTTPException(404, str(e))


class TaskFromTemplate(BaseModel):
    template: str
    prefix: str = ""


@app.post("/api/tasks/from-template")
def task_from_template(body: TaskFromTemplate):
    cfg, _, _, _ = _ctx()
    from .templates import apply_template

    try:
        created = apply_template(PROJECT_DIR, cfg.tasks_dir, body.template, body.prefix)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "tasks": created}


@app.post("/api/tasks")
def task_create(body: dict):
    """Vibecode path: agent-generated TaskDef JSON becomes a versioned YAML."""
    cfg, _, _, _ = _ctx()
    from .templates import create_task_inline

    try:
        name = create_task_inline(PROJECT_DIR, cfg.tasks_dir, body)
    except Exception as e:
        raise HTTPException(400, f"invalid task definition: {e}")
    return {"ok": True, "task": name}


# ---- models: registry, teachers, students, benchmark, serve ----
@app.get("/api/models")
def models_list():
    from .models import load_registry

    return {"models": load_registry(PROJECT_DIR)}


class ApiModelIn(BaseModel):
    name: str
    task: str
    base_url: str
    model: str
    api_key_env: str = "LLM_API_KEY"


@app.post("/api/models/api")
def models_register_api(body: ApiModelIn):
    from .models import register_api_model

    return register_api_model(
        PROJECT_DIR, body.name, body.task, body.base_url, body.model, body.api_key_env
    )


class TrainIn(BaseModel):
    task: str = "topic"
    name: str = "student-v1"
    min_conf: float = 0.8


@app.post("/api/models/train")
def models_train(body: TrainIn):
    from .models import train_local_model

    _, _, tasks, store = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    try:
        entry = train_local_model(PROJECT_DIR, store, tasks[body.task], body.name, body.min_conf)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return entry


class BenchIn(BaseModel):
    task: str = "topic"
    models: list[str] | None = None


@app.post("/api/models/benchmark")
def models_benchmark(body: BenchIn):
    from .models import benchmark

    _, _, tasks, store = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    try:
        return benchmark(PROJECT_DIR, store, tasks[body.task], body.models)
    except ValueError as e:
        raise HTTPException(400, str(e))


class PredictIn(BaseModel):
    model: str
    task: str
    text: str


@app.post("/api/predict")
def predict(body: PredictIn):
    from .models import predict as _predict

    _, _, tasks, _ = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    try:
        return _predict(PROJECT_DIR, body.model, tasks[body.task], body.text)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(502, str(e))


class TeacherRunIn(BaseModel):
    model: str
    task: str = "topic"
    limit: int = 200


@app.post("/api/run-teacher")
def run_teacher(body: TeacherRunIn):
    """Label records with a registered API teacher (source name = model name)."""
    from .models import api_predict, get_model

    _, _, tasks, store = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    try:
        entry = get_model(PROJECT_DIR, body.model)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if entry["kind"] != "api":
        raise HTTPException(400, "run-teacher needs an api model; local models use /api/predict")
    recs = store.list_records(limit=body.limit)
    n, errors = 0, 0
    for r in recs:
        try:
            label, conf, _ = api_predict(entry, tasks[body.task], r["text"])
            store.add_source_label(r["id"], body.task, body.model, label, conf)
            n += 1
        except RuntimeError:
            errors += 1
    store.commit()
    return {"ok": True, "labeled": n, "errors": errors}


class JevRunIn(BaseModel):
    task: str = "topic"
    limit: int = 200


@app.post("/api/run-jev")
def run_jev(body: JevRunIn):
    """Label records with live Jev (source name 'jev'). Needs JEV_API_KEY."""
    from .jev import jev_choice
    from .models import get_model as _get

    _, _, tasks, store = _ctx()
    if body.task not in tasks:
        raise HTTPException(400, f"unknown task {body.task}")
    task = tasks[body.task]
    if task.type != "classification":
        raise HTTPException(400, "live jev currently supports classification tasks")
    try:
        entry = _get(PROJECT_DIR, "jev")
    except KeyError:
        entry = {"name": "jev", "kind": "jev", "params": {"model": "jev-latest"}}
    options = {lab: lab for lab in task.labels}
    recs = store.list_records(limit=body.limit)
    n, errors = 0, 0
    for r in recs:
        try:
            label, conf, _, _ = jev_choice(
                r["text"], task.description or task.name, options,
            )
            store.add_source_label(r["id"], body.task, "jev", validate_label(task, label), conf)
            n += 1
        except RuntimeError:
            errors += 1
    for r in recs:
        votes = store.source_labels_for(r["id"], body.task)
        if votes:
            label, conf = aggregate_any(votes)
            store.set_agg(r["id"], body.task, label, conf)
    store.commit()
    return {"ok": True, "labeled": n, "errors": errors}


# ---- static UI (legacy fallback; primary UI is Next.js on :3000) ----
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))
