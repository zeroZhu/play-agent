"""Official entrypoint for the ymjh_bot task queue UI."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication

from ymjh_bot.ui.task_queue_window import TaskQueueWindow


def main() -> int:
    """Start the ymjh_bot task queue UI."""
    app = QApplication(sys.argv)
    window = TaskQueueWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
