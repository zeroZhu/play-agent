import numpy as np

from botCore import DSLTaskRunner, GameTask, step
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner


class FakeADB:
    serial = "fake"

    def ensure_device(self):
        return None

    def get_screen_size(self):
        return 1280, 720

    def screenshot(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class FakeVision:
    pass


class JumpTask(GameTask):
    calls: list[str]

    def __init__(self):
        super().__init__()
        self.calls = []

    @step(retry=0)
    def first(self):
        self.calls.append("first")
        self.jump_to("target")

    @step(retry=0)
    def skipped(self):
        self.calls.append("skipped")

    @step(retry=0)
    def target(self):
        self.calls.append("target")


def test_dsl_named_jump_executes_target_step():
    task = JumpTask()
    runner = DSLTaskRunner(
        task,
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
    )

    results = runner.run()

    assert [r.success for r in results] == [True, True]
    assert task.calls == ["first", "target"]


def test_queue_named_jump_executes_target_step():
    task = JumpTask()
    runner = TaskQueueRunner(
        [task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
    )

    results = runner.run()

    assert [r.success for r in results] == [True, True]
    assert task.calls == ["first", "target"]
