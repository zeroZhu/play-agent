from pathlib import Path
import time

from botCore.vision import load_image
from ymjh_bot.task.start import StartTask
from ymjh_bot.task.bangpai import BangpaiTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class
from ymjh_bot.ym_game_task import LoginState, YmGameTask


GAME_WINDOW = "mCurrentFocus=Window{abc u0 com.netease.wyclx/com.netease.MainActivity}"
HOME_WINDOW = "mCurrentFocus=Window{abc u0 app.lawnchair/app.lawnchair.LawnchairLauncher}"


class ScriptedLoginTask(YmGameTask):
    LOGIN_TOTAL_TIMEOUT_MS = 500
    LOGIN_LOADING_TIMEOUT_MS = 50
    LOGIN_CLEANUP_TIMEOUT_MS = 200
    LOGIN_POLL_INTERVAL_MS = 10
    LOGIN_WAIT_AFTER_CLICK_MS = 10
    LOGIN_WAIT_AFTER_CLOSE_MS = 10

    def __init__(
        self,
        states: list[str | None] | None = None,
        *,
        process_output: str = "",
        window_output: str = GAME_WINDOW,
        window_error: bool = False,
    ):
        super().__init__()
        self.states = states or []
        self.state_index = 0
        self.process_output = process_output
        self.window_output = window_output
        self.window_error = window_error
        self.shell_calls: list[str] = []
        self.detect_calls: list[tuple[bool, float]] = []
        self.taps: list[str | None] = []
        self.waits: list[int | float] = []
        self.logs: list[str] = []

    def shell(self, command: str) -> str:
        self.shell_calls.append(command)
        if command.startswith("pidof "):
            return self.process_output
        if command == "dumpsys window":
            if self.window_error:
                raise RuntimeError("dumpsys failed")
            return self.window_output
        return ""

    def detect_login_state(
        self,
        *,
        include_modal_controls: bool = False,
        threshold: float = 0.8,
    ) -> LoginState | None:
        self.detect_calls.append((include_modal_controls, threshold))
        state = self._current_state()
        if state is None:
            return None
        return LoginState(
            name=state,
            description=state,
            score=1.0,
            center=(100, 100),
            template_path=f"{state}.png",
        )

    def tap(self, x=None, y=None):
        state = self._current_state()
        self.taps.append(state)
        if state in {
            self.LOGIN_STATE_NOTICE,
            self.LOGIN_STATE_LOGIN,
            self.LOGIN_STATE_ROLE_CONFIRM,
            self.LOGIN_STATE_ROLE,
            self.LOGIN_STATE_POPUP,
        }:
            self._advance_state()

    def wait(self, ms):
        self.waits.append(ms)
        if self._current_state() is None and self.state_index < len(self.states) - 1:
            self._advance_state()
            return
        if ms:
            time.sleep(min(float(ms) / 1000.0, 0.01))

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _current_state(self) -> str | None:
        if not self.states:
            return None
        if self.state_index >= len(self.states):
            return self.states[-1]
        return self.states[self.state_index]

    def _advance_state(self) -> None:
        if self.state_index < len(self.states) - 1:
            self.state_index += 1


class FakeTaskPanelTask(ScriptedLoginTask):
    def __init__(self, image_results: list[bool]):
        super().__init__([])
        self.image_results = image_results
        self.wait_image_calls = []
        self.clicked_points = []
        self.wait_calls = []

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.wait_image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)


class HealthScreenshotTask(YmGameTask):
    def __init__(self, screenshot):
        super().__init__()
        self._screenshot = screenshot

    def screenshot(self):
        return self._screenshot


