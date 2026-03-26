# Task Template Pack

Use one of these templates as your starting point:

- `00_base_skeleton.yaml`: full field skeleton, easy to customize
- `01_daily_farm_image_first.yaml`: image-first daily farm loop
- `02_text_priority_fallback.yaml`: text-first with image fallback
- `03_drag_scan_loop.yaml`: map/page drag-scan loop

## Fast Replace Checklist

1. Replace `device.serial` with your emulator serial.
2. Replace all `assets/templates/*.png` with your real screenshot templates.
3. Tune `threshold`:
   - image: start at `0.88~0.92`
   - text: start at `0.82~0.88`
4. Tune `timeout_ms` and `retry` by scene load speed.
5. Keep `design_resolution` aligned with your capture resolution.

## Run

```powershell
uv run --no-sync python launch_gui.py
```

Then load any template YAML and run.
