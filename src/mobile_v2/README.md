# Mobile V2 Scaffold (Kivy + Buildozer)

This folder provides a V2 scaffold for APK packaging:

- `main.py`: Kivy config UI prototype
- `buildozer.spec.sample`: sample buildozer config

## Goal

V2 focuses on:

- In-app task config (edit/load/save YAML-like JSON model)
- Task scheduling and control surface in emulator

## Important Boundary

Cross-app click/drag automation on Android depends on system permissions (Accessibility/root/system app).  
So V2 is designed as an extension for config/scheduling first, while V1 PC+ADB remains the stable control baseline.

## Typical Build Flow (Linux/WSL)

```bash
pip install buildozer cython
cp buildozer.spec.sample buildozer.spec
buildozer android debug
```

Generated APK can then be installed into emulator for config workflow validation.
