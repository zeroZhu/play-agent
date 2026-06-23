from pathlib import Path

import pytest

from botCore import GameTask, load_task_class, load_task_instance, step
from game_bot.task_loader import load_task_definition, load_task_for_gui


def test_bot_core_loads_python_task_class_and_instance(tmp_path):
    task_file = tmp_path / "demo_task.py"
    task_file.write_text(
        "\n".join(
            [
                "from botCore import GameTask, step",
                "",
                "class DemoTask(GameTask):",
                "    @step(retry=0)",
                "    def run_once(self):",
                "        return True",
            ]
        ),
        encoding="utf-8",
    )

    task_cls = load_task_class(task_file)
    task_instance = load_task_instance(task_file)

    assert issubclass(task_cls, GameTask)
    assert isinstance(task_instance, GameTask)
    assert task_cls.get_steps()[0][0] == "run_once"


def test_dev_task_loader_rejects_yaml(tmp_path):
    task_file = tmp_path / "legacy.yaml"
    task_file.write_text("steps: []", encoding="utf-8")

    with pytest.raises(ValueError, match="Use .py"):
        load_task_definition(task_file)

    with pytest.raises(ValueError, match="Use .py"):
        load_task_for_gui(task_file)