class FakeHealthRecoveryTask(YmGameTask):
    def __init__(self, health_ratios: list[float | None], *, emotion_found: bool = True):
        super().__init__()
        self.health_ratios = health_ratios
        self.emotion_found = emotion_found
        self.actions = []
        self.roi_calls = []
        self.wait_calls = []
        self.logs = []

    def detect_health_ratio(self) -> float | None:
        if not self.health_ratios:
            return None
        if len(self.health_ratios) == 1:
            return self.health_ratios[0]
        return self.health_ratios.pop(0)

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.emotion_found

    def click(self, offset: int = 3) -> None:
        self.actions.append(("click", offset))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_ym_game_task_reports_process_running_from_pid():
    task = ScriptedLoginTask(process_output="1234")

    assert task.is_game_process_running()

    assert task.shell_calls == [f"pidof {task.PACKAGE_NAME}"]


def test_enter_game_runs_full_login_flow_and_cleans_popups():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_NOTICE,
            YmGameTask.LOGIN_STATE_LOGIN,
            None,
            YmGameTask.LOGIN_STATE_ROLE,
            None,
            YmGameTask.LOGIN_STATE_POPUP,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [
        YmGameTask.LOGIN_STATE_NOTICE,
        YmGameTask.LOGIN_STATE_LOGIN,
        YmGameTask.LOGIN_STATE_ROLE,
        YmGameTask.LOGIN_STATE_POPUP,
    ]
    assert "登录流程结束，主界面已清理" in task.logs


def test_enter_game_resumes_from_role_page():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_ROLE,
            None,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [YmGameTask.LOGIN_STATE_ROLE]
    assert "登录流程结束，主界面已清理" in task.logs


def test_enter_game_confirms_online_role_popup():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_LOGIN,
            YmGameTask.LOGIN_STATE_ROLE_CONFIRM,
            None,
            YmGameTask.LOGIN_STATE_ROLE,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [
        YmGameTask.LOGIN_STATE_LOGIN,
        YmGameTask.LOGIN_STATE_ROLE_CONFIRM,
        YmGameTask.LOGIN_STATE_ROLE,
    ]
    assert "登录流程结束，主界面已清理" in task.logs


def test_ym_game_task_skips_launch_when_game_is_foreground_and_clean():
    task = ScriptedLoginTask([YmGameTask.LOGIN_STATE_MAIN], window_output=GAME_WINDOW)

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.taps == []
    assert "检测到游戏已在前台，跳过启动" in task.logs


def test_ym_game_task_cleans_foreground_popup_instead_of_skipping():
    task = ScriptedLoginTask(
        [YmGameTask.LOGIN_STATE_POPUP, YmGameTask.LOGIN_STATE_MAIN],
        window_output=GAME_WINDOW,
    )

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.taps == [YmGameTask.LOGIN_STATE_POPUP]
    assert "检测到游戏在前台但未进入主界面，继续进入游戏" in task.logs


def test_ym_game_task_launches_when_pid_exists_but_foreground_is_home():
    task = ScriptedLoginTask(
        [YmGameTask.LOGIN_STATE_MAIN],
        process_output="1234",
        window_output=HOME_WINDOW,
    )

    assert task.is_game_process_running()
    task.shell_calls.clear()

    task.ensure_game_started()

    assert task.shell_calls == [
        "dumpsys window",
        f"monkey -p {task.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1",
    ]


def test_ym_game_task_launches_when_foreground_cannot_be_parsed():
    task = ScriptedLoginTask([YmGameTask.LOGIN_STATE_MAIN], window_error=True)

    task.ensure_game_started()

    assert task.shell_calls == [
        "dumpsys window",
        f"monkey -p {task.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1",
    ]


def test_enter_game_times_out_when_state_is_never_recognized():
    task = ScriptedLoginTask([None])

    try:
        task.enter_game()
    except RuntimeError as exc:
        assert str(exc) == "登录流程超时：长时间未识别到可操作界面"
    else:
        raise AssertionError("Expected RuntimeError")


def test_start_task_step_metadata_uses_single_long_running_attempt():
    steps = StartTask.get_steps()
    _, _, meta = steps[0]

    assert meta["retry"] == 0
    assert meta["timeout_ms"] == 360000
    assert StartTask.auto_recover_health is False


