from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from botCore import ADBClient, VisionEngine, RunLogger, ExecutionResult, StepSpec, TaskSpec
from botCore.coords import apply_random_offset, scale_point, sleep_with_jitter


class YamlRunner:
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

        # 验证截图尺寸是否与 wm size 一致
        test_shot = self.adb.screenshot()
        h, w = test_shot.shape[:2]
        self._emit(f"Screenshot size: {w}x{h}, wm size: {self._screen_resolution[0]}x{self._screen_resolution[1]}")
        if (w, h) != self._screen_resolution:
            self._emit(f"WARNING: Resolution mismatch! Using screenshot size {w}x{h} for coordinate scaling")
            self._screen_resolution = (w, h)

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
        attempts = max(1, step.retry + 1) if step.retry >= 0 else -1  # -1 means infinite
        deadline = start + max(0.1, step.timeout_ms / 1000.0)
        last_result = ExecutionResult(
            success=False,
            elapsed_ms=0,
            reason="Not executed",
            screenshot_path=None,
        )
        next_index: int | None = None
        while attempts == -1 or attempts > 0:
            if self._stop_requested:
                break
            if time.perf_counter() > deadline:
                break
            last_result, next_index = self._execute_once(step)
            if last_result.success:
                break
            time.sleep(0.15)
            if attempts > 0:
                attempts -= 1
        total_ms = int((time.perf_counter() - start) * 1000)
        last_result.elapsed_ms = total_ms
        return last_result, next_index

    def _execute_once(self, step: StepSpec) -> tuple[ExecutionResult, int | None]:
        match step.type:
            case "find_image_click":
                return self._step_find_image_click(step), None
            case "find_image_loop":
                return self._step_find_image_loop(step), None
            case "find_image_loop_until_missing":
                return self._step_find_image_loop_until_missing(step), None
            case "find_image_loop_with_action":
                return self._step_find_image_loop_with_action(step), None
            case "find_text_click":
                return self._step_find_text_click(step), None
            case "find_text_loop":
                return self._step_find_text_loop(step), None
            case "drag":
                return self._step_drag(step), None
            case "wait":
                return self._step_wait(step), None
            case "loop":
                return self._step_loop(step)
            case "conditional":
                return self._step_conditional(step), None
            case "switch_case":
                return self._step_switch_case(step), None
            case "start_app":
                return self._step_start_app(step), None
            case "click_point":
                return self._step_click_point(step), None
            case _:
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

    def _step_find_image_loop(self, step: StepSpec) -> ExecutionResult:
        """循环找图直到找到"""
        templates = step.target.get("template")
        if isinstance(templates, str):
            template_paths = [templates]
        elif isinstance(templates, list):
            template_paths = [str(x) for x in templates]
        else:
            return ExecutionResult(False, 0, "target.template is required", None)

        roi = step.target.get("roi")
        roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None
        should_click = bool(step.action.get("click", False))
        interval_seconds = float(step.action.get("interval_seconds", 5.0))

        screenshot = self.adb.screenshot()
        match = self.vision.match_template(
            screenshot,
            template_paths,
            threshold=step.threshold,
            roi=roi_tuple,
        )

        if match.found and match.center:
            if should_click:
                jitter = int(step.action.get("random_offset_px", 0))
                point = apply_random_offset(match.center, jitter)
                self.adb.tap(point[0], point[1])
                self._post_action_delay(step)
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Found image(score={match.score:.3f})",
                point=match.center if should_click else None,
            )

        # 未找到，等待间隔时间后返回失败，让重试机制继续尝试
        time.sleep(interval_seconds)
        return self._result_with_shot(
            screenshot,
            step,
            success=False,
            reason=f"Image not found(score={match.score:.3f}), retrying after {interval_seconds}s",
        )

    def _step_find_image_loop_until_missing(self, step: StepSpec) -> ExecutionResult:
        """循环找图并点击，直到连续 N 次找不到才停止"""
        templates = step.target.get("template")
        if isinstance(templates, str):
            template_paths = [templates]
        elif isinstance(templates, list):
            template_paths = [str(x) for x in templates]
        else:
            return ExecutionResult(False, 0, "target.template is required", None)

        roi = step.target.get("roi")
        roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None
        should_click = bool(step.action.get("click", False))
        interval_seconds = float(step.action.get("interval_seconds", 3.0))
        # 连续失败次数阈值，默认 3 次
        missing_threshold = int(step.action.get("missing_threshold", 3))

        consecutive_missing = 0
        found_count = 0

        while consecutive_missing < missing_threshold:
            if self._stop_requested:
                break

            screenshot = self.adb.screenshot()
            match = self.vision.match_template(
                screenshot,
                template_paths,
                threshold=step.threshold,
                roi=roi_tuple,
            )

            if match.found and match.center:
                consecutive_missing = 0  # 重置计数器
                found_count += 1
                if should_click:
                    jitter = int(step.action.get("random_offset_px", 0))
                    point = apply_random_offset(match.center, jitter)
                    self.adb.tap(point[0], point[1])
                    self._post_action_delay(step)
            else:
                consecutive_missing += 1
                if consecutive_missing < missing_threshold:
                    # 还没到阈值，继续等待
                    time.sleep(interval_seconds)

        reason = (
            f"Image disappeared after {found_count} finds"
            if found_count > 0
            else "Image not found"
        )
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"{reason} (consecutive_missing={consecutive_missing})",
        )

    def _step_find_image_loop_with_action(self, step: StepSpec) -> ExecutionResult:
        """
        循环找图，找不到时执行备选操作，直到找到目标或达到最大尝试次数

        action 配置:
          - on_missing: 找不到时执行的操作类型 ("click_template", "click_point", "swipe", "wait")
          - template: 要点击的模板图片路径 (on_missing=click_template 时需要)
          - point: 要点击的坐标 [x, y] (on_missing=click_point 时需要)
          - from/to: 滑动起止坐标 (on_missing=swipe 时需要)
          - seconds: 等待秒数 (on_missing=wait 时需要)
          - interval_seconds: 每次尝试的间隔
          - max_attempts: 最大尝试次数 (-1 表示无限)
        """
        templates = step.target.get("template")
        if isinstance(templates, str):
            template_paths = [templates]
        elif isinstance(templates, list):
            template_paths = [str(x) for x in templates]
        else:
            return ExecutionResult(False, 0, "target.template is required", None)

        roi = step.target.get("roi")
        roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None
        should_click_target = bool(step.action.get("click", False))
        interval_seconds = float(step.action.get("interval_seconds", 3.0))
        max_attempts = int(step.action.get("max_attempts", -1))

        on_missing = str(step.action.get("on_missing", "")).strip()
        if not on_missing:
            return ExecutionResult(False, 0, "action.on_missing is required", None)

        attempt = 0
        screenshot = self.adb.screenshot()

        while max_attempts < 0 or attempt < max_attempts:
            if self._stop_requested:
                break

            match = self.vision.match_template(
                screenshot,
                template_paths,
                threshold=step.threshold,
                roi=roi_tuple,
            )

            if match.found and match.center:
                if should_click_target:
                    jitter = int(step.action.get("random_offset_px", 0))
                    point = apply_random_offset(match.center, jitter)
                    self.adb.tap(point[0], point[1])
                    self._post_action_delay(step)
                return self._result_with_shot(
                    screenshot,
                    step,
                    success=True,
                    reason=f"Found target after {attempt} attempts (score={match.score:.3f})",
                    point=match.center if should_click_target else None,
                )

            # 没找到，执行备选操作
            attempt += 1
            self._execute_on_missing_action(step, on_missing)
            time.sleep(interval_seconds)
            screenshot = self.adb.screenshot()

        return self._result_with_shot(
            screenshot,
            step,
            success=False,
            reason=f"Target not found after {attempt} attempts",
        )

    def _execute_on_missing_action(self, step: StepSpec, on_missing: str) -> None:
        """执行备选操作"""
        match on_missing:
            case "click_template":
                template = step.action.get("template")
                if not template:
                    print(f"[on_missing] click_template: no template specified")
                    return
                roi = step.action.get("template_roi")
                roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None
                match = self.vision.match_template(
                    self.adb.screenshot(),
                    [template],
                    threshold=step.threshold,
                    roi=roi_tuple,
                )
                if match.found and match.center:
                    jitter = int(step.action.get("random_offset_px", 0))
                    point = apply_random_offset(match.center, jitter)
                    self.adb.tap(point[0], point[1])
                    print(f"[on_missing] clicked template (score={match.score:.3f})")
                else:
                    print(f"[on_missing] template not found, skipping")

            case "click_point":
                point = step.action.get("point")
                if not (isinstance(point, list) and len(point) == 2):
                    print(f"[on_missing] click_point: invalid point")
                    return
                x, y = int(point[0]), int(point[1])
                scaled = scale_point((x, y), self.task.meta.design_resolution, self._screen_resolution)
                self.adb.tap(scaled[0], scaled[1])
                print(f"[on_missing] clicked point ({x},{y}) -> ({scaled[0]},{scaled[1]})")

            case "swipe":
                self._require_resolution()
                p1 = step.action.get("from")
                p2 = step.action.get("to")
                if not (isinstance(p1, list) and len(p1) == 2 and isinstance(p2, list) and len(p2) == 2):
                    print(f"[on_missing] swipe: invalid from/to")
                    return
                src = scale_point((int(p1[0]), int(p1[1])), self.task.meta.design_resolution, self._screen_resolution)
                dst = scale_point((int(p2[0]), int(p2[1])), self.task.meta.design_resolution, self._screen_resolution)
                duration_ms = int(step.action.get("duration_ms", 400))
                self.adb.swipe(src[0], src[1], dst[0], dst[1], duration_ms)
                print(f"[on_missing] swiped {src} -> {dst}")

            case "wait":
                seconds = float(step.action.get("seconds", 1.0))
                time.sleep(seconds)
                print(f"[on_missing] waited {seconds}s")

            case _:
                print(f"[on_missing] unknown action type: {on_missing}")

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

    def _step_find_text_loop(self, step: StepSpec) -> ExecutionResult:
        """循环查找文本直到找到并点击"""
        query = str(step.target.get("text", "")).strip()
        if not query:
            return ExecutionResult(False, 0, "target.text is required", None)
        exact = bool(step.target.get("exact", False))
        min_conf = float(step.target.get("min_confidence", self.task.ocr.min_confidence))
        should_click = bool(step.action.get("click", True))
        interval_seconds = float(step.action.get("interval_seconds", 5.0))

        screenshot = self.adb.screenshot()
        match = self.vision.find_text(
            screenshot,
            query,
            exact=exact,
            min_confidence=min_conf,
        )
        if match.found and match.center:
            if should_click:
                jitter = int(step.action.get("random_offset_px", 0))
                point = apply_random_offset(match.center, jitter)
                self.adb.tap(point[0], point[1])
                self._post_action_delay(step)
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Found text({match.text}, conf={match.confidence:.2f})",
                point=match.center if should_click else None,
            )

        # 文本未找到，等待间隔时间后返回失败，让重试机制继续尝试
        time.sleep(interval_seconds)
        return self._result_with_shot(
            screenshot,
            step,
            success=False,
            reason=f"Text not found({query}), retrying after {interval_seconds}s",
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

    def _step_start_app(self, step: StepSpec) -> ExecutionResult:
        package = str(step.target.get("package", "")).strip()
        if not package:
            return ExecutionResult(False, 0, "start_app requires target.package", None)
        try:
            self.adb.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
            wait_seconds = float(step.action.get("wait_seconds", 3.0))
            sleep_with_jitter(wait_seconds, (int(wait_seconds * 1000), int(wait_seconds * 1500)))
            return ExecutionResult(True, 0, f"Started app {package}", None)
        except Exception as e:
            return ExecutionResult(False, 0, f"Failed to start app: {e}", None)

    def _step_click_point(self, step: StepSpec) -> ExecutionResult:
        """点击指定坐标"""
        self._require_resolution()
        point = step.target.get("point")
        if not (isinstance(point, list) and len(point) == 2):
            return ExecutionResult(False, 0, "click_point requires target.point as [x, y]", None)

        x, y = int(point[0]), int(point[1])
        # 根据设计分辨率缩放坐标
        scaled = scale_point(
            (x, y),
            self.task.meta.design_resolution,
            self._screen_resolution,  # type: ignore[arg-type]
        )

        # 添加随机偏移
        jitter = int(step.action.get("random_offset_px", 0))
        if jitter > 0:
            scaled = apply_random_offset(scaled, jitter)

        self.adb.tap(scaled[0], scaled[1])

        screenshot = self.adb.screenshot()
        self._post_action_delay(step)
        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason=f"Clicked point ({x},{y}) -> ({scaled[0]},{scaled[1]})",
            point=scaled,
        )

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

        # 支持跳转操作
        if branch_type == "jump":
            target_id = str(branch.get("step_id", "")).strip()
            if not target_id:
                return ExecutionResult(False, 0, "conditional jump requires step_id", None)
            if target_id not in self._step_index:
                return ExecutionResult(False, 0, f"conditional jump to unknown step: {target_id}", None)
            return self._result_with_shot(
                screenshot,
                step,
                success=True,
                reason=f"Conditional jump to {target_id} (matched={matched})",
                point=center,
            ), self._step_index[target_id]

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

    def _step_switch_case(self, step: StepSpec) -> tuple[ExecutionResult, int | None]:
        """
        switch-case 风格的多条件分支

        target.cases: 按顺序匹配多个条件
          - mode: "image" | "text"
            template: "xxx.png"    # mode=image 时需要
            text: "xxx"            # mode=text 时需要

        action:
          cases:                   # 每个 case 对应的操作
            - step_id: "xxx"       # 匹配第 0 个 case 时跳转
            - step_id: "yyy"       # 匹配第 1 个 case 时跳转
            - ...
          default:                 # 所有 case 都不匹配时的默认操作
            type: "jump"
            step_id: "default_step"
        """
        screenshot = self.adb.screenshot()
        cases = step.target.get("cases", [])
        if not cases:
            return ExecutionResult(False, 0, "switch_case requires target.cases", None), None

        action_cases = step.action.get("cases", [])
        default_action = step.action.get("default")

        # 按顺序匹配每个 case
        for idx, case in enumerate(cases):
            mode = str(case.get("mode", "image")).strip()
            matched = False

            if mode == "image":
                templates = case.get("template")
                if not templates:
                    continue
                template_paths = [templates] if isinstance(templates, str) else [str(x) for x in templates]
                roi = case.get("roi")
                roi_tuple = tuple(int(v) for v in roi) if isinstance(roi, list) and len(roi) == 4 else None
                match = self.vision.match_template(
                    screenshot,
                    template_paths,
                    threshold=step.threshold,
                    roi=roi_tuple,
                )
                matched = bool(match.found)
            else:
                query = str(case.get("text", "")).strip()
                min_conf = float(case.get("min_confidence", self.task.ocr.min_confidence))
                exact = bool(case.get("exact", False))
                match = self.vision.find_text(
                    screenshot,
                    query,
                    exact=exact,
                    min_confidence=min_conf,
                )
                matched = bool(match.found)

            if matched:
                # 匹配成功，执行对应 case 的操作
                if idx < len(action_cases):
                    branch = action_cases[idx]
                    if isinstance(branch, dict) and branch.get("type") == "jump":
                        target_id = str(branch.get("step_id", "")).strip()
                        if target_id and target_id in self._step_index:
                            return self._result_with_shot(
                                screenshot,
                                step,
                                success=True,
                                reason=f"Switch case {idx} matched, jump to {target_id}",
                            ), self._step_index[target_id]
                # 没有配置对应操作，继续
                return self._result_with_shot(
                    screenshot,
                    step,
                    success=True,
                    reason=f"Switch case {idx} matched",
                ), None

        # 所有 case 都不匹配，执行 default
        if isinstance(default_action, dict):
            if default_action.get("type") == "jump":
                target_id = str(default_action.get("step_id", "")).strip()
                if target_id and target_id in self._step_index:
                    return self._result_with_shot(
                        screenshot,
                        step,
                        success=True,
                        reason=f"Switch default, jump to {target_id}",
                    ), self._step_index[target_id]

        return self._result_with_shot(
            screenshot,
            step,
            success=True,
            reason="Switch default (no jump)",
        ), None

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
