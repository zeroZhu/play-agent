from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(slots=True)
class ImageMatchResult:
    found: bool
    score: float
    center: tuple[int, int] | None
    bbox: tuple[int, int, int, int] | None
    template_path: str | None = None


class VisionEngine:
    def match_template(
        self,
        screenshot: np.ndarray,
        template_paths: str | list[str],
        *,
        threshold: float = 0.85,
        roi: tuple[int, int, int, int] | None = None,
    ) -> ImageMatchResult:
        candidates = [template_paths] if isinstance(template_paths, str) else template_paths
        region = screenshot
        offset_x, offset_y = 0, 0
        if roi:
            x, y, w, h = roi
            offset_x, offset_y = x, y
            region = screenshot[y : y + h, x : x + w]

        best = ImageMatchResult(found=False, score=0.0, center=None, bbox=None)
        for tpl_path in candidates:
            tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
                continue
            # Constant-color templates are unstable with CCOEFF. Fall back to SQDIFF.
            if float(np.std(tpl)) < 1e-6:
                response = cv2.matchTemplate(region, tpl, cv2.TM_SQDIFF_NORMED)
                min_val, _, min_loc, _ = cv2.minMaxLoc(response)
                score = 1.0 - float(min_val)
                loc = min_loc
            else:
                response = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(response)
                score = float(max_val)
                loc = max_loc
            if score > best.score:
                x1 = loc[0] + offset_x
                y1 = loc[1] + offset_y
                x2 = x1 + tpl.shape[1]
                y2 = y1 + tpl.shape[0]
                best = ImageMatchResult(
                    found=score >= threshold,
                    score=score,
                    center=(int((x1 + x2) / 2), int((y1 + y2) / 2)),
                    bbox=(x1, y1, x2, y2),
                    template_path=str(tpl_path),
                )
        if best.score < threshold:
            best.found = False
        return best


def load_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Unable to load image: {path}")
    return image
