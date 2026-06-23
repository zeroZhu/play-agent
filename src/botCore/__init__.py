"""botCore - Core components and Python DSL runtime for game automation."""

from .models import ExecutionResult
from .adb_client import ADBClient, ADBError, DeviceInfo
from .vision import VisionEngine, ImageMatchResult, TextItem, TextMatchResult, load_image
from .logger import RunLogger
from .task import GameTask, StepCallable, StepJumpException, StepStopException, step
from .loader import load_task_class, load_task_instance
from .runner import DSLTaskRunner

__all__ = [
    # models
    "ExecutionResult",
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
    # task DSL
    "GameTask",
    "step",
    "StepCallable",
    "StepJumpException",
    "StepStopException",
    # loading/running
    "load_task_class",
    "load_task_instance",
    "DSLTaskRunner",
]
