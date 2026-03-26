from __future__ import annotations

import os

import pytest

from game_bot.adb_client import ADBClient


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.getenv("ADB_SERIAL"), reason="Set ADB_SERIAL for integration test.")
def test_adb_end_to_end():
    adb_path = os.getenv("ADB_PATH", "adb")
    serial = os.getenv("ADB_SERIAL")
    client = ADBClient(adb_path=adb_path, serial=serial)
    client.ensure_device()
    width, height = client.get_screen_size()
    assert width > 0 and height > 0
    image = client.screenshot()
    assert image is not None
