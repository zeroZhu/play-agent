from __future__ import annotations

from pathlib import Path

import yaml

from .models import TaskSpec


def _resolve_template_paths(raw: dict, base_dir: Path) -> None:
    """Recursively resolve template paths in step targets to absolute paths."""
    steps = raw.get("steps", []) or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        target = step.get("target", {}) or {}
        templates = target.get("template")
        if templates:
            if isinstance(templates, str):
                target["template"] = str(base_dir / templates)
            elif isinstance(templates, list):
                target["template"] = [str(base_dir / t) for t in templates]


def load_task(path: str | Path) -> TaskSpec:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Task file root must be a mapping.")
    _resolve_template_paths(raw, p.parent)
    return TaskSpec.from_dict(raw)


def save_task(task: TaskSpec, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(task.to_dict(), allow_unicode=True, sort_keys=False)
    p.write_text(text, encoding="utf-8")
