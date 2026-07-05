"""State helpers for the YMJH task queue UI."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, Any] = {
    "adb_path": "adb",
    "serial": "",
    "selected_task_keys": [],
}


def default_state() -> dict[str, Any]:
    """Return a fresh default state dictionary."""
    return deepcopy(DEFAULT_STATE)


def load_state(path: Path) -> dict[str, Any]:
    """Load queue UI state from JSON, falling back to defaults."""
    state = default_state()
    if not path.exists():
        return state

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state

    if not isinstance(data, dict):
        return state

    state.update({key: value for key, value in data.items() if key in state or key == "progress"})
    if not isinstance(state.get("selected_task_keys"), list):
        state["selected_task_keys"] = []
    state["adb_path"] = str(state.get("adb_path") or "adb")
    state["serial"] = str(state.get("serial") or "")

    progress = normalize_progress(state.get("progress"))
    if progress is None:
        state.pop("progress", None)
    else:
        state["progress"] = progress
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Persist queue UI state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = default_state()
    serializable.update({key: value for key, value in state.items() if key in serializable})
    if "progress" in state:
        progress = normalize_progress(state.get("progress"))
        if progress is not None:
            serializable["progress"] = progress
    path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_progress(state: dict[str, Any]) -> dict[str, Any]:
    """Return state with progress removed while preserving queue/settings."""
    updated = deepcopy(state)
    updated.pop("progress", None)
    return updated


def normalize_progress(progress: Any) -> dict[str, int] | None:
    """Normalize progress-like input to the persisted schema."""
    if not isinstance(progress, dict):
        return None
    try:
        task_index = int(progress.get("current_task_index", 0))
        step_index = int(progress.get("current_step_index", 0))
    except (TypeError, ValueError):
        return None
    return {
        "current_task_index": max(0, task_index),
        "current_step_index": max(0, step_index),
    }


def task_keys_from_infos(task_infos: list[dict[str, Any]]) -> list[str]:
    """Extract persisted task keys from selected task info records."""
    keys: list[str] = []
    for task_info in task_infos:
        key = task_info.get("key")
        if key is not None:
            keys.append(str(key))
    return keys


def restore_selected_tasks(
    available_tasks: list[dict[str, Any]],
    selected_task_keys: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Restore selected task records in saved order, skipping missing keys."""
    by_key = {str(task["key"]): task for task in available_tasks if task.get("key") is not None}
    restored: list[dict[str, Any]] = []
    missing: list[str] = []

    for raw_key in selected_task_keys:
        key = str(raw_key)
        task_info = by_key.get(key)
        if task_info is None:
            missing.append(key)
            continue
        restored.append(task_info.copy())

    return restored, missing
