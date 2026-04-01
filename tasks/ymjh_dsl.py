"""
一梦江湖日常任务 - Python DSL 示例

使用方法：
    python -m src.game_bot.main --dsl tasks/ymjh_dsl.py
"""

from dslBot import GameTask, step


class YmjhDailyTask(GameTask):
    """一梦江湖日常任务 DSL 实现。"""

    # 配置
    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"
    adb_path = "adb"
    loop_count = 1

    # 模板路径常量
    CLOSE_BTN = "templates/btn_close.png"
    BUY_BTN = "templates/btn_buy.png"
    OK_BTN = "templates/btn_OK.png"

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("一梦江湖日常任务开始")
        self._log("=" * 40)
        self.close_all_popups()

    @step(retry=3, timeout_ms=15000)
    def close_all_popups(self) -> bool:
        """关闭所有弹窗。"""
        count = 0
        while self.find_image(self.CLOSE_BTN, threshold=0.7):
            self.click_with_offset(3)
            count += 1
            self.wait(0.5)
            if count > 10:  # 防止死循环
                break
        self._log(f"关闭了 {count} 个弹窗")
        return True

    @step(retry=2, timeout_ms=10000)
    def check_daily_entry(self) -> bool:
        """检查日常任务入口。"""
        if self.find_image(self.BUY_BTN, threshold=0.8):
            self.click_with_offset(5)
            self.wait(2)
            return True

        # 尝试备用方案：OCR 查找"活动"按钮
        if self.find_ocr_text("活动", min_confidence=0.7):
            self.click_with_offset(3)
            self.wait(2)
            return True

        self._log("未找到任务入口")
        return False

    @step(retry=3, timeout_ms=30000)
    def do_task(self) -> bool:
        """执行日常任务。"""
        # 循环点击直到按钮消失
        click_count = self.loop_click_image(
            self.OK_BTN,
            max_count=10,
            interval_seconds=2.0,
            missing_threshold=3,
        )
        self._log(f"完成任务，点击了 {click_count} 次")
        return click_count > 0

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)


# 也可以定义多个任务类
class YmjhWeekendTask(GameTask):
    """一梦江湖周末活动任务。"""

    design_resolution = (1280, 720)
    loop_count = 2

    @step()
    def weekend_bonus(self) -> bool:
        """周末双倍奖励。"""
        self._log("周末活动任务...")
        # TODO: 实现具体逻辑
        return True
