"""botCore - Core components for game automation.

Shared utilities used by both yamlBot and dslBot.
"""

from .models import (
    ExecutionResult,
    StepSpec,
    TaskSpec,
    TaskMeta,
    DeviceConfig,
    OcrConfig,
)
from .adb_client import ADBClient, ADBError, DeviceInfo
from .vision import VisionEngine, ImageMatchResult, TextItem, TextMatchResult, load_image
from .logger import RunLogger

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
]
