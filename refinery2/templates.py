"""Task templates: gallery (built-in YAML) + vibecoded inline creation, all as-code."""
from __future__ import annotations

from pathlib import Path

import yaml

GALLERY = Path(__file__).resolve().parent / "templates"


def list_templates() -> list[dict]:
    out = []
    for path in sorted(GALLERY.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        out.append(
            {
                "template": path.stem,
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "tasks": [t.get("name") for t in data.get("tasks", [])],
            }
        )
    return out


def get_template(name: str) -> dict:
    path = GALLERY / f"{name}.yaml"
    if not path.exists():
        raise KeyError(f"unknown template {name!r}")
    return yaml.safe_load(path.read_text())


def apply_template(project_dir: Path, tasks_dir: str, name: str, prefix: str = "") -> list[str]:
    """Write template tasks into <project>/tasks/. Returns created task names."""
    from .tasks import TaskDef

    tpl = get_template(name)
    dest = project_dir / tasks_dir
    dest.mkdir(parents=True, exist_ok=True)
    created = []
    for t in tpl.get("tasks", []):
        task = TaskDef(**t)
        if prefix:
            task.name = f"{prefix}-{task.name}"
        (dest / f"{task.name}.yaml").write_text(
            yaml.safe_dump(task.model_dump(exclude_none=True), sort_keys=False)
        )
        created.append(task.name)
    return created


def create_task_inline(project_dir: Path, tasks_dir: str, task_def: dict) -> str:
    """Vibecoded path: an agent-generated TaskDef dict becomes a versioned YAML."""
    from .tasks import TaskDef

    task = TaskDef(**task_def)
    dest = project_dir / tasks_dir
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{task.name}.yaml").write_text(
        yaml.safe_dump(task.model_dump(exclude_none=True), sort_keys=False)
    )
    return task.name
