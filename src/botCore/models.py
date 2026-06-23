from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    elapsed_ms: int
    reason: str
    screenshot_path: str | None = None
