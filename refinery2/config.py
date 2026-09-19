"""Project config: refinery.yaml + slices.yaml, all git-versioned."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class ProjectConfig(BaseModel):
    name: str = "demo"
    dataset: str = "agnews-subset"
    records_path: str = "data/records.jsonl"
    golden_path: str = "golden/golden.jsonl"
    tasks_dir: str = "tasks"
    slices_path: str = "slices.yaml"


def load_project(project_dir: Path) -> tuple[ProjectConfig, list[dict]]:
    cfg_path = project_dir / "refinery.yaml"
    data = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    cfg = ProjectConfig(**data)
    slices_path = project_dir / cfg.slices_path
    slices: list[dict] = []
    if slices_path.exists():
        slices = yaml.safe_load(slices_path.read_text()) or []
    return cfg, slices


def apply_slices(record: dict, slices: list[dict]) -> list[str]:
    """Return slice names a record belongs to. Slice = {name, match: {field: substr}}."""
    text = (record.get("text") or "").lower()
    hits = []
    for s in slices:
        match = s.get("match", {}) or {}
        ok = True
        for field, substr in match.items():
            if field == "text_contains":
                if str(substr).lower() not in text:
                    ok = False
            elif field == "len_lt":
                if len(record.get("text") or "") >= int(substr):
                    ok = False
            elif field == "len_gte":
                if len(record.get("text") or "") < int(substr):
                    ok = False
        if ok:
            hits.append(s["name"])
    return hits
