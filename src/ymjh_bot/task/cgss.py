"""
茶馆说书任务 - Python DSL 实现
"""

from pathlib import Path
from dslBot import GameTask, step, StepJumpException

# 获取模板目录的绝对路径
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class ChaguanTask(GameTask):
    """一梦江湖茶馆说书任务。"""
    task_key = "cgss"
    task_name = "茶馆说书"
    task_description = "茶馆说书任务"
    # 配置
    design_resolution = (1280, 720)
    loop_count = 1
    ocr_enabled = True

    # 模板路径常量 (使用绝对路径)
    BTN_CLOSE = str(TEMPLATES_DIR / "btn_close.png")
    BTN_PANE_CLOSE = str(TEMPLATES_DIR / "btn_pane_close.png")
    BTN_HD = str(TEMPLATES_DIR / "btn_HD.png")
    BTN_JRCG = str(TEMPLATES_DIR / "btn_JRCG.png")

    ICON_CGSS_COMPLETE = str(TEMPLATES_DIR / "icon_cgss_complete.png")

    TEXT_AUTO_PATH = str(TEMPLATES_DIR / "text_自动寻路.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_HUODONG_JIANGHU = (192, 680)
    POINT_QIANWANG = (270, 590)
    POINT_ANSWER = (1232, 540)

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("茶馆说书任务开始")
        self._log("=" * 40)

    @step(retry=1, timeout_ms=30000)
    def close_all(self) -> None:
        """关闭所有弹窗（循环点击关闭按钮直到全部消失）。"""
        while self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=5000):
            self.click()
            self.wait(500)
        self._log("已关闭所有弹窗")

    @step(retry=3, timeout_ms=30000)
    def open_huodong(self) -> None:
        """打开活动界面。"""
        self.wait_image_appear(self.BTN_HD, timeout_ms=30000)
        self.click(0)
        self.wait(2000)
        self._log("已打开活动界面")
        self.click_point(self.POINT_HUODONG_JIANGHU[0], self.POINT_HUODONG_JIANGHU[1])
        self._log("已打开活动 - 江湖界面")

        # 条件检查：如果已经检测到 CGSS_COMPLETE 图标，说明已茶馆说书已完成
        if self.wait_image_appear(self.ICON_CGSS_COMPLETE, timeout_ms=2000):
            self._log("检测到茶馆说书已完成，直接结束任务")
            self.jump_to_end()

        self.click_point(self.POINT_QIANWANG[0], self.POINT_QIANWANG[1])
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待自动寻路开始（检测到"自动寻路"文字消失）。"""
        self.wait_image_missing(
            self.TEXT_AUTO_PATH,
            timeout_ms=None,
            threshold=0.8,
            missing_threshold=3,
            callback=lambda missing, count: self._log("自动寻路中..."),
        )

    @step(retry=3, timeout_ms=60000)
    def enter_chaguan(self) -> None:
        """点击进入茶馆（循环点击直到消失）。"""
        self.wait_image_appear(self.BTN_JRCG, callback=lambda found: self.click())
        self.wait_image_missing(self.BTN_JRCG, timeout_ms=30000)

    @step(retry=3, timeout_ms=5000)
    def click_answer(self) -> None:
        """点击回答问题。"""
        while True:
            self.click_point(self.POINT_ANSWER[0], self.POINT_ANSWER[1])
            self.wait(2500)

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"茶馆说书任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
