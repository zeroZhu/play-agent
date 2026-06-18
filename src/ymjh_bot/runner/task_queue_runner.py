"""任务队列执行器 - 支持多任务顺序执行和暂停/继续功能。"""

from __future__ import annotations

import time
from typing import Any, Callable

from botCore import ADBClient, VisionEngine, RunLogger, ExecutionResult
from dslBot.base import GameTask, StepJumpException, StepStopException


class TaskQueueRunner:
    """任务队列执行器。

    Usage:
        runner = TaskQueueRunner(task_list, adb, vision, logger)
        runner.run()  # 执行所有任务
        runner.pause()  # 暂停
        runner.resume()  # 继续
        runner.stop()  # 停止
    """

    def __init__(
        self,
        task_list: list[GameTask],
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
    ):
        self.task_list = task_list
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self._stop_requested = False
        self._paused = False

        # 进度跟踪
        self.current_task_index = 0
        self.current_step_index = 0
        self.total_tasks = len(task_list)

    def stop(self) -> None:
        """停止任务队列。"""
        self._stop_requested = True
        for task in self.task_list:
            task.stop()

    def pause(self) -> None:
        """暂停任务队列（保持当前进度）。"""
        self._paused = True
        # 只设置当前正在执行的任务为停止状态（如果有的话）
        if 0 <= self.current_task_index < len(self.task_list):
            self.task_list[self.current_task_index].stop()

    def resume(self) -> None:
        """继续执行任务队列。"""
        self._paused = False
        # 重置当前任务的停止状态，以便继续执行
        if 0 <= self.current_task_index < len(self.task_list):
            self.task_list[self.current_task_index]._stop_requested = False

    def is_paused(self) -> bool:
        """检查是否暂停。"""
        return self._paused

    def run(self) -> list[ExecutionResult]:
        """执行任务队列中的所有任务。

        Returns:
            所有任务的执行结果列表
        """
        self._stop_requested = False
        self._paused = False
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

        all_results: list[ExecutionResult] = []

        while self.current_task_index < self.total_tasks:
            # 检查停止请求
            if self._stop_requested:
                self._emit("任务队列已停止")
                break

            # 检查暂停
            while self._paused:
                if self._stop_requested:
                    break
                time.sleep(0.1)

            task = self.task_list[self.current_task_index]
            task_name = getattr(task, "task_name", task.__class__.__name__)

            self._emit(f">>> 开始执行任务 {self.current_task_index + 1}/{self.total_tasks}: {task_name}")

            # 设置任务运行时依赖
            task._screen_resolution = screen_size
            task.setup(self.adb, self.vision, self.logger, self.event_callback)

            # 执行单个任务
            task_results = self._run_single_task(task)
            all_results.extend(task_results)

            # 任务完成后，更新索引
            self.current_task_index += 1

        # 所有任务完成后
        if self._stop_requested:
            self._emit(f"任务队列已停止，完成 {self.current_task_index}/{self.total_tasks} 个任务")
        else:
            self._emit("任务队列执行完成")

        return all_results

    def _run_single_task(self, task: GameTask) -> list[ExecutionResult]:
        """执行单个任务。

        Args:
            task: 要执行的任务实例

        Returns:
            任务的执行结果列表
        """
        results: list[ExecutionResult] = []
        steps = task.get_steps()
        loop_count = max(1, task.loop_count)
        task_name = getattr(task, "task_name", task.__class__.__name__)

        # 调用 on_start（只在第一次 loop 调用）
        if hasattr(task, "on_start") and self.current_step_index == 0:
            task.on_start()

        for round_idx in range(loop_count):
            if self._stop_requested or self._paused:
                break

            self._emit(f"  Loop {round_idx + 1}/{loop_count}")

            # 从保存的 step_index 继续（支持暂停/继续）
            step_index = self.current_step_index if round_idx == 0 else 0
            while step_index < len(steps):
                if self._stop_requested or self._paused:
                    # 保存当前步骤索引
                    self.current_step_index = step_index
                    break

                step_name, step_func, step_meta = steps[step_index]
                task._current_step_index = step_index

                if not step_meta.get("enabled", True):
                    step_index += 1
                    continue

                result = self._execute_step(step_name, step_func, step_meta)
                results.append(result)

                if self.logger:
                    self.logger.log_step_result(step_name, result)

                self._emit(
                    f"    [{step_name}] {'OK' if result.success else 'FAIL'} - "
                    f"{result.reason} ({result.elapsed_ms} ms)"
                )

                # 检查跳转请求
                if task._jump_target:
                    target = task._jump_target
                    task._jump_target = None

                    if target == StepJumpException.JUMP_TO_END:
                        self._emit(f"    Jump to end of loop")
                        break
                    elif target == StepJumpException.JUMP_TO_START:
                        step_index = 0
                        continue
                    elif target == StepJumpException.JUMP_TO_PREV:
                        step_index = max(0, step_index - 1)
                        continue
                    elif target == StepJumpException.JUMP_TO_NEXT:
                        step_index += 1
                        continue
                    else:
                        found = False
                        for i, (name, _, _) in enumerate(steps):
                            if name == target:
                                step_index = i
                                found = True
                                break
                        if not found:
                            self._emit(f"    WARN: Jump target '{target}' not found")
                        step_index += 1
                        continue

                step_index += 1

                # 应用间隔
                interval_ms = step_meta.get("interval_ms") or task._default_interval_ms
                if interval_ms is not None and interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)

            # 重置 step_index 为 0，以便下一个 loop 从头开始
            if not self._paused and not self._stop_requested:
                self.current_step_index = 0

        # 调用 on_finish
        if hasattr(task, "on_finish") and not self._paused:
            task.on_finish(results)

        return results

    def _execute_step(
        self,
        name: str,
        func: Callable[[GameTask], Any],
        meta: dict,
    ) -> ExecutionResult:
        """执行单个步骤。"""
        start = time.perf_counter()

        retry_raw = meta.get("retry", 0)
        if retry_raw is None or retry_raw == -1:
            attempts = -1
        else:
            attempts = max(1, int(retry_raw) + 1)

        timeout_raw = meta.get("timeout_ms", 10000)
        deadline = None if timeout_raw is None else start + int(timeout_raw) / 1000.0

        last_error: Exception | None = None

        while attempts == -1 or attempts > 0:
            if self._stop_requested or self._paused:
                return ExecutionResult(
                    success=False,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                    reason="Stopped by user",
                )

            if deadline is not None and time.perf_counter() > deadline:
                break

            try:
                result_value = func(self.task_list[self.current_task_index])
                elapsed_ms = int((time.perf_counter() - start) * 1000)

                if result_value is None:
                    return ExecutionResult(
                        success=True,
                        elapsed_ms=elapsed_ms,
                        reason="Completed",
                    )
                elif isinstance(result_value, bool):
                    if result_value:
                        return ExecutionResult(
                            success=True,
                            elapsed_ms=elapsed_ms,
                            reason="Completed",
                        )
                    else:
                        last_error = Exception("Step returned False")
                else:
                    return ExecutionResult(
                        success=True,
                        elapsed_ms=elapsed_ms,
                        reason=f"Completed with result: {result_value}",
                    )

            except StepJumpException as e:
                self.task_list[self.current_task_index]._jump_target = e.target
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return ExecutionResult(
                    success=True,
                    elapsed_ms=elapsed_ms,
                    reason=f"Jump to {e.target}",
                )
            except StepStopException:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return ExecutionResult(
                    success=False,
                    elapsed_ms=elapsed_ms,
                    reason="Stopped by user",
                )
            except Exception as e:
                last_error = e
                self._emit(f"    [{name}] Error: {e}")

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
        """发送事件消息。"""
        if self.event_callback:
            self.event_callback(message)
