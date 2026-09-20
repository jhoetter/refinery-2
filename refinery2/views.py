"""Saved views: complex, versioned record filters (refinery search-groups, slim).

View YAML in <project>/views/*.yaml:
  name: low-conf-sports
  description: ...
  logic: and            # how top-level groups combine
  groups:
    - logic: and
      negate: false
      conditions:
        - {field: agg_label, task: topic, op: eq, value: Sports}
        - {field: confidence, task: topic, op: lt, value: 0.7}
    - logic: or
      conditions:
        - {field: golden, task: topic, op: missing}

Condition fields:
  text_contains | text_regex | agg_label | golden_label | golden |
  confidence | disagreement | slice | source_label
Ops: eq ne in contains regex lt lte gt gte present missing true false
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


def views_dir(project_dir: Path) -> Path:
    d = project_dir / "views"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_views(project_dir: Path) -> list[dict]:
    out = []
    for path in sorted(views_dir(project_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        out.append(
            {
                "name": path.stem,
                "description": data.get("description", ""),
                "logic": data.get("logic", "and"),
                "groups": data.get("groups", []),
            }
        )
    return out


def get_view(project_dir: Path, name: str) -> dict:
    path = views_dir(project_dir) / f"{name}.yaml"
    if not path.exists():
        raise KeyError(f"unknown view {name!r}")
    data = yaml.safe_load(path.read_text()) or {}
    return {"name": path.stem, **data}


def save_view(project_dir: Path, view: dict) -> str:
    name = str(view.get("name", "")).strip().replace(" ", "-").lower()
    if not name:
        raise ValueError("view needs a name")
    body = {"description": view.get("description", ""), "logic": view.get("logic", "and"),
            "groups": view.get("groups", [])}
    (views_dir(project_dir) / f"{name}.yaml").write_text(yaml.safe_dump(body, sort_keys=False))
    return name


def delete_view(project_dir: Path, name: str) -> None:
    path = views_dir(project_dir) / f"{name}.yaml"
    if not path.exists():
        raise KeyError(f"unknown view {name!r}")
    path.unlink()


def _cmp(op: str, actual, expected) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    if op == "contains":
        return str(expected).lower() in str(actual or "").lower()
    if op == "regex":
        return re.search(str(expected), str(actual or "")) is not None
    if op in ("lt", "lte", "gt", "gte"):
        try:
            a, e = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {"lt": a < e, "lte": a <= e, "gt": a > e, "gte": a >= e}[op]
    if op == "present":
        return actual is not None
    if op == "missing":
        return actual is None
    if op == "true":
        return bool(actual) is True
    if op == "false":
        return bool(actual) is False
    raise ValueError(f"unknown operator {op!r}")


def eval_condition(store, slices: list[dict], rid: str, text: str, cond: dict) -> bool:
    from .config import apply_slices

    field, op = cond.get("field"), cond.get("op", "eq")
    task = cond.get("task")
    if field == "text_contains":
        return str(cond.get("value", "")).lower() in text.lower()
    if field == "text_regex":
        return re.search(str(cond.get("value", "")), text) is not None
    if field == "agg_label":
        agg = store.get_agg(rid, task)
        return _cmp(op, agg["label"] if agg else None, cond.get("value"))
    if field == "golden_label":
        return _cmp(op, store.get_golden(rid, task), cond.get("value"))
    if field == "golden":
        return _cmp(op, store.get_golden(rid, task), cond.get("value"))
    if field == "confidence":
        agg = store.get_agg(rid, task)
        return _cmp(op, agg["confidence"] if agg else None, cond.get("value"))
    if field == "disagreement":
        votes = store.source_labels_for(rid, task)
        disagree = len({json_label(v["label"]) for v in votes}) > 1
        return _cmp(op, disagree, cond.get("value", True))
    if field == "slice":
        mine = apply_slices({"id": rid, "text": text}, slices)
        if op == "ne":
            return cond.get("value") not in mine
        if op == "in":
            return any(s in mine for s in (cond.get("value") or []))
        return cond.get("value") in mine
    if field == "source_label":
        votes = {v["source"]: v["label"] for v in store.source_labels_for(rid, task)}
        return _cmp(op, votes.get(cond.get("source")), cond.get("value"))
    raise ValueError(f"unknown field {field!r}")


def json_label(label) -> str:
    import json as _json

    return _json.dumps(label, sort_keys=True)


def eval_view(store, slices: list[dict], view: dict, limit: int = 10000) -> list[str]:
    """Return matching record ids. Groups combine via view.logic; conditions via group.logic."""
    recs = store.list_records(limit=limit)
    top_logic = (view.get("logic") or "and").lower()
    hits = []
    for r in recs:
        results = []
        for g in view.get("groups", []) or [{"logic": "and", "conditions": []}]:
            conds = [eval_condition(store, slices, r["id"], r["text"], c) for c in g.get("conditions", [])]
            glogic = (g.get("logic") or "and").lower()
            val = all(conds) if glogic == "and" else any(conds)
            if g.get("negate"):
                val = not val
            results.append(val)
        if (all(results) if top_logic == "and" else any(results)) if results else True:
            hits.append(r["id"])
    return hits
