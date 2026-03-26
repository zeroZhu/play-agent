# Game Bot (MuMu First)

Python-based Android emulator auto-farm tool with:

- PC config GUI (`PySide6`)
- ADB control (tap/swipe/screenshot)
- Image match (`OpenCV`) and text match (`PaddleOCR`)
- YAML task specs + runtime logs

## V1 Scope

V1 runs on Windows PC and controls emulator through ADB.  
MuMu is the first target, other emulators can be added by setting the device serial/port.

## Quick Start

1. Install Python 3.10+.
2. Create project virtual env and install dependencies by `uv`:

```powershell
uv venv .venv
uv sync --dev --no-install-project
```

3. Make sure `adb` is available in PATH (or configure `adb_path` in GUI).
4. Start GUI:

```powershell
uv run --no-sync python launch_gui.py
```

## Task Spec (YAML)

Top-level structure:

- `meta`: task meta settings
- `device`: adb path + serial
- `ocr`: OCR settings
- `steps`: executable steps

See sample:

- [sample_tasks/demo_task.yaml](D:/workplace_syzhu/play-agent/sample_tasks/demo_task.yaml)

## Supported Step Types

- `find_image_click`
- `find_text_click`
- `drag`
- `wait`
- `loop`
- `conditional`

## Logs

Runtime logs are written to `logs/run_YYYYMMDD_HHMMSS`:

- `events.jsonl`: structured events
- `shots/*.png`: optional annotated screenshots

## Tests

```powershell
uv run --no-sync pytest -q
```

## V2 (APK)

V2 scaffold is included under:

- [src/mobile_v2](D:/workplace_syzhu/play-agent/src/mobile_v2)

It uses `Kivy + Buildozer` for APK packaging and focuses on in-app config/scheduling.  
Cross-app touch automation still depends on Android permissions and may not fully replace PC+ADB control.
