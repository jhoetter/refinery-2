"""Seed + sync helpers: load records.jsonl into sqlite, import golden.jsonl."""
from __future__ import annotations

import json
from pathlib import Path

from refinery2.store import Store

PROJECT = Path(__file__).resolve().parent.parent / "projects" / "demo_agnews"


def sync(scale_golden: int = 60) -> None:
    from refinery2.aggregate import aggregate_any
    from refinery2.config import load_project
    from refinery2.sources import mock_llm_topic, run_sources_for_record
    from refinery2.tasks import load_tasks

    cfg, _ = load_project(PROJECT)
    tasks = load_tasks(PROJECT / cfg.tasks_dir)
    store = Store(PROJECT / "data" / "store.db")
    recs = [json.loads(l) for l in (PROJECT / "data" / "records.jsonl").open()]
    store.upsert_records(recs)
    # label every record with every built-in source, aggregate every project task
    for r in recs:
        for task, sources in run_sources_for_record(r["text"]).items():
            for source, v in sources.items():
                store.add_source_label(r["id"], task, source, v["label"], v["confidence"])
    for r in recs:
        for task in tasks:
            votes = store.source_labels_for(r["id"], task)
            if votes:
                label, conf = aggregate_any(votes)
                store.set_agg(r["id"], task, label, conf)
    store.commit()
    # seed golden: first `scale_golden` records with REAL ground truth.
    # AG News rows carry the true hf_label (0=World, 1=Sports, 2=Business,
    # 3=Sci/Tech) — that is the "careful human". Users overwrite/extend
    # these via the review UI.
    golden_path = PROJECT / "golden" / "golden.jsonl"
    golden_path.parent.mkdir(parents=True, exist_ok=True)
    HF_TO_LABEL = ["World", "Sports", "Business", "Sci/Tech"]
    if not golden_path.exists():
        # stratified: AG News is class-sorted, so spread across true labels
        by_label: dict[int, list[dict]] = {}
        for r in recs:
            hf = (r.get("meta") or {}).get("hf_label")
            if hf is not None:
                by_label.setdefault(int(hf), []).append(r)
        per_class = max(1, scale_golden // max(len(by_label), 1)) if by_label else scale_golden
        seed = [r for lab in sorted(by_label) for r in by_label[lab][:per_class]][:scale_golden]
        if not seed:
            seed = recs[:scale_golden]
        with golden_path.open("w") as f:
            for r in seed:
                hf = (r.get("meta") or {}).get("hf_label")
                if hf is not None:
                    label = HF_TO_LABEL[int(hf)]
                else:  # synthetic fallback rows: mock-llm as stand-in
                    label, _ = mock_llm_topic(r["text"])
                f.write(json.dumps({"record_id": r["id"], "task": "topic", "label": label}) + "\n")
    for line in golden_path.open():
        g = json.loads(line)
        store.set_golden(g["record_id"], g["task"], g["label"])
    print(f"synced {len(recs)} records, store={store.count_records()}")


if __name__ == "__main__":
    sync()
