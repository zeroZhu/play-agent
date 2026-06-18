"""
一梦江湖启动任务 - Python DSL 实现

原 YAML 文件：src/task/start.yaml
"""

from pathlib import Path
from dslBot import GameTask, step

# 获取模板目录的绝对路径
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class StartTask(GameTask):
    """一梦江湖启动任务。"""
    task_key = "launch"
    task_name = "启动游戏"
    task_description = "启动游戏任务"
    # 配置
    design_resolution = (1280, 720)
    loop_count = 1
    ocr_enabled = True

    # 应用包名
    PACKAGE_NAME = "com.netease.wyclx"
    # 模板路径常量 (使用绝对路径)
    BTN_OK = str(TEMPLATES_DIR / "btn_OK.png")
    BTN_CLOSE = str(TEMPLATES_DIR / "btn_close.png")
    BTN_MODAL_OK = str(TEMPLATES_DIR / "btn_modal_ok.png") 
    
    BTN_ZZDL = str(TEMPLATES_DIR / "btn_ZZDL.png")
    BTN_TRJH = str(TEMPLATES_DIR / "btn_TRJH.png")
    BTN_JRYX = str(TEMPLATES_DIR / "btn_JRYX.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_HUODONG_JIANGHU = (192, 680)
    POINT_KEYE_PANEL = (210, 280)
    POINT_QIANWANG = (276, 500)
    POINT_GET_TASK = (356, 456)

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("一梦江湖启动任务开始")
        self._log("=" * 40)


    @step(retry=1, timeout_ms=60000)
    def start_app(self) -> None:
        """启动一梦江湖游戏。"""
        self._log("启动应用")
        self.shell(f"monkey -p {self.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1")
        self.wait(5000)
        self._log("应用启动完成")


    @step(retry=1, timeout_ms=60000)
    def enter_game(self) -> None:
        """进入游戏主界面。"""
        self._log("进入游戏主界面")
        self.wait_image_appear([self.BTN_ZZDL, self.BTN_TRJH], timeout_ms=None)
        self.wait_image_missing([self.BTN_ZZDL, self.BTN_TRJH], timeout_ms=None, callback=self.tap_missing)
        # 如果有弹框，点击确认\关闭
        self.wait_image_appear(self.BTN_JRYX, timeout_ms=None)
        self.tap()
        if self.wait_image_appear([self.BTN_CLOSE, self.BTN_MODAL_OK], timeout_ms=15000):
            self.wait_image_missing([self.BTN_CLOSE, self.BTN_MODAL_OK], timeout_ms=None, callback=self.tap_missing)

    def tap_missing(self, found: bool, missing_count: int) -> None:
        """点击目标图标。"""
        if found:
            self.tap()
        else:
            self._log(f"未找到点击目标图标 (连续 {missing_count} 次)")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"启动任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
