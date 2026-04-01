"""Task engine - core components for game automation."""

from .models import ExecutionResult, StepSpec, TaskSpec, TaskMeta, DeviceConfig, OcrConfig
from .adb_client import ADBClient, ADBError, DeviceInfo
from .vision import VisionEngine, ImageMatchResult, TextItem, TextMatchResult, load_image
from .logger import RunLogger
from .runner import TaskRunner
from .config_io import load_task, save_task, load_dsl_task, load_task_auto

__all__ = [
    # models
    "ExecutionResult",
    "StepSpec",
    "TaskSpec",
    "TaskMeta",
    "DeviceConfig",
    "OcrConfig",
    # adb_client
    "ADBClient",
    "ADBError",
    "DeviceInfo",
    # vision
    "VisionEngine",
    "ImageMatchResult",
    "TextItem",
    "TextMatchResult",
    "load_image",
    # logger
    "RunLogger",
    # runner
    "TaskRunner",
    # config_io
    "load_task",
    "save_task",
    "load_dsl_task",
    "load_task_auto",
]
