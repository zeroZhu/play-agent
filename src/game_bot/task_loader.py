from __future__ import annotations

from pathlib import Path

from botCore import GameTask, load_task_class, load_task_instance


def load_task_definition(path: str | Path) -> type[GameTask]:
    """Load a Python DSL task class for development debugging."""
    p = Path(path)
    if p.suffix.lower() != ".py":
        raise ValueError(f"Unsupported task file format: {p.suffix}. Use .py")
    return load_task_class(p)


def load_task_for_gui(path: str | Path) -> GameTask:
    """Load a Python DSL task instance for development debugging GUI."""
    p = Path(path)
    if p.suffix.lower() != ".py":
        raise ValueError(f"Unsupported task file format: {p.suffix}. Use .py")
    return load_task_instance(p)
