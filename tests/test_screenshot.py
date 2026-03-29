"""截图测试脚本 - 用于调试 OCR 和截图功能"""

import os
from pathlib import Path

import cv2
import numpy as np

from game_bot.adb_client import ADBClient
from game_bot.vision import VisionEngine, TextItem


def test_screenshot_and_ocr():
    """测试截图和 OCR 功能"""
    # 初始化 ADB
    adb = ADBClient(adb_path="adb", serial="127.0.0.1:16384")
    adb.ensure_device()

    # 截图
    print("Taking screenshot...")
    screenshot = adb.screenshot()
    print(f"Screenshot size: {screenshot.shape}")

    # 保存截图
    output_path = Path(__file__).parent / "screenshot.png"
    cv2.imwrite(str(output_path), screenshot)
    print(f"Screenshot saved to: {output_path}")

    # 初始化 OCR 引擎
    print("\nInitializing OCR engine...")
    try:
        vision = VisionEngine(enable_ocr=True, ocr_lang="ch")
    except Exception as e:
        print(f"Failed to initialize OCR: {e}")
        print("OCR 功能需要安装 PaddlePaddle 和 PaddleOCR")
        print("请运行：pip install paddlepaddle paddleocr")
        return None, []

    # 执行 OCR
    print("Performing OCR...")
    results = vision.perform_ocr(screenshot)
    print(f"Found {len(results)} text regions:\n")

    for i, item in enumerate(results, 1):
        print(f"{i}. Text: {item.text}")
        print(f"   Confidence: {item.confidence:.2f}")
        print(f"   BBox: {item.bbox}")
        print(f"   Center: {item.center}")
        print()

    # 搜索特定文本
    search_texts = ["开始游戏", "朕知道了", "确定"]
    for query in search_texts:
        match = vision.find_text(screenshot, query, exact=False, min_confidence=0.3)
        if match.found:
            print(f"[FOUND] '{query}' -> '{match.text}' (conf={match.confidence:.2f}, center={match.center})")
        else:
            print(f"[NOT FOUND] '{query}'")

    return screenshot, results


if __name__ == "__main__":
    test_screenshot_and_ocr()
