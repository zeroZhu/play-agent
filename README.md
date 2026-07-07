# PlayAgent

Python-based Android emulator automation toolkit.

- `botCore`: shared foundation and Python DSL runtime
- `game_bot`: development-only GUI/CLI for debugging task scripts
- `ymjh_bot`: Yi Meng Jiang Hu scripts, queue runner, templates, and UI

## Scope

PlayAgent controls Android emulators through ADB. The root `launch_gui.py` entrypoint is a developer debugger for loading and running Python task scripts during development. Product/game-specific scripts and UI live inside their own sub bot packages.

YAML task support has been removed. Tasks are Python DSL classes.

## Quick Start

```powershell
uv venv .venv
uv sync --dev --no-install-project
```

Start the development debugger:

```powershell
uv run --no-sync python launch_gui.py
```

Run a Python DSL task from the CLI:

```powershell
uv run --no-sync python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py
```

## DSL Example

```python
from botCore import GameTask, step

class MyTask(GameTask):
    design_resolution = (1280, 720)
    loop_count = 1

    @step(retry=3, timeout_ms=10000)
    def click_start(self) -> bool:
        if self.find_image("templates/btn_start.png"):
            self.click()
            return True
        return False
```

## Logs

Runtime logs are written to `logs/run_YYYYMMDD_HHMMSS`:

- `events.jsonl`: structured events
- `shots/*.png`: optional annotated screenshots

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Integration tests that touch a real emulator are skipped unless `ADB_SERIAL` is set.
