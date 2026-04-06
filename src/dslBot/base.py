"""
Python DSL for defining game automation tasks.

Usage:
    from dslBot import GameTask, step

    class MyTask(GameTask):
        design_resolution = (1280, 720)
        device_serial = "127.0.0.1:16384"

        @step(retry=3)
        def close_popup(self):
            if self.find_image("btn_close.png"):
                self.click()
                return True
            return False

        @step()
        def do_daily(self):
            self.click_image("btn_start.png")
            self.wait(2)
            if self.find_ocr_text("确认"):
                self.click()
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

from botCore import ADBClient, VisionEngine, RunLogger, ExecutionResult, TaskMeta, TaskSpec
from botCore.coords import apply_random_offset, scale_point, sleep_with_jitter


@runtime_checkable
class StepCallable(Protocol):
    def __call__(self, __self: GameTask) -> Any: ...


def step(
    retry: int = 0,
    timeout_ms: int = 10000,
    enabled: bool = True,
):
    """Decorator to mark a method as a task step.

    Args:
        retry: Number of retries on failure
        timeout_ms: Timeout in milliseconds
        enabled: Whether this step is enabled
    """
    def decorator(func: Callable[[GameTask], Any]) -> StepCallable:
        func._step_meta = {
            "retry": retry,
            "timeout_ms": timeout_ms,
            "enabled": enabled,
        }
        return func
    return decorator


class GameTask:
    """Base class for game automation tasks using Python DSL.

    Class attributes:
        design_resolution: Tuple of (width, height) for design resolution
        device_serial: ADB device serial (can be None for auto-detect)
        adb_path: Path to adb executable (default: "adb")
        ocr_enabled: Whether to enable OCR (default: True)
        ocr_lang: OCR language (default: "ch")
        loop_count: Number of loops (default: 1)

    Example:
        class YmjhTask(GameTask):
            design_resolution = (1280, 720)
            device_serial = "127.0.0.1:16384"

            @step(retry=3)
            def close_all(self):
                while self.find_image("btn_close.png"):
                    self.click()
                    self.wait(0.5)
    """

    # Class-level configuration
    design_resolution: tuple[int, int] = (1280, 720)
    device_serial: str | None = None
    adb_path: str = "adb"
    ocr_enabled: bool = True
    ocr_lang: str = "ch"
    loop_count: int = 1

    # Instance attributes (set at runtime)
    _adb: ADBClient
    _vision: VisionEngine
    _logger: RunLogger | None
    _stop_requested: bool
    _screen_resolution: tuple[int, int] | None

    def __init__(self):
        self._stop_requested = False
        self._screen_resolution = None
        self._last_match_center: tuple[int, int] | None = None
        self._last_match_score: float = 0.0

    @classmethod
    def get_steps(cls) -> list[tuple[str, Callable[[GameTask], Any], dict]]:
        """Get all step methods with their metadata."""
        steps = []
        for name in dir(cls):
            attr = getattr(cls, name)
            if callable(attr) and hasattr(attr, "_step_meta"):
                steps.append((name, attr, attr._step_meta))
        return steps

    @classmethod
    def to_task_spec(cls) -> TaskSpec:
        """Convert DSL task to TaskSpec for execution."""
        spec = TaskSpec(
            meta=TaskMeta(
                name=cls.__name__,
                design_resolution=cls.design_resolution,
                loop_count=cls.loop_count,
            ),
        )
        spec.device.adb_path = cls.adb_path
        spec.device.serial = cls.device_serial
        spec.ocr.enabled = cls.ocr_enabled
        spec.ocr.lang = cls.ocr_lang
        return spec

    def setup(
        self,
        adb: ADBClient,
        vision: VisionEngine,
        logger: RunLogger | None = None,
    ) -> None:
        """Initialize the task with ADB and vision engines."""
        self._adb = adb
        self._vision = vision
        self._logger = logger

    def stop(self) -> None:
        """Request task stop."""
        self._stop_requested = True

    def is_stopped(self) -> bool:
        """Check if stop was requested."""
        return self._stop_requested

    # === ADB Operations ===

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        """Click at specified coordinates or last matched position.

        Args:
            x: X coordinate (uses last match center if None)
            y: Y coordinate (uses last match center if None)
        """
        if x is None or y is None:
            if self._last_match_center:
                x, y = self._last_match_center
            else:
                raise RuntimeError("No position to tap. Provide coordinates or find_image first.")
        self._adb.tap(x, y)
        self._log(f"Clicked at ({x}, {y})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        """Swipe from (x1, y1) to (x2, y2)."""
        self._adb.swipe(x1, y1, x2, y2, duration_ms)
        self._log(f"Swiped ({x1},{y1}) -> ({x2},{y2})")

    def shell(self, command: str) -> str:
        """Execute adb shell command."""
        return self._adb.shell(command)

    def screenshot(self) -> np.ndarray:
        """Take a screenshot."""
        return self._adb.screenshot()

    # === Vision Operations ===

    def find_image(
        self,
        template: str | list[str],
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """Find template image on screen.

        Args:
            template: Template image path or list of paths
            threshold: Match threshold (0.0-1.0)
            roi: Region of interest (x, y, w, h)

        Returns:
            True if found, stores center in _last_match_center
        """
        templates = [template] if isinstance(template, str) else template
        screenshot = self.screenshot()
        match = self._vision.match_template(screenshot, templates, threshold=threshold, roi=roi)
        self._last_match_score = match.score
        if match.found and match.center:
            self._last_match_center = match.center
            self._log(f"Found image: {template} (score={match.score:.3f})")
            return True
        self._last_match_center = None
        self._log(f"Image not found: {template} (score={match.score:.3f})")
        return False

    def find_image_pos(
        self,
        template: str | list[str],
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        """Find template image and return position.

        Returns:
            (x, y) center position or None if not found
        """
        if self.find_image(template, threshold, roi):
            return self._last_match_center
        return None

    def find_ocr_text(
        self,
        query: str,
        exact: bool = False,
        min_confidence: float = 0.55,
    ) -> bool:
        """Find text using OCR.

        Args:
            query: Text to search for
            exact: Exact match required
            min_confidence: Minimum confidence threshold

        Returns:
            True if found, stores center in _last_match_center
        """
        screenshot = self.screenshot()
        match = self._vision.find_text(screenshot, query, exact=exact, min_confidence=min_confidence)
        if match.found and match.center:
            self._last_match_center = match.center
            self._last_match_score = match.confidence
            self._log(f"Found OCR text: '{match.text}' (conf={match.confidence:.2f})")
            return True
        self._last_match_center = None
        self._log(f"OCR text not found: '{query}'")
        return False

    def get_ocr_text(self) -> list[dict[str, Any]]:
        """Get all OCR text from screen.

        Returns:
            List of {text, confidence, bbox, center} dicts
        """
        screenshot = self.screenshot()
        results = self._vision.ocr(screenshot)
        return [
            {
                "text": r.text,
                "confidence": r.confidence,
                "bbox": r.bbox,
                "center": ((r.bbox[0] + r.bbox[2]) // 2, (r.bbox[1] + r.bbox[3]) // 2),
            }
            for r in results
        ]

    # === Combined Operations ===

    def click_image(
        self,
        template: str | list[str],
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
        random_offset: int = 3,
        retry: int = 0,
        timeout_ms: int = 5000,
    ) -> bool:
        """Find and click template image.

        Args:
            template: Template image path(s)
            threshold: Match threshold
            roi: Region of interest
            random_offset: Random offset pixels
            retry: Number of retries
            timeout_ms: Timeout in milliseconds

        Returns:
            True if found and clicked
        """
        start = time.perf_counter()
        attempts = max(1, retry + 1)
        deadline = start + timeout_ms / 1000.0

        while time.perf_counter() < deadline and attempts > 0:
            if self._stop_requested:
                return False
            if self.find_image(template, threshold, roi):
                self.click_with_offset(random_offset)
                return True
            attempts -= 1
            time.sleep(0.2)
        return False

    def click_with_offset(self, offset: int = 3) -> None:
        """Click at last matched position with random offset."""
        if self._last_match_center:
            point = apply_random_offset(self._last_match_center, offset)
            self.tap(point[0], point[1])

    def click_point(
        self,
        x: int,
        y: int,
        random_offset: int = 3,
        design_resolution: tuple[int, int] | None = None,
    ) -> None:
        """Click at specified design-resolution coordinates.

        Args:
            x: X coordinate in design resolution
            y: Y coordinate in design resolution
            random_offset: Random offset pixels
            design_resolution: Override design resolution (uses class default if None)
        """
        if design_resolution is None:
            design_resolution = self.design_resolution

        scaled = scale_point((x, y), design_resolution, self._screen_resolution or design_resolution)
        if random_offset > 0:
            scaled = apply_random_offset(scaled, random_offset)
        self.tap(scaled[0], scaled[1])

    def wait(self, seconds: float, jitter: tuple[int, int] | None = None) -> None:
        """Wait for specified seconds.

        Args:
            seconds: Base wait time
            jitter: Optional (min_ms, max_ms) for random delay
        """
        if jitter:
            sleep_with_jitter(seconds, jitter)
        else:
            time.sleep(seconds)

    def wait_for_image(
        self,
        template: str | list[str],
        timeout_ms: int = 10000,
        threshold: float = 0.8,
    ) -> bool:
        """Wait for image to appear.

        Returns:
            True if image appears within timeout
        """
        start = time.perf_counter()
        deadline = start + timeout_ms / 1000.0

        while time.perf_counter() < deadline:
            if self._stop_requested:
                return False
            if self.find_image(template, threshold):
                return True
            time.sleep(0.3)
        return False

    def wait_for_missing(
        self,
        template: str | list[str],
        timeout_ms: int = 10000,
        threshold: float = 0.8,
        missing_threshold: int = 3,
    ) -> bool:
        """Wait for image to disappear (consecutive missing).

        Args:
            template: Template to watch for disappearance
            timeout_ms: Max wait time
            threshold: Match threshold
            missing_threshold: Consecutive missing count to consider as disappeared

        Returns:
            True if image disappears within timeout
        """
        start = time.perf_counter()
        deadline = start + timeout_ms / 1000.0
        consecutive_missing = 0

        while time.perf_counter() < deadline:
            if self._stop_requested:
                return False
            if not self.find_image(template, threshold):
                consecutive_missing += 1
                if consecutive_missing >= missing_threshold:
                    return True
            else:
                consecutive_missing = 0
            time.sleep(0.5)
        return consecutive_missing >= missing_threshold

    # === Loop Operations ===

    def loop_click_image(
        self,
        template: str | list[str],
        max_count: int = 10,
        interval_seconds: float = 3.0,
        threshold: float = 0.8,
        missing_threshold: int = 3,
    ) -> int:
        """Loop find and click image until it disappears.

        Args:
            template: Template image path(s)
            max_count: Maximum iterations
            interval_seconds: Interval between attempts
            threshold: Match threshold
            missing_threshold: Consecutive missing to stop

        Returns:
            Number of successful clicks
        """
        click_count = 0
        consecutive_missing = 0

        for _ in range(max_count):
            if self._stop_requested:
                break
            if self.find_image(template, threshold):
                consecutive_missing = 0
                self.click_with_offset(3)
                click_count += 1
                self.wait(interval_seconds)
            else:
                consecutive_missing += 1
                if consecutive_missing >= missing_threshold:
                    break
                self.wait(interval_seconds)

        self._log(f"Loop click completed: {click_count} clicks")
        return click_count

    # === Utility ===

    def _log(self, message: str) -> None:
        """Internal log method."""
        if self._logger:
            self._logger.log(message)
        else:
            print(f"[{self.__class__.__name__}] {message}")

    def _get_scaled_point(
        self,
        x: int,
        y: int,
        design_resolution: tuple[int, int] | None = None,
    ) -> tuple[int, int]:
        """Scale point from design resolution to screen resolution."""
        if design_resolution is None:
            design_resolution = self.design_resolution
        return scale_point(
            (x, y),
            design_resolution,
            self._screen_resolution or design_resolution,
        )
