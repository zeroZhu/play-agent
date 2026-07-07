from pathlib import Path

import pytest

from botCore import load_task_class
from ymjh_bot.task.HSLJ_task import HuashanLunjianTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeHsljTask(HuashanLunjianTask):
    def __init__(
        self,
        *,
        roi_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        find_once_results: list[bool] | None = None,
        power_saving_results: list[bool] | None = None,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.image_results = image_results or []
        self.find_once_results = find_once_results or []
        self.power_saving_results = power_saving_results or []
        self.roi_calls = []
        self.image_calls = []
        self.find_once_calls = []
        self.open_activity_calls = []
        self.safe_close_panel_calls = []
        self.clicked_points = []
        self.click_offsets = []
        self.refresh_calls = 0
        self.wait_calls = []
        self.logs = []

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
        return self.roi_results.pop(0) if self.roi_results else False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def find_image_once(self, template, *, threshold=0.8, roi=None, log_found=False, log_missing=False):
        self.find_once_calls.append((template, threshold, roi, log_found, log_missing))
        return self.find_once_results.pop(0) if self.find_once_results else False

    def open_activity_panel(
        self,
        category_point=None,
        category_name=None,
        *,
        timeout_ms=30000,
        wait_after_open_ms=2000,
        wait_after_category_ms=0,
    ) -> None:
        self.open_activity_calls.append(
            (
                category_point,
                category_name,
                timeout_ms,
                wait_after_open_ms,
                wait_after_category_ms,
            )
        )

    def close_all_panels_for_hslj(
        self,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 500,
        max_attempts: int | None = None,
    ) -> None:
        self.safe_close_panel_calls.append((timeout_ms, wait_after_click_ms, max_attempts))

    def is_power_saving_mode(self) -> bool:
        if self.power_saving_results:
            return self.power_saving_results.pop(0)
        return False

    def refresh_screen_resolution(self) -> None:
        self.refresh_calls += 1
        self._screen_resolution = self.design_resolution

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class SafeCloseHsljTask(HuashanLunjianTask):
    def __init__(self, *, image_results: list[bool] | None = None):
        super().__init__()
        self.image_results = image_results or []
        self.chat_collapse_calls = []
        self.image_calls = []
        self.click_offsets = []
        self.wait_calls = []
        self.logs = []

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        self.chat_collapse_calls.append(wait_after_click_ms)
        return False

    def close_purchase_dialog_if_needed(self) -> bool:
        return False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class OneVOneFlowTask(HuashanLunjianTask):
    def __init__(
        self,
        *,
        complete: bool | None = None,
        complete_results: list[bool] | None = None,
        hslj_settings: dict | None = None,
        stop_after_matches: int | None = None,
    ):
        super().__init__(hslj_settings=hslj_settings)
        if complete_results is None and complete is not None:
            complete_results = [complete]
        self.complete_results = complete_results or []
        self.stop_after_matches = stop_after_matches
        self.ready_calls = []
        self.selected_modes = []
        self.match_clicks = 0
        self.battle_calls = []
        self.logs = []

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        self.ready_calls.append((mode, timeout_ms))

    def select_hslj_mode(self, mode: str) -> None:
        self.selected_modes.append(mode)

    def is_1v1_complete(self) -> bool:
        return self.complete_results.pop(0) if self.complete_results else False

    def click_match_button(self) -> None:
        self.match_clicks += 1

    def run_match_battle(self, mode: str, match_index: int) -> None:
        self.battle_calls.append((mode, match_index))
        if self.stop_after_matches and match_index >= self.stop_after_matches:
            self.stop()

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ThreeVThreeLoopTask(HuashanLunjianTask):
    def __init__(
        self,
        *,
        lunjian_count: int = HuashanLunjianTask.DEFAULT_LUNJIAN_COUNT,
        lunjian_infinite: bool = False,
        hslj_settings: dict | None = None,
        complete_results: list[bool] | None = None,
        stop_after_matches: int | None = None,
    ):
        super().__init__(
            lunjian_count=lunjian_count,
            lunjian_infinite=lunjian_infinite,
            hslj_settings=hslj_settings,
        )
        self.complete_results = complete_results or []
        self.stop_after_matches = stop_after_matches
        self.ready_calls = []
        self.selected_modes = []
        self.match_clicks = 0
        self.battle_calls = []
        self.logs = []

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        self.ready_calls.append((mode, timeout_ms))

    def select_hslj_mode(self, mode: str) -> None:
        self.selected_modes.append(mode)

    def is_3v3_complete(self) -> bool:
        return self.complete_results.pop(0) if self.complete_results else False

    def click_match_button(self) -> None:
        self.match_clicks += 1

    def run_match_battle(self, mode: str, match_index: int) -> None:
        self.battle_calls.append((mode, match_index))
        if self.stop_after_matches and match_index >= self.stop_after_matches:
            self.stop()

    def _log(self, message: str) -> None:
        self.logs.append(message)


class BattleFlowHsljTask(FakeHsljTask):
    def __init__(
        self,
        *,
        result_visible_results: list[bool],
        panel_visible_results: list[bool] | None = None,
        ready_states: list[str] | None = None,
    ):
        super().__init__(roi_results=[True, True, True])
        self.result_visible_results = result_visible_results
        self.panel_visible_results = panel_visible_results or []
        self.ready_states = ready_states or [self.MATCH_READY_STATE_READY]
        self.auto_battle_calls = []

    def click_ready_button(self, mode: str, match_index: int) -> str:
        state = self.ready_states.pop(0)
        if state == self.MATCH_READY_STATE_READY:
            self.roi_calls.append(
                (
                    self.BTN_HSLJ_READY,
                    self.ROI_READY_BUTTON,
                    self.MATCH_READY_TIMEOUT_MS,
                    "华山论剑准备按钮",
                    0.85,
                    self.MATCH_WAIT_POLL_INTERVAL_MS,
                )
            )
            self.click_offsets.append(0)
            self.wait_calls.append(1000)
        return state

    def is_result_panel_visible(self) -> bool:
        return self.result_visible_results.pop(0)

    def is_hslj_panel_visible(self) -> bool:
        if self.panel_visible_results:
            return self.panel_visible_results.pop(0)
        return False

    def auto_battle(self, skill_pages: int = 2, repeat_count: int = 3, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append((skill_pages, repeat_count, interval_ms))


class ReadyWaitHsljTask(HuashanLunjianTask):
    def __init__(
        self,
        *,
        confirm_results: list[bool] | None = None,
        ready_results: list[bool] | None = None,
        result_results: list[bool] | None = None,
        panel_results: list[bool] | None = None,
        complete_1v1_results: list[bool] | None = None,
        complete_3v3_results: list[bool] | None = None,
        match_button_results: list[bool] | None = None,
    ):
        super().__init__()
        self.confirm_results = confirm_results or []
        self.ready_results = ready_results or []
        self.result_results = result_results or []
        self.panel_results = panel_results or []
        self.complete_1v1_results = complete_1v1_results or []
        self.complete_3v3_results = complete_3v3_results or []
        self.match_button_results = match_button_results or []
        self.wait_calls = []
        self.click_offsets = []
        self.debug_prefixes = []
        self.logs = []

    def confirm_match_leave_team_dialog_if_needed(self, activity_name: str, **kwargs) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else False

    def is_ready_button_visible(self) -> bool:
        return self.ready_results.pop(0) if self.ready_results else False

    def is_result_panel_visible_quiet(self) -> bool:
        return self.result_results.pop(0) if self.result_results else False

    def is_hslj_panel_visible_quiet(self) -> bool:
        return self.panel_results.pop(0) if self.panel_results else False

    def is_1v1_complete_quiet(self) -> bool:
        return self.complete_1v1_results.pop(0) if self.complete_1v1_results else False

    def is_3v3_complete_quiet(self) -> bool:
        return self.complete_3v3_results.pop(0) if self.complete_3v3_results else False

    def is_match_button_visible_quiet(self) -> bool:
        return self.match_button_results.pop(0) if self.match_button_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        self.debug_prefixes.append(prefix)
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_hslj_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/HSLJ_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "HuashanLunjianTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "HSLJ"
    assert task_cls.task_name == "华山论剑"


def test_hslj_step_order():
    steps = [name for name, _, _ in HuashanLunjianTask.get_steps()]

    assert steps == [
        "close_all",
        "open_fenzheng_activity",
        "open_1v1_panel",
        "complete_1v1",
        "claim_1v1_first_win",
        "switch_to_3v3",
        "complete_3v3_matches",
        "final_cleanup",
    ]


def test_hslj_safe_close_panels_collapses_chat_before_and_after():
    task = SafeCloseHsljTask(image_results=[False])

    task.close_all_panels_for_hslj()

    assert task.chat_collapse_calls == [800, 800]
    assert task.image_calls == [
        ([task.BTN_CLOSE, task.BTN_PANE_CLOSE, task.BTN_WELCOME_CLOSE], 5000, 0.8)
    ]
    assert task.click_offsets == []
    assert "已关闭所有弹窗" in task.logs


def test_open_fenzheng_activity_uses_fenzheng_tab_point():
    task = FakeHsljTask()

    task.open_fenzheng_activity()

    assert task.open_activity_calls == [
        (task.POINT_HUODONG_FENZHENG, "纷争", 30000, 2500, 1500),
    ]


def test_open_1v1_panel_clicks_activity_icon_open_button_and_verifies_panel():
    task = FakeHsljTask(roi_results=[True, True, True])

    task.open_1v1_panel()

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_ACTIVITY_1V1,
            task.ROI_ACTIVITY_HSLJ_CARD,
            5000,
            "活动页华山论剑卡片",
            0.85,
            500,
        ),
        (
            task.BTN_HSLJ_ACTIVITY_OPEN,
            task.ROI_ACTIVITY_HSLJ_OPEN,
            5000,
            "活动页华山论剑打开按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            5000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.clicked_points == [(task.POINT_ACTIVITY_HSLJ_ICON[0], task.POINT_ACTIVITY_HSLJ_ICON[1], 0)]
    assert task.click_offsets == [0]
    assert task.wait_calls == [1000, 2000]


def test_switch_to_3v3_clicks_panel_tab_and_verifies_panel():
    task = FakeHsljTask(roi_results=[True, False, True])

    task.switch_to_3v3()

    assert task.roi_calls == [
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            10000,
            "华山论剑面板",
            0.85,
            500,
        ),
        (
            task.TAB_HSLJ_3V3_ACTIVE,
            task.ROI_SIDE_TABS,
            800,
            "3v3已选中页签",
            0.85,
            300,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            5000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.clicked_points == [(task.POINT_TAB_3V3[0], task.POINT_TAB_3V3[1], 0)]
    assert task.wait_calls == [1500]


def test_complete_1v1_skips_matching_when_already_complete():
    task = OneVOneFlowTask(complete=True)

    task.complete_1v1()

    assert task.ready_calls == [("1v1", 10000)]
    assert task.selected_modes == ["1v1"]
    assert task.match_clicks == 0
    assert task.battle_calls == []
    assert "检测到华山论剑 1v1 已完成，跳过匹配" in task.logs


def test_complete_1v1_matches_once_when_not_complete():
    task = OneVOneFlowTask(complete_results=[False, True])

    task.complete_1v1()

    assert task.ready_calls == [("1v1", 10000)]
    assert task.selected_modes == ["1v1"]
    assert task.match_clicks == 1
    assert task.battle_calls == [("1v1", 1)]


def test_complete_1v1_fixed_count_runs_configured_matches():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "fixed_count", "count": 2},
            "3v3": {"strategy": "fixed_count", "count": 5},
        }
    )

    task.complete_1v1()

    assert task.match_clicks == 2
    assert task.battle_calls == [("1v1", 1), ("1v1", 2)]