def test_detect_health_ratio_reads_reference_screenshots():
    root = Path(__file__).resolve().parents[1]

    low_ratio = HealthScreenshotTask(load_image(root / "screenshots" / "1.png")).detect_health_ratio()
    full_ratio = HealthScreenshotTask(load_image(root / "screenshots" / "5.png")).detect_health_ratio()

    assert low_ratio is not None
    assert low_ratio < YmGameTask.HEALTH_RECOVER_THRESHOLD
    assert full_ratio is not None
    assert full_ratio >= YmGameTask.HEALTH_FULL_THRESHOLD


def test_recover_health_if_needed_meditates_until_full():
    task = FakeHealthRecoveryTask([0.79, 0.85, 0.90])

    task.recover_health_if_needed()

    assert task.roi_calls == [
        (task.BTN_BIAOQING, task.ROI_BIAOQING_BUTTON, 3000, "表情按钮", 0.9, 300)
    ]
    assert task.actions == [
        ("click", 0),
        ("point", task.POINT_EMOTION_SINGLE_TAB[0], task.POINT_EMOTION_SINGLE_TAB[1], 0),
        ("point", task.POINT_EMOTION_MEDITATE[0], task.POINT_EMOTION_MEDITATE[1], 0),
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert task.wait_calls == [800, 800, 1000, task.HEALTH_RECOVER_POLL_INTERVAL_MS, 500, 1000]


def test_recover_health_if_needed_skips_when_health_is_not_low():
    task = FakeHealthRecoveryTask([0.80])

    task.recover_health_if_needed()

    assert task.roi_calls == []
    assert task.actions == []


def test_recover_health_if_needed_skips_when_emotion_button_is_missing():
    task = FakeHealthRecoveryTask([0.79], emotion_found=False)

    task.recover_health_if_needed()

    assert task.roi_calls == [
        (task.BTN_BIAOQING, task.ROI_BIAOQING_BUTTON, 3000, "表情按钮", 0.9, 300)
    ]
    assert task.actions == []
    assert "未找到主界面表情按钮，跳过自动打坐" in task.logs


def test_bangpai_task_steps_include_sidebar_execution_after_accept():
    step_names = [name for name, _, _ in BangpaiTask.get_steps()]

    assert step_names == [
        "close_all",
        "resume_existing_task",
        "open_bangpai_activity",
        "start_auto_pathfinding",
        "auto_pathfinding",
        "accept_task",
        "start_accepted_task",
        "run_task_flow",
    ]


def test_hidden_and_abstract_tasks_are_not_visible():
    class VisibleTask(YmGameTask):
        pass

    class HiddenTask(YmGameTask):
        task_visible = False

    assert is_visible_task_class(VisibleTask)
    assert not is_visible_task_class(HiddenTask)
    assert not is_visible_task_class(YmGameTask)


def test_switch_task_panel_switches_when_sidebar_is_already_active():
    task = FakeTaskPanelTask([True, True])

    task.switch_task_panel("江湖")

    assert task.wait_image_calls == [
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_JH, 3000, 0.8),
    ]
    assert task.clicked_points == [(174, 124, 3)]
    assert task.wait_calls == [500]


def test_switch_task_panel_opens_sidebar_when_not_active():
    task = FakeTaskPanelTask([False, True, True])

    task.switch_task_panel("任务")

    assert task.wait_image_calls == [
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_RW, 3000, 0.8),
    ]
    assert task.clicked_points == [
        (22, 160, 3),
        (88, 124, 3),
    ]
    assert task.wait_calls == [500, 500]


def test_switch_task_panel_raises_when_sidebar_cannot_open():
    task = FakeTaskPanelTask([False, False])

    try:
        task.switch_task_panel("奇遇")
    except RuntimeError as exc:
        assert str(exc) == "未能打开任务侧栏"
    else:
        raise AssertionError("Expected RuntimeError")

    assert task.clicked_points == [(22, 160, 3)]


def test_switch_task_panel_rejects_unknown_panel():
    task = FakeTaskPanelTask([])

    try:
        task.switch_task_panel("帮派")
    except ValueError as exc:
        assert str(exc) == "Unsupported task panel: 帮派"
    else:
        raise AssertionError("Expected ValueError")
