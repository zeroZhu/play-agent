from ymjh_bot.ui.task_queue_state import (
    clear_progress,
    default_state,
    load_state,
    restore_selected_tasks,
    save_state,
    task_keys_from_infos,
)


def test_task_queue_state_read_write_defaults(tmp_path):
    path = tmp_path / "state.json"

    assert load_state(path) == default_state()

    state = default_state()
    state.update(
        {
            "adb_path": "custom-adb",
            "serial": "127.0.0.1:16416",
            "selected_task_keys": ["launch", "daily"],
            "progress": {"current_task_index": 1, "current_step_index": 2},
        }
    )

    save_state(path, state)

    assert load_state(path) == state


def test_restore_selected_tasks_keeps_saved_order_and_skips_missing():
    available = [
        {"key": "launch", "name": "Launch"},
        {"key": "daily", "name": "Daily"},
        {"key": "guild", "name": "Guild"},
    ]

    restored, missing = restore_selected_tasks(available, ["daily", "missing", "launch"])

    assert task_keys_from_infos(restored) == ["daily", "launch"]
    assert missing == ["missing"]


def test_clear_progress_preserves_queue_order():
    state = default_state()
    state["selected_task_keys"] = ["launch", "daily"]
    state["progress"] = {"current_task_index": 1, "current_step_index": 2}

    cleared = clear_progress(state)

    assert "progress" not in cleared
    assert cleared["selected_task_keys"] == ["launch", "daily"]
