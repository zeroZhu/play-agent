"""截图测试脚本 - 用于调试截图功能"""

import os

import cv2
import pytest

from botCore import ADBClient


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.getenv("ADB_SERIAL"), reason="Set ADB_SERIAL for screenshot test.")
def test_screenshot(tmp_path):
    """测试截图功能"""
    # 初始化 ADB
    adb = ADBClient(
        adb_path=os.getenv("ADB_PATH", "adb"),
        serial=os.getenv("ADB_SERIAL"),
    )
    adb.ensure_device()

    # 截图
    print("Taking screenshot...")
    screenshot = adb.screenshot()
    print(f"Screenshot size: {screenshot.shape}")

    # 保存截图
    output_path = tmp_path / "screenshot.png"
    cv2.imwrite(str(output_path), screenshot)
    print(f"Screenshot saved to: {output_path}")

    return screenshot


if __name__ == "__main__":
    test_screenshot()
