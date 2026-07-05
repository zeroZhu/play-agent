from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from botCore import VisionEngine
from botCore.vision import load_image


def test_template_match_found():
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.rectangle(screen, (120, 70), (170, 120), (255, 255, 255), thickness=-1)
    template = screen[70:120, 120:170].copy()

    tmp_dir = Path("logs/test_tmp/template") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tmp_dir / "template.png"
    cv2.imwrite(str(tpl_path), template)

    engine = VisionEngine()
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

    engine = VisionEngine()
    result = engine.match_template(screen, str(tpl_path), threshold=0.99)

    assert result.found is False


def test_menke_sheyan_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    screenshot_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{screenshot_prefix}3.png",
            root / "src/ymjh_bot/templates/btn_menke_sheyan_entry.png",
            (150, 470, 210, 145),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}4.png",
            root / "src/ymjh_bot/templates/btn_menke_invite_forward.png",
            (780, 135, 170, 520),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}5.png",
            root / "src/ymjh_bot/templates/btn_menke_banquet_invite.png",
            None,
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}6.png",
            root / "src/ymjh_bot/templates/btn_menke_confirm_invite.png",
            None,
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7.png",
            root / "src/ymjh_bot/templates/btn_menke_get_item.png",
            (960, 530, 210, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_menke_one_key_submit.png",
            (960, 530, 210, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_menke_start_active.png",
            (220, 550, 200, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8.png",
            root / "src/ymjh_bot/templates/route_menke_warehouse_recommended.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}10.png",
            root / "src/ymjh_bot/templates/route_menke_mall.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8.png",
            root / "src/ymjh_bot/templates/route_menke_stall.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8-2.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}12.png",
            root / "src/ymjh_bot/templates/btn_menke_view_all_server.png",
            (600, 440, 250, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}15.png",
            root / "src/ymjh_bot/templates/btn_menke_mall_buy_area.png",
            (800, 610, 290, 100),
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=0.95, roi=roi)

        assert result.found is True
        assert result.score >= 0.95


def test_menke_sheyan_templates_avoid_key_false_positives():
    root = Path(__file__).resolve().parents[1]
    screenshot_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{screenshot_prefix}8-1.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}11.png",
            root / "src/ymjh_bot/templates/route_menke_warehouse_recommended.png",
            (560, 70, 660, 480),
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=0.8, roi=roi)

        assert result.found is False


def test_pozhen_sheyan_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    menke_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    pozhen_prefix = "\u7834\u9635\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{menke_prefix}3.png",
            root / "src/ymjh_bot/templates/btn_pozhen_sheyan_entry.png",
            (540, 230, 260, 160),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}4.png",
            root / "src/ymjh_bot/templates/btn_menke_invite_forward.png",
            (780, 135, 170, 520),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}5.png",
            root / "src/ymjh_bot/templates/btn_menke_banquet_invite.png",
            None,
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_get_item.png",
            (960, 530, 210, 110),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-2.png",
            root / "src/ymjh_bot/templates/btn_pozhen_one_key_submit.png",
            (960, 530, 210, 110),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_submit_5_tab.png",
            (110, 365, 215, 65),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_submit_6_tab.png",
            (295, 365, 205, 65),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_bangpai_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    menke_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/text_bangpai.png",
            (40, 135, 330, 430),
            0.9,
        ),
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/route_bangpai_stall.png",
            (720, 120, 480, 500),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/route_bangpai_warehouse.png",
            (720, 120, 480, 500),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}13.png",
            root / "src/ymjh_bot/templates/btn_buy.png",
            (520, 440, 330, 120),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}12.png",
            root / "src/ymjh_bot/templates/btn_menke_view_all_server.png",
            (600, 440, 250, 100),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}8-2.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_current_after_loop_timeout.png",
            root / "src/ymjh_bot/templates/btn_bangpai_one_key_submit.png",
            (900, 330, 340, 160),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_after_full_run_start_fail.png",
            root / "src/ymjh_bot/templates/text_power_saving.png",
            (480, 470, 340, 140),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_task_complete.png",
            root / "src/ymjh_bot/templates/text_bangpai_task_complete.png",
            (40, 570, 650, 90),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold
