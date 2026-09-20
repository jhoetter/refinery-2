"""Model registry: API teachers (OpenAI-compatible) + local students, all as-code.

Registry lives at <project>/models/models.yaml, artifacts at <project>/models/.
Benchmark answers: how does the cheap local model match the LLM teacher?
"""
from __future__ import annotations

import json
import os
import pickle
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .distill import evaluate, train_classifier
from .tasks import TaskDef, validate_label


def models_dir(project_dir: Path) -> Path:
    d = project_dir / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_registry(project_dir: Path) -> list[dict]:
    path = models_dir(project_dir) / "models.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text()) or []


def save_registry(project_dir: Path, entries: list[dict]) -> None:
    path = models_dir(project_dir) / "models.yaml"
    path.write_text(yaml.safe_dump(entries, sort_keys=False))


def get_model(project_dir: Path, name: str) -> dict:
    for e in load_registry(project_dir):
        if e["name"] == name:
            return e
    raise KeyError(f"unknown model {name!r}")


def register_api_model(
    project_dir: Path, name: str, task: str, base_url: str, model: str, api_key_env: str = "LLM_API_KEY"
) -> dict:
    entries = [e for e in load_registry(project_dir) if e["name"] != name]
    entry = {
        "name": name,
        "kind": "api",
        "task": task,
        "created": datetime.now(timezone.utc).isoformat(),
        "params": {"base_url": base_url.rstrip("/"), "model": model, "api_key_env": api_key_env},
        "metrics": {},
    }
    entries.append(entry)
    save_registry(project_dir, entries)
    return entry


# ---- API teacher (OpenAI-compatible chat completions, stdlib http) ----

def build_prompt(task: TaskDef, text: str) -> tuple[str, str]:
    system = "You are a precise data-labeling assistant. Reply with JSON only."
    if task.type == "classification":
        user = (
            f"Task: {task.description or task.name}\n"
            f"Labels (reply with exactly one): {task.labels}\n"
            f'Text: """{text}"""\n'
            'Reply JSON: {"label": "<one of the labels>", "confidence": 0.0-1.0}'
        )
    elif task.type == "spans":
        user = (
            f"Task: {task.description or task.name}\n"
            f"Entity types: {task.entities}\n"
            f'Text: """{text}"""\n'
            'Reply JSON: {"spans": [{"start": int, "end": int, "entity": "<type>"}]} '
            "(character offsets into the text)"
        )
    else:
        fields = ", ".join(f'{f["name"]}: {f.get("prompt", "")}' for f in task.fields)
        user = (
            f"Task: {task.description or task.name}\n"
            f"Fields: {fields}\n"
            f'Text: """{text}"""\n'
            'Reply JSON object with exactly these keys: '
            + ", ".join(f["name"] for f in task.fields)
        )
    return system, user