def test_complete_1v1_infinite_runs_until_stopped():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "infinite", "count": 5},
            "3v3": {"strategy": "fixed_count", "count": 5},
        },
        stop_after_matches=3,
    )

    task.complete_1v1()

    assert task.match_clicks == 3
    assert task.battle_calls == [("1v1", 1), ("1v1", 2), ("1v1", 3)]


def test_hslj_click_match_confirms_leave_team_dialog():
    task = FakeHsljTask(roi_results=[False], find_once_results=[True])

    task.click_match_button()

    assert task.clicked_points == [(task.POINT_HSLJ_MATCH[0], task.POINT_HSLJ_MATCH[1], 0)]
    assert task.find_once_calls == [
        (
            task.BTN_MODAL_OK,
            0.85,
            task.scale_roi(task.ROI_CENTER_MODAL_OK),
            False,
            False,
        )
    ]
    assert task.click_offsets == [0]
    assert task.wait_calls == [task.MATCH_SETTLE_WAIT_MS, 1200]
    assert "检测到华山论剑单人匹配退队确认，点击确定" in task.logs


def test_hslj_ready_wait_returns_when_1v1_completed_on_panel():
    task = ReadyWaitHsljTask(
        panel_results=[True],
        complete_1v1_results=[True],
    )

    state = task.click_ready_button("1v1", 1)

    assert state == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.click_offsets == []
    assert task.wait_calls == []
    assert "华山论剑 1v1 第 1 场已完成并返回面板" in task.logs


