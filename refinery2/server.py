"""FastAPI server: project API + static review UI on a single port."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import os

from .aggregate import (
    aggregate_classification,
    disagreement_queue,
    source_quality,
)
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
    _, _, _, store = _ctx()
    recs = store.list_records(limit=body.limit)
    n = 0
    for r in recs:
        out = run_sources_for_record(r["text"])
        for task, sources in out.items():
            for source, v in sources.items():
                store.add_source_label(r["id"], task, source, v["label"], v["confidence"])
    # re-aggregate classification task
    for r in recs:
        votes = store.source_labels_for(r["id"], "topic")
        if votes:
            label, conf = aggregate_classification(votes)
            store.set_agg(r["id"], "topic", label, conf)
    store.commit()
    return {"ok": True, "n_records": len(recs)}


@app.get("/api/quality")
def quality(task: str = "topic"):
    _, _, _, store = _ctx()
    golden = store.golden_all(task)
    labels = store.all_source_labels(task)
    return {"golden_n": len(golden), "sources": source_quality(labels, golden)}


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


# ---- static UI ----
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))
