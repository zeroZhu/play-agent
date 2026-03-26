from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from .adb_client import ADBClient
from .coords import apply_random_offset, scale_point, sleep_with_jitter
from .logger import RunLogger
from .models import ExecutionResult, StepSpec, TaskSpec
from .vision import VisionEngine


class TaskRunner:
    def __init__(
        self,
        task: TaskSpec,
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.task = task
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self._stop_requested = False
        self._loop_counters: dict[str, int] = {}
        self._step_index = {step.id: i for i, step in enumerate(task.steps)}
        self._screen_resolution: tuple[int, int] | None = None

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> list[ExecutionResult]:
        self._stop_requested = False
        self.adb.ensure_device()
        self._screen_resolution = self.adb.get_screen_size()
        self._emit(f"Connected to {self.adb.serial}, resolution={self._screen_resolution}")

        results: list[ExecutionResult] = []
        loop_count = max(1, self.task.meta.loop_count)
        for round_idx in range(loop_count):
            if self._stop_requested:
                break
            self._emit(f"Loop {round_idx + 1}/{loop_count}")
            cursor = 0
            while cursor < len(self.task.steps):
                if self._stop_requested:
                    break
                step = self.task.steps[cursor]
                if not step.enabled:
                    cursor += 1
                    continue
                result, next_index = self._execute_with_retry(step)
                results.append(result)
                if self.logger:
                    self.logger.log_step_result(step.id, result)
                self._emit(
                    f"[{step.id}] {'OK' if result.success else 'FAIL'} - "
                    f"{result.reason} ({result.elapsed_ms} ms)"
                )
                if not result.success and step.type != "conditional":
                    # Keep moving, but surface failures clearly in logs.
                    pass
                cursor = cursor + 1 if next_index is None else next_index
        return results

    def _execute_with_retry(self, step: StepSpec) -> tuple[ExecutionResult, int | None]:
        start = time.perf_counter()
        attempts = max(1, step.retry + 1)
        deadline = start + max(0.1, step.timeout_ms / 1000.0)
        last_result = ExecutionResult(
            success=False,
            elapsed_ms=0,
            reason="Not executed",
            screenshot_path=None,
        )
        next_index: int | None = None
        for _ in range(attempts):
            if self._stop_requested:
                break
            if time.perf_counter() > deadline:
                break
            last_result, next_index = self._execute_once(step)
            if last_result.success:
                break
            time.sleep(0.15)
        total_ms = int((time.perf_counter() - start) * 1000)
        last_result.elapsed_ms = total_ms
        return last_result, next_index

    def _execute_once(self, step: StepSpec) -> tuple[ExecutionResult, int | None]:
        if step.type == "find_image_click":
            return self._step_find_image_click(step), None
        if step.type == "find_text_click":
            return self._step_find_text_click(step), None
        if step.type == "drag":
            return self._step_drag(step), None
        if step.type == "wait":
            return self._step_wait(step), None
        if step.type == "loop":
            return self._step_loop(step)
        if step.type == "conditional":
            return self._step_conditional(step), None
        return (
            ExecutionResult(
                success=False,
                elapsed_ms=0,
                reason=f"Unsupported step type: {step.type}",
                screenshot_path=None,
            ),
            None,
        )

    def _step_find_image_click(self, step: StepSpec) -> ExecutionResult:
        screenshot = self.adb.screenshot()
        templates = step.target.get("template")
        if isinstance(templates, str):
            template_paths = [templates]
        elif isinstance(templates, list):
            template_paths = [str(x) for x in templates]
        else:
            return ExecutionResult(False, 0, "target.template is required", None)

        roi = step.target.get("roi")
        roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None

        match = self.vision.match_template(
            screenshot,
            template_paths,
            threshold=step.threshold,
            roi=roi_tuple,
        )
        if not match.found or not match.center:
            return self._result_with_shot(
                screenshot,
                step,
                success=False,
                reason=f"Image not found(score={match.score:.3f})",
            )

        jitter = int(step.action.get("random_offset_px", 0))
        point = apply_random_offset(match.center, jitter)
        self.adb.tap(point[0], point[1])
        self._post_action_delay(step)
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"Clicked image(score={match.score:.3f})",
            point=point,
        )

    def _step_find_text_click(self, step: StepSpec) -> ExecutionResult:
        screenshot = self.adb.screenshot()
        query = str(step.target.get("text", "")).strip()
        if not query:
            return ExecutionResult(False, 0, "target.text is required", None)
        exact = bool(step.target.get("exact", False))
        min_conf = float(step.target.get("min_confidence", self.task.ocr.min_confidence))
        match = self.vision.find_text(
            screenshot,
            query,
            exact=exact,
            min_confidence=min_conf,
        )
        if not match.found or not match.center:
            return self._result_with_shot(
                screenshot,
                step,
                success=False,
                reason=f"Text not found({query})",
            )
        jitter = int(step.action.get("random_offset_px", 0))
        point = apply_random_offset(match.center, jitter)
        self.adb.tap(point[0], point[1])
        self._post_action_delay(step)
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"Clicked text({match.text}, conf={match.confidence:.2f})",
            point=point,
        )

    def _step_drag(self, step: StepSpec) -> ExecutionResult:
        self._require_resolution()
        action = step.action
        p1 = action.get("from")
        p2 = action.get("to")
        if not (isinstance(p1, list) and len(p1) == 2 and isinstance(p2, list) and len(p2) == 2):
            return ExecutionResult(False, 0, "drag action requires from/to", None)
        src = scale_point(
            (int(p1[0]), int(p1[1])),
            self.task.meta.design_resolution,
            self._screen_resolution,  # type: ignore[arg-type]
        )
        dst = scale_point(
            (int(p2[0]), int(p2[1])),
            self.task.meta.design_resolution,
            self._screen_resolution,  # type: ignore[arg-type]
        )
        jitter = int(action.get("random_offset_px", 0))
        src = apply_random_offset(src, jitter)
        dst = apply_random_offset(dst, jitter)
        duration_ms = int(action.get("duration_ms", 450))
        self.adb.swipe(src[0], src[1], dst[0], dst[1], duration_ms)
        screenshot = self.adb.screenshot()
        self._post_action_delay(step)
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"Dragged {src}->{dst}",
            point=dst,
        )

    def _step_wait(self, step: StepSpec) -> ExecutionResult:
        seconds = float(step.action.get("seconds", 1.0))
        sleep_with_jitter(seconds, self._delay_range_from_action(step))
        return ExecutionResult(True, 0, f"Waited {seconds:.2f}s", None)

    def _step_loop(self, step: StepSpec) -> tuple[ExecutionResult, int | None]:
        target_id = str(step.target.get("step_id", "")).strip()
        if not target_id:
            return ExecutionResult(False, 0, "loop target.step_id is required", None), None
        if target_id not in self._step_index:
            return (
                ExecutionResult(False, 0, f"loop step_id not found: {target_id}", None),
                None,
            )
        times = int(step.action.get("times", 1))
        current = self._loop_counters.get(step.id, 0)
        if times < 0 or current < times:
            self._loop_counters[step.id] = current + 1
            return (
                ExecutionResult(
                    True,
                    0,
                    f"Loop jump to {target_id} ({self._loop_counters[step.id]}/{times})",
                    None,
                ),
                self._step_index[target_id],
            )
        self._loop_counters[step.id] = 0
        return ExecutionResult(True, 0, "Loop completed", None), None

    def _step_conditional(self, step: StepSpec) -> ExecutionResult:
        screenshot = self.adb.screenshot()
        mode = str(step.target.get("mode", "text")).strip()
        matched = False
        center: tuple[int, int] | None = None
        if mode == "image":
            templates = step.target.get("template")
            template_paths = [templates] if isinstance(templates, str) else templates
            if not template_paths:
                return ExecutionResult(False, 0, "conditional image missing template", None)
            match = self.vision.match_template(
                screenshot,
                [str(x) for x in template_paths],
                threshold=step.threshold,
            )
            matched = bool(match.found)
            center = match.center
        else:
            query = str(step.target.get("text", "")).strip()
            min_conf = float(step.target.get("min_confidence", self.task.ocr.min_confidence))
            exact = bool(step.target.get("exact", False))
            match = self.vision.find_text(
                screenshot,
                query,
                exact=exact,
                min_confidence=min_conf,
            )
            matched = bool(match.found)
            center = match.center

        branch = step.action.get("on_true" if matched else "on_false")
        if not isinstance(branch, dict):
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Conditional matched={matched}, no branch action",
                point=center,
            )

        branch_type = str(branch.get("type", "noop")).strip().lower()
        if branch_type == "tap":
            point = self._resolve_branch_tap_point(branch, center)
            if point is None:
                return ExecutionResult(False, 0, "conditional tap missing coordinates", None)
            jitter = int(step.action.get("random_offset_px", 0))
            point = apply_random_offset(point, jitter)
            self.adb.tap(point[0], point[1])
            self._post_action_delay(step)
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Conditional tap matched={matched}",
                point=point,
            )
        if branch_type == "swipe":
            self._require_resolution()
            src = branch.get("from")
            dst = branch.get("to")
            if not (isinstance(src, list) and isinstance(dst, list) and len(src) == 2 and len(dst) == 2):
                return ExecutionResult(False, 0, "conditional swipe missing from/to", None)
            p1 = scale_point(
                (int(src[0]), int(src[1])),
                self.task.meta.design_resolution,
                self._screen_resolution,  # type: ignore[arg-type]
            )
            p2 = scale_point(
                (int(dst[0]), int(dst[1])),
                self.task.meta.design_resolution,
                self._screen_resolution,  # type: ignore[arg-type]
            )
            duration_ms = int(branch.get("duration_ms", 400))
            self.adb.swipe(p1[0], p1[1], p2[0], p2[1], duration_ms)
            self._post_action_delay(step)
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Conditional swipe matched={matched}",
                point=p2,
            )
        if branch_type == "wait":
            seconds = float(branch.get("seconds", 0.5))
            time.sleep(max(0.0, seconds))
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Conditional wait({seconds}s), matched={matched}",
                point=center,
            )
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"Conditional noop, matched={matched}",
            point=center,
        )

    def _resolve_branch_tap_point(
        self,
        branch: dict[str, Any],
        matched_center: tuple[int, int] | None,
    ) -> tuple[int, int] | None:
        use_match = bool(branch.get("use_match_center", True))
        if use_match and matched_center:
            return matched_center
        x = branch.get("x")
        y = branch.get("y")
        if x is None or y is None:
            return None
        self._require_resolution()
        return scale_point(
            (int(x), int(y)),
            self.task.meta.design_resolution,
            self._screen_resolution,  # type: ignore[arg-type]
        )

    def _delay_range_from_action(self, step: StepSpec) -> tuple[int, int]:
        raw = step.action.get("random_delay_ms")
        if isinstance(raw, list) and len(raw) == 2:
            return int(raw[0]), int(raw[1])
        return self.task.meta.random_delay_ms

    def _post_action_delay(self, step: StepSpec) -> None:
        sleep_with_jitter(0.0, self._delay_range_from_action(step))

    def _result_with_shot(
        self,
        screenshot: np.ndarray,
        step: StepSpec,
        *,
        success: bool,
        reason: str,
        point: tuple[int, int] | None = None,
    ) -> ExecutionResult:
        shot_path = None
        if self.logger:
            shot_path = self.logger.save_annotated(
                screenshot,
                point=point,
                label=f"{step.id}: {'OK' if success else 'FAIL'}",
            )
        return ExecutionResult(success=success, elapsed_ms=0, reason=reason, screenshot_path=shot_path)

    def _require_resolution(self) -> None:
        if self._screen_resolution is None:
            raise RuntimeError("Screen resolution not initialized.")

    def _emit(self, message: str) -> None:
        if self.event_callback:
            self.event_callback(message)
