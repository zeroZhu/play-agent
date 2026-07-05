from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .task import GameTask


def load_task_class(path: str | Path) -> type[GameTask]:
    """Load the first GameTask subclass from a Python file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"DSL task file not found: {p}")

    module_name = f"bot_task_{p.stem}_{abs(hash(p.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, p)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {p}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for attr in module.__dict__.values():
        if (
            isinstance(attr, type)
            and issubclass(attr, GameTask)
            and attr is not GameTask
            and attr.__module__ == module.__name__
            and not attr.__dict__.get("__abstract_task__", False)
        ):
            return attr

    raise ValueError(f"No GameTask subclass found in {p}")


def load_task_instance(path: str | Path) -> GameTask:
    """Load and instantiate the first GameTask subclass from a Python file."""
    return load_task_class(path)()