def test_hslj_ready_wait_times_out_with_debug_screenshot():
    task = ReadyWaitHsljTask()
    task.MATCH_READY_TIMEOUT_MS = 0

    with pytest.raises(RuntimeError, match="匹配/准备等待超时"):
        task.click_ready_button("3v3", 2)

    assert task.debug_prefixes == ["hslj_3v3_2_match_ready_timeout"]


def test_claim_1v1_first_win_attempts_chest_click_after_completed_match():
    task = FakeHsljTask(roi_results=[True, True, True, True], image_results=[True, False])

    task.claim_1v1_first_win()

    assert task.roi_calls == [
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            10000,
            "华山论剑面板",
            0.85,
            500,
        ),
        (
            task.TAB_HSLJ_1V1_ACTIVE,
            task.ROI_SIDE_TABS,
            800,
            "1v1已选中页签",
            0.85,
            300,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            5000,
            "华山论剑面板",
            0.85,
            500,
        ),
        (
            task.ICON_HSLJ_FIRST_WIN_CHEST,
            task.ROI_FIRST_WIN_CHEST,
            3000,
            "华山论剑 1v1 首胜宝箱",
            0.85,
            500,
        ),
    ]
    assert task.clicked_points == [(task.POINT_TAB_1V1[0], task.POINT_TAB_1V1[1], 0)]
    assert task.click_offsets == [0, 0]
    assert task.wait_calls == [1500, 1500, 1000]


