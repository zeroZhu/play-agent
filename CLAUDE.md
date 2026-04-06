# Project Context

## 项目概述
这是一个游戏自动化机器人项目，支持 YAML 和 Python DSL 两种方式定义任务。

## 架构
- **botCore**: 核心公共组件（ADB、视觉引擎、数据模型）
- **yamlBot**: YAML 任务执行引擎
- **dslBot**: Python DSL 任务系统
- **game_bot**: GUI 和 CLI 入口

## 开发规范
- 使用 `uv` 管理依赖和虚拟环境
- 导入顺序：botCore → yamlBot/dslBot → game_bot
- 新增任务文件放在 `tasks/` 目录
- 模板图片放在 `templates/` 目录

## 常用命令
```bash
# 运行任务
python -m src.game_bot.run --task tasks/xxx.yaml
python -m src.game_bot.run --task tasks/xxx.py

# GUI 启动
python -m src.game_bot.main
```

## 偏好设置
- 响应使用简洁的中文
- 代码修改前先读取文件
- 优先使用 Edit 工具而非重写整个文件
