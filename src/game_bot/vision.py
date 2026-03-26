from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


@dataclass(slots=True)
class ImageMatchResult:
    found: bool
    score: float
    center: tuple[int, int] | None
    bbox: tuple[int, int, int, int] | None
    template_path: str | None = None


@dataclass(slots=True)
class TextItem:
    text: str
    confidence: float
    bbox: list[list[float]]

    @property
    def center(self) -> tuple[int, int]:
        xs = [pt[0] for pt in self.bbox]
        ys = [pt[1] for pt in self.bbox]
        return int(sum(xs) / len(xs)), int(sum(ys) / len(ys))


@dataclass(slots=True)
class TextMatchResult:
    found: bool
    text: str | None
    confidence: float
    center: tuple[int, int] | None
    bbox: list[list[float]] | None


class VisionEngine:
    def __init__(
        self,
        *,
        enable_ocr: bool = True,
        ocr_lang: str = "ch",
        ocr_reader: Any | None = None,
    ) -> None:
        self.enable_ocr = enable_ocr
        self.ocr_lang = ocr_lang
        self._ocr_reader = ocr_reader

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

    def find_text(
        self,
        screenshot: np.ndarray,
        query: str,
        *,
        exact: bool = False,
        min_confidence: float = 0.55,
    ) -> TextMatchResult:
        results = self.perform_ocr(screenshot)
        return self.find_text_in_items(
            results,
            query=query,
            exact=exact,
            min_confidence=min_confidence,
        )

    def perform_ocr(self, screenshot: np.ndarray) -> list[TextItem]:
        if not self.enable_ocr:
            return []
        reader = self._get_ocr_reader()
        raw = reader.ocr(screenshot, cls=True)
        return self._parse_paddle_ocr(raw)

    @staticmethod
    def find_text_in_items(
        items: Iterable[TextItem],
        *,
        query: str,
        exact: bool = False,
        min_confidence: float = 0.55,
    ) -> TextMatchResult:
        query = query.strip()
        best: TextItem | None = None
        for item in items:
            if item.confidence < min_confidence:
                continue
            ok = item.text == query if exact else query in item.text
            if not ok:
                continue
            if best is None or item.confidence > best.confidence:
                best = item
        if best is None:
            return TextMatchResult(
                found=False,
                text=None,
                confidence=0.0,
                center=None,
                bbox=None,
            )
        return TextMatchResult(
            found=True,
            text=best.text,
            confidence=best.confidence,
            center=best.center,
            bbox=best.bbox,
        )

    def _get_ocr_reader(self) -> Any:
        if self._ocr_reader is not None:
            return self._ocr_reader
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "PaddleOCR is not available. Install dependencies with uv sync."
            ) from exc
        self._ocr_reader = PaddleOCR(use_angle_cls=True, lang=self.ocr_lang, show_log=False)
        return self._ocr_reader

    @staticmethod
    def _parse_paddle_ocr(raw: Any) -> list[TextItem]:
        if not raw:
            return []
        lines = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
        items: list[TextItem] = []
        for line in lines:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            bbox_raw, rec_raw = line[0], line[1]
            if (
                not isinstance(bbox_raw, (list, tuple))
                or len(bbox_raw) < 4
                or not isinstance(rec_raw, (list, tuple))
                or len(rec_raw) < 2
            ):
                continue
            text = str(rec_raw[0])
            conf = float(rec_raw[1])
            bbox = [[float(p[0]), float(p[1])] for p in bbox_raw]
            items.append(TextItem(text=text, confidence=conf, bbox=bbox))
        return items


def load_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Unable to load image: {path}")
    return image
