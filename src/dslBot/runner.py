"""Executor for Python DSL tasks."""

from __future__ import annotations

import time
from typing import Any, Callable

from task_engine import ADBClient, VisionEngine, RunLogger, ExecutionResult
from .base import GameTask


class DSLTaskRunner:
    """Runner for Python DSL tasks.

    Usage:
        runner = DSLTaskRunner(task_instance, adb, vision, logger)
        results = runner.run()
    """

    def __init__(
        self,
        task: GameTask,
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
    ):
        self.task = task
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self._stop_requested = False

    def stop(self) -> None:
        """Request task stop."""
        self._stop_requested = True
        self.task.stop()

    def run(self) -> list[ExecutionResult]:
        """Execute the DSL task.

        Returns:
            List of execution results for each step
        """
        self._stop_requested = False
        self.adb.ensure_device()

        screen_size = self.adb.get_screen_size()
        self._emit(f"Connected to {self.adb.serial}, resolution={screen_size}")

        # Verify screenshot matches wm size
        test_shot = self.adb.screenshot()
        h, w = test_shot.shape[:2]
        self._emit(f"Screenshot size: {w}x{h}, wm size: {screen_size[0]}x{screen_size[1]}")

        if (w, h) != screen_size:
            self._emit(f"WARNING: Resolution mismatch! Using screenshot size {w}x{h}")
            screen_size = (w, h)

        # Setup task with runtime dependencies
        self.task._screen_resolution = screen_size
        self.task.setup(self.adb, self.vision, self.logger)

        # Call optional lifecycle hooks
        if hasattr(self.task, "on_start"):
            self.task.on_start()

        results: list[ExecutionResult] = []
        steps = self.task.get_steps()
        loop_count = max(1, self.task.loop_count)

        for round_idx in range(loop_count):
            if self._stop_requested:
                break
            self._emit(f"Loop {round_idx + 1}/{loop_count}")

            for step_name, step_func, step_meta in steps:
                if self._stop_requested:
                    break

                if not step_meta.get("enabled", True):
                    continue

                result = self._execute_step(step_name, step_func, step_meta)
                results.append(result)

                if self.logger:
                    self.logger.log_step_result(step_name, result)

                self._emit(
                    f"[{step_name}] {'OK' if result.success else 'FAIL'} - "
                    f"{result.reason} ({result.elapsed_ms} ms)"
                )

        # Call optional finish hook
        if hasattr(self.task, "on_finish"):
            self.task.on_finish(results)

        return results

    def _execute_step(
        self,
        name: str,
        func: Callable[[GameTask], Any],
        meta: dict,
    ) -> ExecutionResult:
        """Execute a single step with retry logic."""
        start = time.perf_counter()
        retry = max(0, int(meta.get("retry", 0)))
        timeout_ms = max(100, int(meta.get("timeout_ms", 10000)))
        deadline = start + timeout_ms / 1000.0

        attempts = max(1, retry + 1) if retry >= 0 else -1  # -1 = infinite
        last_error: Exception | None = None

        while attempts == -1 or attempts > 0:
            if self._stop_requested:
                return ExecutionResult(
                    success=False,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                    reason="Stopped by user",
                )

            if time.perf_counter() > deadline:
                break

            try:
                # Execute the step method
                result_value = func(self.task)
                elapsed_ms = int((time.perf_counter() - start) * 1000)

                # Determine success based on return value
                if result_value is None:
                    # No return value = success
                    return ExecutionResult(
                        success=True,
                        elapsed_ms=elapsed_ms,
                        reason="Completed",
                    )
                elif isinstance(result_value, bool):
                    # Boolean return = explicit success/failure
                    if result_value:
                        return ExecutionResult(
                            success=True,
                            elapsed_ms=elapsed_ms,
                            reason="Completed",
                        )
                    else:
                        last_error = Exception("Step returned False")
                else:
                    # Any other truthy value = success
                    return ExecutionResult(
                        success=True,
                        elapsed_ms=elapsed_ms,
                        reason=f"Completed with result: {result_value}",
                    )

            except Exception as e:
                last_error = e
                self._emit(f"[{name}] Error: {e}")

            # Retry logic
            if attempts > 0:
                attempts -= 1
            time.sleep(0.15)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        reason = str(last_error) if last_error else "Timeout exceeded"
        return ExecutionResult(
            success=False,
            elapsed_ms=elapsed_ms,
            reason=reason,
        )

    def _emit(self, message: str) -> None:
        """Emit event message."""
        if self.event_callback:
            self.event_callback(message)
