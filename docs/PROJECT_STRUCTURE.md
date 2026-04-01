# 项目结构说明

## 目录结构

```
src/
├── task_engine/          # 任务执行引擎（YAML 任务核心）
│   ├── __init__.py       # 包入口，导出所有公共 API
│   ├── models.py         # 数据模型：TaskSpec, StepSpec, ExecutionResult
│   ├── adb_client.py     # ADB 客户端：ADBClient
│   ├── vision.py         # 视觉引擎：VisionEngine（模板匹配、OCR）
│   ├── coords.py         # 坐标工具：缩放、随机偏移
│   ├── logger.py         # 运行日志：RunLogger
│   ├── runner.py         # 任务执行器：TaskRunner
│   └── config_io.py      # 配置 IO：加载/保存 YAML，DSL 任务加载
│
├── dslBot/               # Python DSL 任务系统
│   ├── __init__.py       # 包入口：GameTask, step
│   ├── base.py           # DSL 基类：GameTask（丰富的 API）
│   └── runner.py         # DSL 执行器：DSLTaskRunner
│
├── game_bot/             # GUI 和入口
│   ├── __init__.py
│   ├── main.py           # GUI 入口
│   ├── run.py            # CLI 入口（支持 YAML 和 DSL）
│   └── ui/
│       ├── __init__.py
│       └── main_window.py  # 主窗口（任务编辑、运行）
│
├── mobile_v2/            # 移动端相关（独立）
└── ymjh_bot/             # 一梦江湖机器人（独立）

tasks/                    # 任务定义目录
├── *.yaml                # YAML 格式任务
└── *.py                  # Python DSL 格式任务

templates/                # 模板图片目录
docs/                     # 文档
```

## 模块职责

### task_engine（任务引擎）
**核心功能**：提供 YAML 任务执行的所有核心组件
- **models**: 任务、步骤、结果的数据模型
- **adb_client**: ADB 设备连接和操作
- **vision**: 图像识别（模板匹配、OCR）
- **runner**: YAML 任务解释执行器
- **config_io**: YAML 加载/保存

**使用场景**：编写 YAML 配置文件，适合简单、线性的任务流程

### dslBot（DSL 任务）
**核心功能**：提供 Python DSL 任务定义和执行
- **base**: GameTask 基类，提供丰富的任务 API
  - 图像操作：`find_image()`, `click_image()`, `loop_click_image()`
  - OCR 操作：`find_ocr_text()`, `get_ocr_text()`
  - 控制操作：`tap()`, `swipe()`, `wait()`, `wait_for_image()`
- **runner**: DSL 任务执行器，支持 `@step` 装饰器

**使用场景**：编写 Python 类，适合复杂逻辑、条件分支、循环任务

### game_bot（GUI/CLI 入口）
**核心功能**：用户界面和任务运行入口
- **main.py**: GUI 应用入口
- **run.py**: CLI 运行器（支持 YAML 和 DSL）
- **ui/main_window.py**: 任务编辑器 GUI

## 使用示例

### YAML 任务
```yaml
# tasks/my_task.yaml
meta:
  name: "我的任务"
  design_resolution: [1280, 720]

device:
  adb_path: adb
  serial: 127.0.0.1:16384

steps:
  - id: click_start
    type: find_image_click
    target:
      template: "templates/btn_start.png"
    retry: 3
```

```bash
python -m src.game_bot.run --task tasks/my_task.yaml
```

### Python DSL 任务
```python
# tasks/my_task.py
from dslBot import GameTask, step

class MyTask(GameTask):
    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"

    @step(retry=3)
    def click_start(self) -> bool:
        if self.find_image("templates/btn_start.png"):
            self.click()
            return True
        return False

    @step()
    def do_battle(self) -> bool:
        self.loop_click_image("templates/btn_attack.png", max_count=10)
        return True
```

```bash
python -m src.game_bot.run --task tasks/my_task.py
```

## 依赖关系

```
task_engine  ← 基础引擎（无依赖）
    ↑
dslBot     ← DSL 层（依赖 task_engine）
    ↑
game_bot   ← 用户界面（依赖 task_engine, dslBot）
```

## 迁移指南

### 从旧结构迁移
旧文件 → 新位置：

- `game_bot/models.py` → `task_engine/models.py`
- `game_bot/adb_client.py` → `task_engine/adb_client.py`
- `game_bot/vision.py` → `task_engine/vision.py`
- `game_bot/runner.py` → `task_engine/runner.py`
- `game_bot/config_io.py` → `task_engine/config_io.py`
- `game_bot/logger.py` → `task_engine/logger.py`
- `game_bot/coords.py` → `task_engine/coords.py`
- `game_bot/dsl/` → `dslBot/`

### 导入路径更新
旧导入：
```python
from game_bot.models import TaskSpec
from game_bot.adb_client import ADBClient
from game_bot.dsl import GameTask
```

新导入：
```python
from task_engine import TaskSpec, ADBClient
from dslBot import GameTask
```
