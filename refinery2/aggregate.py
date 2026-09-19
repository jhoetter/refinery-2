"""Aggregation + source quality: the modern weak-supervision core.

- aggregate_classification: confidence-weighted vote across sources.
- source_quality: per-source accuracy/coverage/confusion vs golden set.
- disagreement_queue: records where sources disagree or confidence is low.
"""
from __future__ import annotations

from collections import Counter


def aggregate_classification(votes: list[dict]) -> tuple[object, float]:
    """votes = [{label, confidence}]. Returns (label, confidence)."""
    if not votes:
        return None, 0.0
    weights: dict[str, float] = {}
    for v in votes:
        weights[v["label"]] = weights.get(v["label"], 0.0) + float(v.get("confidence", 1.0))
    total = sum(weights.values())
    top = max(weights, key=lambda k: weights[k])
    return top, round(weights[top] / total, 3) if total else (top, 0.0)


def source_quality(source_labels: list[dict], golden: dict[str, object]) -> dict[str, dict]:
    """Per-source {accuracy, coverage, n} measured against golden labels."""
    stats: dict[str, dict] = {}
    by_source: dict[str, list] = {}
    for s in source_labels:
        by_source.setdefault(s["source"], []).append(s)
    for source, items in by_source.items():
        scored = [(i["record_id"], i["label"]) for i in items if i["record_id"] in golden]
        if not scored:
            stats[source] = {"accuracy": None, "coverage": len(items), "n_scored": 0}
            continue
        correct = sum(1 for rid, lab in scored if lab == golden[rid])
        stats[source] = {
            "accuracy": round(correct / len(scored), 3),
            "coverage": len(items),
            "n_scored": len(scored),
        }
    return stats


def disagreement_queue(
    record_ids: list[str],
    get_votes,
    get_agg_conf,
    threshold: float = 0.65,
) -> list[dict]:
    """Records where sources disagree or aggregated confidence < threshold."""
    queue = []
    for rid in record_ids:
        votes = get_votes(rid)
        labels = {v["label"] for v in votes}
        conf = get_agg_conf(rid)
        if len(labels) > 1 or (conf is not None and conf < threshold):
            queue.append({"record_id": rid, "n_sources": len(votes), "confidence": conf})
    queue.sort(key=lambda q: (q["confidence"] is not None, q["confidence"] or 0.0))
    return queue


def confusion(golden: dict[str, str], pred: dict[str, str]) -> dict[str, Counter]:
    mat: dict[str, Counter] = {}
    for rid, g in golden.items():
        if rid in pred:
            mat.setdefault(g, Counter())[pred[rid]] += 1
    return mat