def api_predict(entry: dict, task: TaskDef, text: str, timeout: int = 60) -> tuple[object, float, float]:
    """Returns (label, confidence, latency_ms). Raises RuntimeError on failure."""
    p = entry["params"]
    key = os.environ.get(p.get("api_key_env", "LLM_API_KEY"), "")
    url = p["base_url"] + "/chat/completions"
    system, user = build_prompt(task, text)
    body = {
        "model": p["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.load(r)
    except Exception as e:
        raise RuntimeError(f"API model {entry['name']} failed: {e}")
    latency = (time.time() - t0) * 1000
    try:
        content = payload["choices"][0]["message"]["content"]
        data = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"API model {entry['name']} returned unparsable output: {e}")
    if task.type == "classification":
        label = validate_label(task, data.get("label"))
        conf = float(data.get("confidence", 0.8))
    elif task.type == "spans":
        label = validate_label(task, data.get("spans", []))
        conf = 0.8
    else:
        label = validate_label(task, data)
        conf = 0.8
    return label, conf, round(latency, 1)


# ---- local student (pickled NB) ----

def train_local_model(project_dir: Path, store, task: TaskDef, name: str, min_conf: float = 0.8) -> dict:
    from .aggregate import aggregate_classification  # noqa (kept for future weighting)

    agg = store.agg_all(task.name)
    golden = store.golden_all(task.name)
    pool = {rid: v["label"] for rid, v in agg.items() if v["confidence"] >= min_conf}
    pool.update(golden)
    pairs = [(store.get_record(rid)["text"], lab) for rid, lab in pool.items() if store.get_record(rid)]
    if len({lab for _, lab in pairs}) < 2 or len(pairs) < 10:
        raise ValueError("not enough training data (need >=10 rows, >=2 classes)")
    clf = train_classifier([t for t, _ in pairs], [lab for _, lab in pairs])
    artifact = f"{name}.pkl"
    with open(models_dir(project_dir) / artifact, "wb") as f:
        pickle.dump({"task": task.name, "classes": clf.classes, "model": clf}, f)
    entries = [e for e in load_registry(project_dir) if e["name"] != name]
    entry = {
        "name": name,
        "kind": "local",
        "task": task.name,
        "created": datetime.now(timezone.utc).isoformat(),
        "params": {"artifact": artifact, "min_conf": min_conf},
        "metrics": {"train_n": len(pairs)},
    }
    entries.append(entry)
    save_registry(project_dir, entries)
    return entry


def load_local(project_dir: Path, entry: dict):
    with open(models_dir(project_dir) / entry["params"]["artifact"], "rb") as f:
        return pickle.load(f)["model"]


def local_predict(project_dir: Path, entry: dict, text: str) -> tuple[object, float, float]:
    clf = load_local(project_dir, entry)
    t0 = time.time()
    label = clf.predict_one(text)
    probs = clf.proba_one(text)
    latency = (time.time() - t0) * 1000
    return label, round(max(probs.values()), 3), round(latency, 1)


def jev_predict(entry: dict, task: TaskDef, text: str) -> tuple[object, float, float]:
    """Live Jev teacher. Currently supports classification tasks."""
    if task.type != "classification":
        raise ValueError("jev runner currently supports classification tasks")
    from .jev import jev_choice

    options = {lab: lab for lab in task.labels}
    label, conf, _probs, latency = jev_choice(
        text,
        task.description or f"Classify into one of: {task.labels}",
        options,
        model=entry.get("params", {}).get("model", "jev-latest"),
    )
    return validate_label(task, label), conf, latency


def predict(project_dir: Path, model_name: str, task: TaskDef, text: str) -> dict:
    entry = get_model(project_dir, model_name)
    if entry["kind"] == "api":
        label, conf, latency = api_predict(entry, task, text)
    elif entry["kind"] == "jev":
        label, conf, latency = jev_predict(entry, task, text)
    else:
        label, conf, latency = local_predict(project_dir, entry, text)
    return {"model": model_name, "label": label, "confidence": conf, "latency_ms": latency}


# ---- benchmark: teacher(s) vs student(s) on golden holdout ----

def golden_eval_split(golden: dict[str, str], frac: float = 0.3) -> list[str]:
    by_label: dict[str, list[str]] = {}
    for rid, lab in golden.items():
        by_label.setdefault(str(lab), []).append(rid)
    return [rid for ids in by_label.values() for rid in sorted(ids)[int(len(ids) * (1 - frac)):]]


def benchmark(
    project_dir: Path, store, task: TaskDef, model_names: list[str] | None = None
) -> dict:
    golden = store.golden_all(task.name)
    if len(golden) < 4:
        raise ValueError("need at least 4 golden labels to benchmark")
    eval_ids = golden_eval_split(golden)
    eval_recs = [store.get_record(i) for i in eval_ids]
    texts = [r["text"] for r in eval_recs]
    labels = [golden[r["id"]] for r in eval_recs]
    entries = load_registry(project_dir)
    if model_names:
        entries = [e for e in entries if e["name"] in model_names]
    results: dict[str, dict] = {}
    # baseline: aggregated consensus already in store
    agg = store.agg_all(task.name)
    if agg and all(i in agg for i in eval_ids):
        from .distill import evaluate as _ev

        class _Fake:
            def predict(self, ts):
                return [agg[i]["label"] for i in eval_ids]

        m = _ev(_Fake(), texts, labels)
        results["agg-consensus"] = {**m, "kind": "consensus", "latency_ms": 0.0}
    for e in entries:
        preds, lats = [], []
        ok_all = True
        for t in texts:
            try:
                if e["kind"] == "api":
                    lab, _, lat = api_predict(e, task, t)
                elif e["kind"] == "jev":
                    lab, _, lat = jev_predict(e, task, t)
                else:
                    lab, _, lat = local_predict(project_dir, e, t)
                preds.append(lab)
                lats.append(lat)
            except Exception:
                ok_all = False
                break
        if not ok_all or not preds:
            results[e["name"]] = {"error": "prediction failed (API unreachable?)", "kind": e["kind"]}
            continue
        from .distill import evaluate as _ev2

        class _F:
            def __init__(self, p):
                self._p = p

            def predict(self, ts):
                return self._p

        m = _ev2(_F(preds), texts, labels)
        results[e["name"]] = {
            **m, "kind": e["kind"], "latency_ms": round(sum(lats) / len(lats), 1),
        }
    return {"task": task.name, "eval_n": len(eval_ids), "models": results}
