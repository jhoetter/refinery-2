"""Task definitions: classification, spans (NER), extraction.

Tasks are declared as-code in YAML, e.g.:

  name: topic
  type: classification
  labels: [World, Sports, Business, Sci/Tech]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, field_validator

TaskType = Literal["classification", "spans", "extraction"]


class TaskDef(BaseModel):
    name: str
    type: TaskType
    description: str = ""
    # classification
    labels: list[str] = []
    # spans (NER-style): entity types
    entities: list[str] = []
    # extraction: fields {name, prompt}
    fields: list[dict[str, str]] = []
    # which model/source to use by default for auto-labeling
    model: str = "mock-llm"

    @field_validator("labels", "entities", mode="before")
    @classmethod
    def _empty(cls, v: Any) -> Any:
        return v or []


def load_tasks(tasks_dir: Path) -> dict[str, TaskDef]:
    tasks: dict[str, TaskDef] = {}
    for path in sorted(tasks_dir.glob("*.yaml")) + sorted(tasks_dir.glob("*.yml")):
        data = yaml.safe_load(path.read_text())
        task = TaskDef(**data)
        tasks[task.name] = task
    return tasks


def validate_label(task: TaskDef, label: Any) -> Any:
    """Normalize + validate a label value for a task. Raises ValueError."""
    if task.type == "classification":
        if isinstance(label, dict):
            label = label.get("label", label.get("value"))
        if label not in task.labels:
            raise ValueError(f"unknown label {label!r}, expected one of {task.labels}")
        return label
    if task.type == "spans":
        # list of {start, end, entity, text?}
        if not isinstance(label, list):
            raise ValueError("spans label must be a list")
        out = []
        for s in label:
            if s.get("entity") not in task.entities:
                raise ValueError(f"unknown entity {s.get('entity')!r}")
            out.append(
                {"start": int(s["start"]), "end": int(s["end"]), "entity": s["entity"]}
            )
        return out
    if task.type == "extraction":
        if not isinstance(label, dict):
            raise ValueError("extraction label must be a dict")
        return {f["name"]: label.get(f["name"]) for f in task.fields}
    raise ValueError(f"unknown task type {task.type}")
