# Python DSL 任务开发指南

## 快速开始

### 1. 创建任务文件

在 `tasks/` 目录下创建 Python 文件，例如 `tasks/my_task.py`：

```python
from dslBot import GameTask, step

class MyTask(GameTask):
    """我的自定义任务。"""

    # 配置
    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"
    loop_count = 1

    @step(retry=3, timeout_ms=10000)
    def step_1(self) -> bool:
        """步骤 1：关闭弹窗。"""
        while self.find_image("templates/btn_close.png"):
            self.click()
            self.wait(0.5)
        return True

    @step()
    def step_2(self) -> bool:
        """步骤 2：执行任务。"""
        if self.find_image("templates/btn_start.png"):
            self.click()
            self.wait(2)
            return True
        return False
```

### 2. 运行任务

```bash
# 运行 DSL 任务
python -m src.game_bot.run --task tasks/my_task.py

# 指定设备
python -m src.game_bot.run --task tasks/my_task.py --serial 127.0.0.1:5555
```

## API 参考

### 类属性配置

```python
class MyTask(GameTask):
    design_resolution = (1280, 720)      # 设计分辨率
    device_serial = "127.0.0.1:16384"    # 设备串口
    adb_path = "adb"                     # ADB 路径
    ocr_enabled = True                   # 是否启用 OCR
    ocr_lang = "ch"                      # OCR 语言
    loop_count = 1                       # 循环次数
```

### 装饰器

```python
@step(retry=3, timeout_ms=10000, enabled=True)
def my_step(self) -> bool:
    ...
```

- `retry`: 失败重试次数
- `timeout_ms`: 超时时间（毫秒）
- `enabled`: 是否启用此步骤

### 生命周期钩子

```python
def on_start(self) -> None:
    """任务开始时调用。"""
    self.close_all_popups()

def on_finish(self, results: list) -> None:
    """任务结束时调用。"""
    print(f"完成任务：{sum(1 for r in results if r.success)}/{len(results)}")
```

### 图像操作

```python
# 查找图像
if self.find_image("btn.png", threshold=0.8):
    self.click()

# 获取图像位置
pos = self.find_image_pos("btn.png")
if pos:
    print(f"Found at {pos}")

# 查找并点击
self.click_image("btn.png", retry=3)

# 循环点击直到消失
count = self.loop_click_image(
    "btn_close.png",
    max_count=10,
    interval_seconds=2.0,
)
```

### OCR 操作

```python
# 查找文本
if self.find_ocr_text("开始", min_confidence=0.7):
    self.click()

# 获取所有文本
texts = self.get_ocr_text()
for t in texts:
    print(f"{t['text']} ({t['confidence']:.2f})")
```

### 坐标操作

```python
# 点击设计分辨率坐标
self.click_point(500, 300)

# 点击（使用上次匹配的图像位置）
self.tap()

# 点击指定坐标
self.tap(100, 200)

# 滑动
self.swipe(100, 500, 900, 500)
```

### 等待

```python
# 简单等待
self.wait(2.0)

# 带随机抖动的等待
self.wait(2.0, jitter=(100, 300))

# 等待图像出现
if self.wait_for_image("btn.png", timeout_ms=5000):
    self.click()

# 等待图像消失
self.wait_for_missing("popup.png", missing_threshold=3)
```

## 完整示例

```python
from game_bot.dsl import GameTask, step

class YmjhDailyTask(GameTask):
    """一梦江湖日常任务。"""

    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"
    loop_count = 1

    # 模板路径常量
    CLOSE_BTN = "templates/btn_close.png"
    START_BTN = "templates/btn_start.png"
    OK_BTN = "templates/btn_OK.png"

    def on_start(self) -> None:
        self._log("=== 任务开始 ===")
        self.close_all_popups()

    @step(retry=3)
    def close_all_popups(self) -> bool:
        """关闭所有弹窗。"""
        count = 0
        while self.find_image(self.CLOSE_BTN, threshold=0.7):
            self.click_with_offset(3)
            count += 1
            self.wait(0.5)
            if count > 10:
                break
        self._log(f"关闭了 {count} 个弹窗")
        return True

    @step()
    def start_task(self) -> bool:
        """开始任务。"""
        if self.find_image(self.START_BTN):
            self.click()
            self.wait(2)
            return True
        return False

    @step(retry=2, timeout_ms=30000)
    def do_battle(self) -> bool:
        """执行战斗任务。"""
        # 循环点击确认按钮直到消失
        self.loop_click_image(
            self.OK_BTN,
            max_count=10,
            interval_seconds=1.5,
            missing_threshold=3,
        )
        return True

    def on_finish(self, results) -> None:
        success = sum(1 for r in results if r.success)
        self._log(f"=== 任务完成：{success}/{len(results)} ===")
```

## YAML vs DSL 对比

| 特性 | YAML | Python DSL |
|------|------|-----------|
| 上手难度 | 低 | 中 |
| 条件判断 | 有限 | 完整 if/else |
| 循环 | 预设类型 | 任意循环 |
| 变量复用 | 有限 | 完整支持 |
| 调试 | 困难 | 断点/单步 |
| IDE 提示 | 无 | 自动补全 |
| 错误处理 | 无 | try/except |

## 最佳实践

1. **使用常量定义模板路径**
   ```python
   CLOSE_BTN = "templates/btn_close.png"
   ```

2. **复杂逻辑拆分为多个 `@step` 方法**
   ```python
   @step()
   def step1(self): ...

   @step()
   def step2(self): ...
   ```

3. **使用 `self._log()` 记录关键信息**

4. **添加适当的超时和重试**
   ```python
   @step(timeout_ms=30000, retry=3)
   ```

5. **使用生命周期钩子处理初始化和清理**
