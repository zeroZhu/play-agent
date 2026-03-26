from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


class ADBError(RuntimeError):
    pass


@dataclass(slots=True)
class DeviceInfo:
    serial: str
    state: str


class ADBClient:
    def __init__(self, adb_path: str = "adb", serial: str | None = None, timeout_sec: int = 15):
        self.adb_path = adb_path
        self.serial = serial
        self.timeout_sec = timeout_sec

    @staticmethod
    def list_devices(adb_path: str = "adb", timeout_sec: int = 10) -> list[DeviceInfo]:
        cmd = [adb_path, "devices"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        if proc.returncode != 0:
            raise ADBError(proc.stderr.strip() or "adb devices failed")
        devices: list[DeviceInfo] = []
        for line in proc.stdout.splitlines():
            if "\t" not in line or line.startswith("List of devices"):
                continue
            serial, state = line.split("\t", 1)
            devices.append(DeviceInfo(serial=serial.strip(), state=state.strip()))
        return devices

    def connect(self, serial: str) -> None:
        proc = self._run(["connect", serial], check=False, text=True)
        text = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and "already connected" not in text.lower():
            raise ADBError(text.strip() or f"Failed to connect {serial}")
        self.serial = serial

    def ensure_device(self) -> None:
        devices = self.list_devices(self.adb_path, timeout_sec=self.timeout_sec)
        if self.serial:
            if any(d.serial == self.serial and d.state == "device" for d in devices):
                return
            raise ADBError(f"Device serial not found or not ready: {self.serial}")
        ready = [d for d in devices if d.state == "device"]
        if len(ready) == 1:
            self.serial = ready[0].serial
            return
        if len(ready) == 0:
            raise ADBError("No active adb device found.")
        raise ADBError("Multiple devices found. Please select a device serial.")

    def get_screen_size(self) -> tuple[int, int]:
        out = self.shell("wm size")
        match = re.search(r"(\d+)x(\d+)", out)
        if not match:
            raise ADBError(f"Unable to parse wm size output: {out}")
        return int(match.group(1)), int(match.group(2))

    def screenshot(self) -> np.ndarray:
        cmd = [self.adb_path, *self._device_prefix(), "exec-out", "screencap", "-p"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=self.timeout_sec,
            check=False,
        )
        if proc.returncode != 0:
            raise ADBError(proc.stderr.decode(errors="ignore").strip() or "screencap failed")
        raw = proc.stdout.replace(b"\r\n", b"\n")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ADBError("Failed to decode screenshot bytes.")
        return image

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.shell(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}"
        )

    def shell(self, command: str) -> str:
        proc = self._run(["shell", command], check=False, text=True)
        if proc.returncode != 0:
            raise ADBError(proc.stderr.strip() or f"adb shell failed: {command}")
        return (proc.stdout or "").strip()

    def _device_prefix(self) -> list[str]:
        return ["-s", self.serial] if self.serial else []

    def _run(
        self,
        args: Sequence[str],
        *,
        check: bool,
        text: bool,
    ) -> subprocess.CompletedProcess:
        cmd = [self.adb_path, *self._device_prefix(), *args]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=text,
            timeout=self.timeout_sec,
            check=False,
        )
        if check and proc.returncode != 0:
            stderr = proc.stderr if text else proc.stderr.decode(errors="ignore")
            raise ADBError(stderr.strip() or "adb command failed")
        return proc
