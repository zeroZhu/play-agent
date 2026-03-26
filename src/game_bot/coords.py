from __future__ import annotations

import random
import time


def scale_point(
    point: tuple[int, int],
    design_resolution: tuple[int, int],
    current_resolution: tuple[int, int],
) -> tuple[int, int]:
    dx = current_resolution[0] / design_resolution[0]
    dy = current_resolution[1] / design_resolution[1]
    return int(round(point[0] * dx)), int(round(point[1] * dy))


def apply_random_offset(point: tuple[int, int], max_offset_px: int) -> tuple[int, int]:
    if max_offset_px <= 0:
        return point
    return (
        point[0] + random.randint(-max_offset_px, max_offset_px),
        point[1] + random.randint(-max_offset_px, max_offset_px),
    )


def sleep_with_jitter(base_seconds: float, delay_range_ms: tuple[int, int] | None) -> float:
    extra = 0.0
    if delay_range_ms:
        lo = min(delay_range_ms[0], delay_range_ms[1])
        hi = max(delay_range_ms[0], delay_range_ms[1])
        extra = random.uniform(lo, hi) / 1000.0
    total = max(0.0, base_seconds + extra)
    if total > 0:
        time.sleep(total)
    return total
