from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from game_bot.vision import VisionEngine


def test_template_match_found():
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.rectangle(screen, (120, 70), (170, 120), (255, 255, 255), thickness=-1)
    template = screen[70:120, 120:170].copy()

    tmp_dir = Path("logs/test_tmp/template") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tmp_dir / "template.png"
    cv2.imwrite(str(tpl_path), template)

    engine = VisionEngine(enable_ocr=False)
    result = engine.match_template(screen, str(tpl_path), threshold=0.95)

    assert result.found is True
    assert result.center is not None
    assert 140 <= result.center[0] <= 150
    assert 90 <= result.center[1] <= 100


def test_template_match_not_found():
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    template = np.full((40, 40, 3), 255, dtype=np.uint8)
    tmp_dir = Path("logs/test_tmp/template") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tmp_dir / "template2.png"
    cv2.imwrite(str(tpl_path), template)

    engine = VisionEngine(enable_ocr=False)
    result = engine.match_template(screen, str(tpl_path), threshold=0.99)

    assert result.found is False
