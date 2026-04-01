from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_STEP_TYPES = {
    "find_image_click",
    "find_image_loop",
    "find_image_loop_until_missing",
    "find_image_loop_with_action",
    "find_text_click",
    "find_text_loop",
    "drag",
    "wait",
    "loop",
    "conditional",
    "switch_case",
    "start_app",
    "click_point",
}


def _to_resolution(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return default


def _to_range(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return default


@dataclass(slots=True)
class TaskMeta:
    name: str = "New Task"
    design_resolution: tuple[int, int] = (1280, 720)
    loop_count: int = 1
    random_delay_ms: tuple[int, int] = (60, 140)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TaskMeta":
        raw = data or {}
        return cls(
            name=str(raw.get("name", "New Task")),
            design_resolution=_to_resolution(raw.get("design_resolution"), (1280, 720)),
            loop_count=max(1, int(raw.get("loop_count", 1))),
            random_delay_ms=_to_range(raw.get("random_delay_ms"), (60, 140)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "design_resolution": [self.design_resolution[0], self.design_resolution[1]],
            "loop_count": self.loop_count,
            "random_delay_ms": [self.random_delay_ms[0], self.random_delay_ms[1]],
        }


@dataclass(slots=True)
class DeviceConfig:
    adb_path: str = "adb"
    serial: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DeviceConfig":
        raw = data or {}
        serial = raw.get("serial")
        return cls(
            adb_path=str(raw.get("adb_path", "adb")),
            serial=str(serial) if serial else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"adb_path": self.adb_path, "serial": self.serial}


@dataclass(slots=True)
class OcrConfig:
    enabled: bool = True
    lang: str = "ch"
    min_confidence: float = 0.55

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OcrConfig":
        raw = data or {}
        return cls(
            enabled=bool(raw.get("enabled", True)),
            lang=str(raw.get("lang", "ch")),
            min_confidence=float(raw.get("min_confidence", 0.55)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "lang": self.lang,
            "min_confidence": self.min_confidence,
        }


@dataclass(slots=True)
class StepSpec:
    id: str
    type: str
    target: dict[str, Any] = field(default_factory=dict)
    threshold: float = 0.85
    timeout_ms: int = 5000
    retry: int = 0
    action: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepSpec":
        step_type = str(data.get("type", "")).strip()
        if step_type not in SUPPORTED_STEP_TYPES:
            raise ValueError(f"Unsupported step type: {step_type}")
        retry_raw = int(data.get("retry", 0))
        retry = retry_raw if retry_raw < 0 else max(0, retry_raw)
        return cls(
            id=str(data.get("id", "")).strip(),
            type=step_type,
            target=dict(data.get("target", {}) or {}),
            threshold=float(data.get("threshold", 0.85)),
            timeout_ms=max(100, int(data.get("timeout_ms", 5000))),
            retry=retry,
            action=dict(data.get("action", {}) or {}),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "target": self.target,
            "threshold": self.threshold,
            "timeout_ms": self.timeout_ms,
            "retry": self.retry,
            "action": self.action,
            "enabled": self.enabled,
        }


@dataclass(slots=True)
class TaskSpec:
    meta: TaskMeta = field(default_factory=TaskMeta)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    steps: list[StepSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        steps_raw = data.get("steps", []) or []
        steps = [StepSpec.from_dict(item) for item in steps_raw]
        missing_ids = [idx for idx, step in enumerate(steps) if not step.id]
        if missing_ids:
            raise ValueError(f"Step id is required, missing at indexes: {missing_ids}")
        return cls(
            meta=TaskMeta.from_dict(data.get("meta")),
            device=DeviceConfig.from_dict(data.get("device")),
            ocr=OcrConfig.from_dict(data.get("ocr")),
            steps=steps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "device": self.device.to_dict(),
            "ocr": self.ocr.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    elapsed_ms: int
    reason: str
    screenshot_path: str | None = None
