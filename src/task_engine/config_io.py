from __future__ import annotations

import importlib.util
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


def load_dsl_task(path: str | Path) -> type:
    """Load a Python DSL task from a .py file.

    Args:
        path: Path to the Python file containing a GameTask subclass

    Returns:
        The task class (not instance)

    Example:
        task_cls = load_dsl_task("tasks/my_task.py")
        # task_cls is a subclass of GameTask
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"DSL task file not found: {p}")

    # Load the module dynamically
    spec = importlib.util.spec_from_file_location("dsl_task_module", p)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {p}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find the GameTask subclass in the module
    from dslBot.base import GameTask

    for name in dir(module):
        attr = getattr(module, name)
        if isinstance(attr, type) and issubclass(attr, GameTask) and attr is not GameTask:
            return attr

    raise ValueError(f"No GameTask subclass found in {p}")


def load_task_auto(path: str | Path) -> TaskSpec | type:
    """Auto-detect task format and load accordingly.

    - .yaml/.yml files -> load_task() -> TaskSpec
    - .py files -> load_dsl_task() -> GameTask subclass

    Args:
        path: Path to task file

    Returns:
        TaskSpec for YAML, GameTask subclass for Python DSL
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return load_task(p)
    elif suffix == ".py":
        return load_dsl_task(p)
    else:
        raise ValueError(f"Unsupported task file format: {suffix}. Use .yaml or .py")
