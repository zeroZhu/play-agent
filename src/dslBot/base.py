"""
Python DSL for defining game automation tasks.

Usage:
    from dslBot import GameTask, step

    class MyTask(GameTask):
        design_resolution = (1280, 720)

        @step(retry=3)
        def close_popup(self):
            if self.find_image("btn_close.png"):
                self.click()
                return True
            return False

        @step()
        def do_daily(self):
            self.wait(2000)
            if self.find_image("btn_start.png", timeout_ms=5000):
                self.click()
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

from botCore import ADBClient, VisionEngine, RunLogger, ExecutionResult, TaskMeta, TaskSpec
from botCore.coords import apply_random_offset, scale_point


class StepJumpException(Exception):
    """Exception raised to jump to a specific step.

    Usage:
        raise StepJumpException("step_name")  # Jump to named step
        raise StepJumpException(StepJumpException.JUMP_TO_START)  # Jump to first step
        raise StepJumpException(StepJumpException.JUMP_TO_END)  # End current loop
        raise StepJumpException(StepJumpException.JUMP_TO_PREV)  # Jump to previous step
        raise StepJumpException(StepJumpException.JUMP_TO_NEXT)  # Continue to next step
    """
    JUMP_TO_START = "__start__"
    JUMP_TO_END = "__end__"
    JUMP_TO_PREV = "__prev__"
    JUMP_TO_NEXT = "__next__"

    def __init__(self, target: str):
        self.target = target
        super().__init__(f"Jump to: {target}")


@runtime_checkable
class StepCallable(Protocol):
    def __call__(self, __self: GameTask) -> Any: ...


def step(
    retry: int | None = 3,
    timeout_ms: int | None = 30000,
    enabled: bool = True,
    interval_ms: int | None = None,
):
    """Decorator to mark a method as a task step.

    Args:
        retry: Number of retries on failure (None for infinite)
        timeout_ms: Timeout in milliseconds (default: 30000, None for no timeout)
        enabled: Whether this step is enabled
        interval_ms: Wait time in milliseconds after step completes (None for no wait)
    """
    def decorator(func: Callable[[GameTask], Any]) -> StepCallable:
        func._step_meta = {
            "retry": retry,
            "timeout_ms": timeout_ms,
            "enabled": enabled,
            "interval_ms": interval_ms,
        }
        return func
    return decorator


class StepStopException(Exception):
    """Raised when stop is requested during a blocking operation."""
    pass


class GameTask:
    """Base class for game automation tasks using Python DSL.

    Class attributes:
        design_resolution: Tuple of (width, height) for design resolution
        loop_count: Number of loops (default: 1)
        ocr_enabled: Whether to enable OCR (default: False)
        ocr_lang: OCR language (default: "ch")

    Example:
        class YmjhTask(GameTask):
            design_resolution = (1280, 720)

            @step(retry=3)
            def close_all(self):
                while self.find_image("btn_close.png"):
                    self.click()
                    self.wait(500)
    """

    # Class-level configuration
    design_resolution: tuple[int, int] = (1280, 720)
    loop_count: int = 1
    ocr_enabled: bool = False
    ocr_lang: str = "ch"

    # Instance attributes (set at runtime)
    _adb: ADBClient
    _vision: VisionEngine
    _logger: RunLogger | None
    _event_callback: Callable[[str], None] | None
    _stop_requested: bool
    _screen_resolution: tuple[int, int] | None
    _jump_target: str | None
    _current_step_index: int

    def __init__(self, default_interval_ms: int | None = None):
        self._stop_requested = False
        self._screen_resolution = None
        self._last_match_center: tuple[int, int] | None = None
        self._last_match_score: float = 0.0
        self._default_interval_ms = default_interval_ms
        self._event_callback: Callable[[str], None] | None = None
        self._jump_target: str | None = None
        self._current_step_index: int = 0

    def setup(
        self,
        adb: ADBClient,
        vision: VisionEngine,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the task with ADB and vision engines."""
        self._adb = adb
        self._vision = vision
        self._logger = logger
        self._event_callback = event_callback

    @classmethod
    def get_steps(cls) -> list[tuple[str, Callable[[GameTask], Any], dict]]:
        """Get all step methods with their metadata in definition order."""
        import inspect
        steps = []

        # Try to get source code to determine method order
        try:
            source = inspect.getsource(cls)
            lines = source.split('\n')
            # Find all @step decorated methods and their line numbers
            step_methods = {}
            for lineno, line in enumerate(lines):
                if '@step' in line:
                    # Next line should be the method definition
                    if lineno + 1 < len(lines) and 'def ' in lines[lineno + 1]:
                        method_name = lines[lineno + 1].split('def ')[1].split('(')[0]
                        step_methods[method_name] = lineno
            # Sort methods by line number
            sorted_methods = sorted(step_methods.keys(), key=lambda x: step_methods[x])
            # Build steps list in order
            for name in sorted_methods:
                attr = getattr(cls, name)
                if callable(attr) and hasattr(attr, "_step_meta"):
                    steps.append((name, attr, attr._step_meta))
            return steps
        except Exception:
            pass

        # Fallback: use __dict__ to preserve definition order (Python 3.7+)
        step_methods = []
        for name, attr in cls.__dict__.items():
            if callable(attr) and hasattr(attr, "_step_meta"):
                step_methods.append((name, attr, attr._step_meta))

        if step_methods:
            return step_methods

        # Last resort: use dir() (order not guaranteed)
        for name in dir(cls):
            attr = getattr(cls, name)
            if callable(attr) and hasattr(attr, "_step_meta"):
                steps.append((name, attr, attr._step_meta))
        return steps

    @classmethod
    def to_task_spec(cls) -> TaskSpec:
        """Convert DSL task to TaskSpec for execution."""
        return TaskSpec(
            meta=TaskMeta(
                name=cls.__name__,
                design_resolution=cls.design_resolution,
                loop_count=cls.loop_count,
            ),
        )

    def stop(self) -> None:
        """Request task stop."""
        self._stop_requested = True

    def is_stopped(self) -> bool:
        """Check if stop was requested."""
        return self._stop_requested

    def jump_to(self, step_name: str) -> None:
        """Jump to a specific step by name.

        Args:
            step_name: Name of the target step
        """
        raise StepJumpException(step_name)

    def jump_to_start(self) -> None:
        """Jump to the first step."""
        raise StepJumpException(StepJumpException.JUMP_TO_START)

    def jump_to_end(self) -> None:
        """Jump to end (finish current loop)."""
        raise StepJumpException(StepJumpException.JUMP_TO_END)

    def jump_to_prev(self) -> None:
        """Jump to previous step."""
        raise StepJumpException(StepJumpException.JUMP_TO_PREV)

    def jump_to_next(self) -> None:
        """Jump to next step (skip remaining logic in current step)."""
        raise StepJumpException(StepJumpException.JUMP_TO_NEXT)

    def get_current_step_name(self) -> str | None:
        """Get the current step name."""
        steps = self.get_steps()
        if 0 <= self._current_step_index < len(steps):
            return steps[self._current_step_index][0]
        return None

    # === ADB Operations ===

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        """Click at specified coordinates or last matched position."""
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

    def wait_image_appear(
        self,
        template: str | list[str],
        timeout_ms: int | None = 10000,
        threshold: float = 0.8,
        callback: Callable[[bool], None] | None = None,
        interval_ms: int = 500,
    ) -> bool:
        """Wait for image to appear.

        Args:
            template: Template image path or list of paths
            timeout_ms: Max wait time in milliseconds (None for infinite)
            threshold: Match threshold (0.0-1.0)
            callback: Optional callback function called with found status after each attempt
            interval_ms: Interval between find attempts in milliseconds (default: 500)

        Returns:
            True if image appears within timeout
        """
        templates = [template] if isinstance(template, str) else template
        start = time.perf_counter()
        deadline = None if timeout_ms is None else start + timeout_ms / 1000.0

        while deadline is None or time.perf_counter() < deadline:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            screenshot = self.screenshot()
            match = self._vision.match_template(screenshot, templates, threshold=threshold)
            self._last_match_score = match.score
            if match.found and match.center:
                self._last_match_center = match.center
                self._log(f"Found image: {template} (score={match.score:.3f})")
                if callback:
                    callback(True)
                return True
            if callback:
                callback(False)
            # Sleep in smaller intervals to respond to stop requests faster
            sleep_interval = min(interval_ms / 1000.0, 0.1)
            time.sleep(sleep_interval)

        self._last_match_center = None
        self._log(f"Image not found: {template} (timeout)")
        if callback:
            callback(False)
        return False

    def wait_image_missing(
        self,
        template: str | list[str],
        timeout_ms: int | None = 10000,
        threshold: float = 0.8,
        missing_threshold: int = 3,
        callback: Callable[[bool, int], None] | None = None,
        interval_ms: int = 500,
    ) -> bool:
        """Wait for image to disappear (consecutive missing).

        Args:
            template: Template to watch for disappearance
            timeout_ms: Max wait time in milliseconds (None for infinite)
            threshold: Match threshold (0.0-1.0)
            missing_threshold: Consecutive missing count to consider as disappeared
            callback: Optional callback function called with (found, missing_count) after each attempt
            interval_ms: Interval between find attempts in milliseconds (default: 500)

        Returns:
            True if image disappears within timeout
        """
        start = time.perf_counter()
        deadline = None if timeout_ms is None else start + timeout_ms / 1000.0
        consecutive_missing = 0

        while deadline is None or time.perf_counter() < deadline:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            found = self.find_image(template, threshold)
            if not found:
                consecutive_missing += 1
                if callback:
                    callback(False, consecutive_missing)
                if consecutive_missing >= missing_threshold:
                    return True
            else:
                consecutive_missing = 0
                if callback:
                    callback(True, consecutive_missing)
            # Sleep in smaller intervals to respond to stop requests faster
            sleep_interval = min(interval_ms / 1000.0, 0.1)
            time.sleep(sleep_interval)
        if callback:
            callback(False, consecutive_missing)
        return consecutive_missing >= missing_threshold

    # === Combined Operations ===

    def click(self, offset: int = 3) -> None:
        """Click at last matched position with random offset.

        Args:
            offset: Random offset in pixels (default: 3)
        """
        if self._last_match_center:
            x, y = apply_random_offset(self._last_match_center, offset)
            self.tap(x, y)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        """Click at specified design-resolution coordinates.

        Args:
            x: X coordinate in design resolution
            y: Y coordinate in design resolution
            offset: Random offset in pixels (default: 3)
        """
        scaled = scale_point((x, y), self.design_resolution, self._screen_resolution or self.design_resolution)
        if offset > 0:
            x, y = apply_random_offset(scaled, offset)
        else:
            x, y = scaled
        self.tap(x, y)

    # === Utility ===

    def wait(self, ms: int | float) -> None:
        """Wait for specified milliseconds."""
        # Sleep in small intervals to check for stop requests
        remaining_ms = int(ms)
        while remaining_ms > 0:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            sleep_time = min(remaining_ms, 50)  # Check every 50ms
            time.sleep(sleep_time / 1000.0)
            remaining_ms -= sleep_time

    def _log(self, message: str) -> None:
        """Internal log method."""
        # Send to GUI via event callback first
        if self._event_callback:
            self._event_callback(f"[{self.__class__.__name__}] {message}")
        # Also log to logger if available
        if self._logger:
            self._logger.log_event({"message": message})
        # Fallback to console
        if not self._event_callback and not self._logger:
            print(f"[{self.__class__.__name__}] {message}")
