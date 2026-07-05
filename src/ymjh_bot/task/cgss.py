"""
茶馆说书任务 - Python DSL 实现
"""

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class ChaguanTask(YmGameTask):
    """一梦江湖茶馆说书任务。"""

    task_key = "cgss"
    task_name = "茶馆说书"
    task_description = "茶馆说书任务"

    BTN_JRCG = str(YmGameTask.TEMPLATES_DIR / "btn_JRCG.png")

    ICON_CGSS_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "icon_cgss_complete.png")

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
        self.close_all_panels()

    @step(retry=3, timeout_ms=30000)
    def open_huodong(self) -> None:
        """打开活动界面。"""
        self.open_activity_panel(self.POINT_HUODONG_JIANGHU, "江湖")

        # 条件检查：如果已经检测到 CGSS_COMPLETE 图标，说明已茶馆说书已完成
        if self.wait_image_appear(self.ICON_CGSS_COMPLETE, timeout_ms=2000):
            self._log("检测到茶馆说书已完成，直接结束任务")
            self.jump_to_end()

        self.click_point(self.POINT_QIANWANG[0], self.POINT_QIANWANG[1])
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待自动寻路开始（检测到"自动寻路"文字消失）。"""
        self.wait_auto_pathfinding()

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