def test_3v3_loop_runs_default_five_matches():
    task = ThreeVThreeLoopTask()

    task.complete_3v3_matches()

    assert task.ready_calls == [("3v3", 10000)]
    assert task.selected_modes == ["3v3"]
    assert task.match_clicks == task.DEFAULT_LUNJIAN_COUNT
    assert task.battle_calls == [("3v3", index) for index in range(1, 6)]


def test_3v3_loop_uses_configured_match_count():
    task = ThreeVThreeLoopTask(lunjian_count=3)

    task.complete_3v3_matches()

    assert task.match_clicks == 3
    assert task.battle_calls == [("3v3", 1), ("3v3", 2), ("3v3", 3)]


def test_3v3_loop_infinite_runs_until_stopped():
    task = ThreeVThreeLoopTask(lunjian_count=2, lunjian_infinite=True, stop_after_matches=3)

    task.complete_3v3_matches()

    assert task.match_clicks == 3
    assert task.battle_calls == [("3v3", 1), ("3v3", 2), ("3v3", 3)]


def test_3v3_first_win_runs_until_completion_marker():
    task = ThreeVThreeLoopTask(
        hslj_settings={
            "1v1": {"strategy": "first_win", "count": 5},
            "3v3": {"strategy": "first_win", "count": 5},
        },
        complete_results=[False, True],
    )

    task.complete_3v3_matches()

    assert task.match_clicks == 1
    assert task.battle_calls == [("3v3", 1)]
    assert "检测到华山论剑 3v3 首胜/次数已完成" in task.logs


def test_run_match_battle_clicks_ready_battles_and_exits_result_panel():
    task = BattleFlowHsljTask(result_visible_results=[False, True], panel_visible_results=[False])

    task.run_match_battle("1v1", 1)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_READY,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "华山论剑准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.BTN_HSLJ_RESULT_EXIT,
            task.ROI_RESULT_EXIT_BUTTON,
            10000,
            "华山论剑结果面板退出按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            30000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0, 0]
    assert task.auto_battle_calls == [(1, 1, task.AUTO_BATTLE_INTERVAL_MS)]
    assert task.wait_calls == [1000, 3000]


def test_run_match_battle_stops_auto_battle_when_panel_has_returned():
    task = BattleFlowHsljTask(result_visible_results=[False, False], panel_visible_results=[False, True])

    task.run_match_battle("3v3", 1)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_READY,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "华山论剑准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            30000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.auto_battle_calls == [(1, 1, task.AUTO_BATTLE_INTERVAL_MS)]
    assert task.wait_calls == [1000]
