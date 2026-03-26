from __future__ import annotations

from pathlib import Path

import yaml

from .models import TaskSpec


def load_task(path: str | Path) -> TaskSpec:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Task file root must be a mapping.")
    return TaskSpec.from_dict(raw)


def save_task(task: TaskSpec, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(task.to_dict(), allow_unicode=True, sort_keys=False)
    p.write_text(text, encoding="utf-8")
