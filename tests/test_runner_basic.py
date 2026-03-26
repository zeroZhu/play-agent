import numpy as np

from game_bot.models import StepSpec, TaskSpec
from game_bot.runner import TaskRunner
from game_bot.vision import ImageMatchResult, TextMatchResult


class FakeADB:
    def __init__(self):
        self.serial = "fake"
        self.taps: list[tuple[int, int]] = []
        self.swipes: list[tuple[int, int, int, int, int]] = []

    def ensure_device(self):
        return None

    def get_screen_size(self):
        return 1920, 1080

    def screenshot(self):
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def tap(self, x, y):
        self.taps.append((x, y))

    def swipe(self, x1, y1, x2, y2, duration_ms):
        self.swipes.append((x1, y1, x2, y2, duration_ms))


class FakeVision:
    def match_template(self, *_args, **_kwargs):
        return ImageMatchResult(
            found=True,
            score=0.97,
            center=(960, 540),
            bbox=(900, 500, 1020, 580),
            template_path="demo.png",
        )

    def find_text(self, *_args, **_kwargs):
        return TextMatchResult(
            found=True,
            text="开始",
            confidence=0.9,
            center=(1000, 550),
            bbox=[[0, 0], [1, 0], [1, 1], [0, 1]],
        )


def test_runner_execute_core_steps():
    task = TaskSpec(
        steps=[
            StepSpec(id="img", type="find_image_click", target={"template": "a.png"}),
            StepSpec(id="txt", type="find_text_click", target={"text": "开始"}),
            StepSpec(
                id="drag",
                type="drag",
                action={"from": [1280, 720], "to": [640, 360], "duration_ms": 300},
            ),
            StepSpec(id="w", type="wait", action={"seconds": 0.0}),
        ]
    )
    adb = FakeADB()
    runner = TaskRunner(task=task, adb_client=adb, vision=FakeVision())
    results = runner.run()

    assert len(results) == 4
    assert all(x.success for x in results)
    assert len(adb.taps) == 2
    # Drag coordinates should scale from design(1280x720) to 1920x1080.
    assert adb.swipes[0][:4] == (1920, 1080, 960, 540)
