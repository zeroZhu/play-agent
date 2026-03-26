from pathlib import Path
from uuid import uuid4

from game_bot.config_io import load_task, save_task
from game_bot.models import StepSpec, TaskSpec


def test_task_roundtrip():
    task = TaskSpec(
        steps=[
            StepSpec(
                id="s1",
                type="wait",
                action={"seconds": 1.2},
            )
        ]
    )
    tmp_dir = Path("logs/test_tmp/config_io") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / "task.yaml"
    save_task(task, path)
    loaded = load_task(path)

    assert loaded.meta.name == task.meta.name
    assert len(loaded.steps) == 1
    assert loaded.steps[0].type == "wait"
    assert loaded.steps[0].action["seconds"] == 1.2
