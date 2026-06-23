"""Task Queue Manager UI - Transfer box for selecting and ordering multiple tasks."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from botCore import ADBClient, ADBError, GameTask, RunLogger, VisionEngine, load_task_class
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner


class QueueRunnerWorker(QObject):
    """Worker for running task queue in background thread."""
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        task_instances: list[GameTask],
        adb_path: str,
        serial: str | None,
        ocr_enabled: bool,
        ocr_lang: str,
    ):
        super().__init__()
        self.task_instances = task_instances
        self.adb_path = adb_path
        self.serial = serial
        self.ocr_enabled = ocr_enabled
        self.ocr_lang = ocr_lang
        self.runner: TaskQueueRunner | None = None

    @Slot()
    def run(self) -> None:
        try:
            adb = ADBClient(adb_path=self.adb_path, serial=self.serial)
            vision = VisionEngine(enable_ocr=self.ocr_enabled, ocr_lang=self.ocr_lang)
            logger = RunLogger()
            self.runner = TaskQueueRunner(
                task_list=self.task_instances,
                adb_client=adb,
                vision=vision,
                logger=logger,
                event_callback=self.progress.emit,
            )
            self.runner.run()
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class TaskQueueWindow(QMainWindow):
    """Task Queue Manager with transfer box UI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Queue Manager")
        self.resize(1000, 700)

        self._load_env_config()

        self.worker: QueueRunnerWorker | None = None
        self.thread: QThread | None = None
        self.available_tasks: list[dict] = []  # [{"key": str, "name": str, "class": type, "file": str}]
        self.selected_tasks: list[dict] = []  # Same structure as available_tasks

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_config_panel())
        layout.addWidget(self._build_transfer_panel(), 1)
        layout.addWidget(self._build_control_panel())
        layout.addWidget(self._build_log_panel(), 1)

        self._scan_available_tasks()

    def _build_config_panel(self) -> QWidget:
        """Build ADB configuration panel."""
        box = QGroupBox("ADB Configuration")
        grid = QGridLayout(box)

        self.adb_path_edit = QLineEdit(self._env_adb_path or "adb")
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_devices)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("e.g., 127.0.0.1:5555")
        if self._env_serial:
            self.serial_input.setText(self._env_serial)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)

        self.ocr_enabled = QCheckBox("Enable OCR")
        self.ocr_enabled.setChecked(True)
        self.ocr_lang = QComboBox()
        self.ocr_lang.addItems(["中文 (ch)", "English (en)"])
        self.ocr_lang.setCurrentIndex(0)

        row = 0
        grid.addWidget(QLabel("ADB Path"), row, 0)
        grid.addWidget(self.adb_path_edit, row, 1)
        grid.addWidget(QLabel("Device"), row, 2)
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(self.refresh_btn)
        grid.addWidget(device_row, row, 3)
        row += 1

        grid.addWidget(QLabel("Custom Serial"), row, 0)
        serial_row = QWidget()
        serial_layout = QHBoxLayout(serial_row)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.addWidget(self.serial_input, 1)
        serial_layout.addWidget(self.connect_btn)
        grid.addWidget(serial_row, row, 1, 1, 3)
        row += 1

        grid.addWidget(self.ocr_enabled, row, 0)
        grid.addWidget(QLabel("OCR Lang"), row, 1)
        grid.addWidget(self.ocr_lang, row, 2)

        self.refresh_devices()
        return box

    def _build_transfer_panel(self) -> QWidget:
        """Build transfer box for task selection."""
        box = QGroupBox("Task Selection")
        layout = QHBoxLayout(box)

        # Left: Available tasks
        left_group = QGroupBox("Available Tasks")
        left_layout = QVBoxLayout(left_group)
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.available_list)

        # Middle: Buttons
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        self.add_btn = QPushButton("→")
        self.add_btn.clicked.connect(self.add_selected_tasks)
        btn_layout.addWidget(self.add_btn)
        self.remove_btn = QPushButton("←")
        self.remove_btn.clicked.connect(self.remove_selected_tasks)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        layout.addWidget(left_group)
        layout.addLayout(btn_layout)

        # Right: Selected tasks (queue)
        right_group = QGroupBox("Task Queue (Drag to Reorder)")
        right_layout = QVBoxLayout(right_group)
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.selected_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        right_layout.addWidget(self.selected_list)

        layout.addWidget(right_group)
        return box

    def _build_control_panel(self) -> QWidget:
        """Build control buttons panel."""
        box = QGroupBox("Control")
        layout = QHBoxLayout(box)
        layout.addStretch()

        self.start_btn = QPushButton("Start Queue")
        self.start_btn.clicked.connect(self.start_queue)
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_queue)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.resume_queue)
        self.resume_btn.setEnabled(False)
        layout.addWidget(self.resume_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_queue)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        layout.addStretch()
        return box

    def _build_log_panel(self) -> QWidget:
        """Build log output panel."""
        box = QGroupBox("Log Output")
        layout = QVBoxLayout(box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.clear_log_btn)
        layout.addLayout(btn_layout)
        return box

    def _scan_available_tasks(self) -> None:
        """Scan task directory for available Python DSL tasks."""
        task_dir = Path(__file__).parent.parent / "task"
        if not task_dir.exists():
            self._append_log(f"[WARN] Task directory not found: {task_dir}")
            return

        self.available_tasks = []
        for file_path in task_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            try:
                task_class = self._load_task_class_from_file(file_path)
                if task_class:
                    self.available_tasks.append({
                        "key": getattr(task_class, "task_key", task_class.__name__),
                        "name": getattr(task_class, "task_name", task_class.__name__),
                        "description": getattr(task_class, "task_description", ""),
                        "class": task_class,
                        "file": str(file_path),
                    })
            except Exception as e:
                self._append_log(f"[WARN] Failed to load {file_path.name}: {e}")

        self._update_available_list()

    def _load_task_class_from_file(self, file_path: Path) -> type[GameTask] | None:
        """Load GameTask subclass from a Python file."""
        return load_task_class(file_path)

    def _update_available_list(self) -> None:
        """Update the available tasks list widget."""
        self.available_list.clear()
        for task_info in self.available_tasks:
            item = QListWidgetItem(f"{task_info['name']} ({task_info['key']})")
            item.setToolTip(task_info.get("description", ""))
            item.setData(Qt.ItemDataRole.UserRole, task_info)
            self.available_list.addItem(item)

    def _update_selected_list(self) -> None:
        """Update the selected tasks list widget."""
        self.selected_list.clear()
        for task_info in self.selected_tasks:
            item = QListWidgetItem(f"{task_info['name']} ({task_info['key']})")
            item.setToolTip(task_info.get("description", ""))
            item.setData(Qt.ItemDataRole.UserRole, task_info)
            self.selected_list.addItem(item)

    def _sync_selected_tasks_from_widget(self) -> None:
        """Persist the current visual order after drag-and-drop reordering."""
        ordered_tasks = []
        for row in range(self.selected_list.count()):
            task_info = self.selected_list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(task_info, dict):
                ordered_tasks.append(task_info)
        self.selected_tasks = ordered_tasks

    def add_selected_tasks(self) -> None:
        """Add selected available tasks to queue."""
        selected_indexes = self.available_list.selectedIndexes()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda i: i.row(), reverse=True):
            row = index.row()
            if 0 <= row < len(self.available_tasks):
                task_info = self.available_tasks[row].copy()
                self.selected_tasks.append(task_info)

        self._update_selected_list()

    def remove_selected_tasks(self) -> None:
        """Remove selected tasks from queue."""
        self._sync_selected_tasks_from_widget()
        selected_indexes = self.selected_list.selectedIndexes()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda i: i.row(), reverse=True):
            row = index.row()
            if 0 <= row < len(self.selected_tasks):
                self.selected_tasks.pop(row)

        self._update_selected_list()

    def _get_selected_task_instances(self) -> list[GameTask]:
        """Create task instances from selected tasks."""
        self._sync_selected_tasks_from_widget()
        instances = []
        for task_info in self.selected_tasks:
            try:
                instance = task_info["class"]()
                instances.append(instance)
            except Exception as e:
                self._append_log(f"[ERROR] Failed to create task instance: {e}")
        return instances

    def start_queue(self) -> None:
        """Start executing the task queue."""
        if not self.selected_tasks:
            QMessageBox.warning(self, "No Tasks", "Please select at least one task.")
            return

        task_instances = self._get_selected_task_instances()
        if not task_instances:
            return

        adb_path = self.adb_path_edit.text().strip() or "adb"
        serial = self.device_combo.currentText().strip() or self.serial_input.text().strip() or None
        ocr_lang = self._current_ocr_lang()

        self.thread = QThread(self)
        self.worker = QueueRunnerWorker(
            task_instances,
            adb_path,
            serial,
            self.ocr_enabled.isChecked(),
            ocr_lang,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._append_log)
        self.worker.error.connect(self._on_run_error)
        self.worker.finished.connect(self._on_run_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_worker)
        self.thread.start()

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self._append_log(f"Task queue started. OCR={self.ocr_enabled.isChecked()}, lang={ocr_lang}")

    def pause_queue(self) -> None:
        """Pause the task queue."""
        if self.worker and self.worker.runner:
            self.worker.runner.pause()
            self._append_log("Pause requested.")
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
        else:
            self._append_log("[WARN] No active runner to pause")

    def resume_queue(self) -> None:
        """Resume the paused task queue."""
        if self.worker and self.worker.runner:
            self.worker.runner.resume()
            self._append_log("Resumed.")
            self.resume_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
        else:
            self._append_log("[WARN] No active runner to resume")

    def stop_queue(self) -> None:
        """Stop the task queue."""
        if self.worker and self.worker.runner:
            self.worker.runner.stop()
            self._append_log("Stop requested.")
            self.stop_btn.setEnabled(False)
        else:
            self._append_log("[WARN] No active runner to stop")

    def _on_run_finished(self) -> None:
        """Called when queue execution finishes."""
        self._append_log("Task queue finished.")
        self._reset_buttons()

    def _on_run_error(self, message: str) -> None:
        """Called when queue execution errors."""
        self._append_log(f"[ERROR] {message}")
        self._reset_buttons()

    def _reset_buttons(self) -> None:
        """Reset control buttons to initial state."""
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

    def _cleanup_worker(self) -> None:
        """Clean up worker reference after thread finishes."""
        self.worker = None

    def _load_env_config(self) -> None:
        """Load default ADB configuration from .env file."""
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()

        self._env_adb_path = os.getenv("DEFAULT_ADB_PATH")
        self._env_serial = os.getenv("DEFAULT_ADB_SERIAL")

    def _append_log(self, text: str) -> None:
        """Append text to log view."""
        self.log_view.append(text)

    def _current_ocr_lang(self) -> str:
        """Return OCR language code from the UI selection."""
        lang_map = {"中文 (ch)": "ch", "English (en)": "en"}
        return lang_map.get(self.ocr_lang.currentText(), "ch")

    def clear_log(self) -> None:
        """Clear all log messages."""
        self.log_view.clear()

    def refresh_devices(self) -> None:
        """Refresh connected ADB devices."""
        self.device_combo.clear()
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            devices = ADBClient.list_devices(adb_path=adb_path)
        except ADBError as exc:
            self.device_combo.addItem("")
            self._append_log(f"[WARN] {exc}")
            return
        if not devices:
            self.device_combo.addItem("")
            return
        for item in devices:
            self.device_combo.addItem(item.serial)

    def connect_serial(self) -> None:
        """Connect to a custom ADB serial port."""
        serial = self.serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "Invalid Serial", "Please enter a serial port.")
            return
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            adb = ADBClient(adb_path=adb_path)
            adb.connect(serial)
            self._append_log(f"Connected to {serial}")
            self.refresh_devices()
            idx = self.device_combo.findText(serial)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "Connect", f"Successfully connected to {serial}")
        except ADBError as exc:
            QMessageBox.critical(self, "Connect Failed", str(exc))
            self._append_log(f"[ERROR] Connect failed: {exc}")


def main():
    """Entry point for the Task Queue Manager."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = TaskQueueWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
