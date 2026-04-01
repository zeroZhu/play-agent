"""
Game Bot CLI - 支持 YAML 和 Python DSL 任务

Usage:
    # 运行 YAML 任务
    python -m src.game_bot.run --task tasks/keye.yaml

    # 运行 Python DSL 任务
    python -m src.game_bot.run --task tasks/ymjh_dsl.py

    # 指定设备
    python -m src.game_bot.run --task tasks/keye.yaml --serial 127.0.0.1:5555
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from task_engine import ADBClient, RunLogger, VisionEngine, TaskSpec, load_task, load_dsl_task
from dslBot.base import GameTask
from dslBot.runner import DSLTaskRunner
from task_engine.runner import TaskRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Game Bot Runner")
    parser.add_argument("--task", "-t", required=True, help="Task file (.yaml or .py)")
    parser.add_argument("--adb", default="adb", help="ADB path")
    parser.add_argument("--serial", "-s", help="Device serial (overrides task config)")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    task_path = Path(args.task)
    if not task_path.exists():
        print(f"Error: Task file not found: {task_path}")
        return 1

    print(f"Loading task: {task_path}")

    try:
        task = load_task_auto(task_path)
    except Exception as e:
        print(f"Error loading task: {e}")
        return 1

    # Determine if it's a DSL task (class) or YAML task (TaskSpec)
    if isinstance(task, type) and issubclass(task, GameTask):
        # Python DSL task
        print(f"Executing Python DSL task: {task.__name__}")

        # Override config from CLI args
        if args.adb:
            task.adb_path = args.adb
        if args.serial:
            task.device_serial = args.serial
        if args.no_ocr:
            task.ocr_enabled = False

        # Create instance and run
        task_instance = task()
        adb = ADBClient(adb_path=task.adb_path, serial=task.device_serial)
        vision = VisionEngine(enable_ocr=task.ocr_enabled, ocr_lang=task.ocr_lang)
        logger = RunLogger()

        runner = DSLTaskRunner(
            task_instance,
            adb,
            vision,
            logger=logger,
            event_callback=lambda msg: print(msg),
        )

        try:
            results = runner.run()
            success_count = sum(1 for r in results if r.success)
            print(f"\nFinished: {success_count}/{len(results)} steps succeeded")
            return 0 if success_count == len(results) else 1
        except KeyboardInterrupt:
            runner.stop()
            print("\nStopped by user")
            return 130
        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1

    elif isinstance(task, TaskSpec):
        # YAML task
        print(f"Executing YAML task: {task.meta.name}")

        # Override config from CLI args
        if args.adb:
            task.device.adb_path = args.adb
        if args.serial:
            task.device.serial = args.serial
        if args.no_ocr:
            task.ocr.enabled = False

        adb = ADBClient(adb_path=task.device.adb_path, serial=task.device.serial)
        vision = VisionEngine(enable_ocr=task.ocr.enabled, ocr_lang=task.ocr.lang)
        logger = RunLogger()

        runner = TaskRunner(
            task,
            adb,
            vision,
            logger=logger,
            event_callback=lambda msg: print(msg),
        )

        try:
            results = runner.run()
            success_count = sum(1 for r in results if r.success)
            print(f"\nFinished: {success_count}/{len(results)} steps succeeded")
            return 0 if success_count == len(results) else 1
        except KeyboardInterrupt:
            runner.stop()
            print("\nStopped by user")
            return 130
        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1

    else:
        print(f"Error: Unknown task type: {type(task)}")
        return 1


def load_task_auto(path: Path) -> TaskSpec | type:
    """Auto-detect task format and load accordingly."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return load_task(path)
    elif suffix == ".py":
        return load_dsl_task(path)
    else:
        raise ValueError(f"Unsupported task file format: {suffix}. Use .yaml or .py")


if __name__ == "__main__":
    raise SystemExit(main())
