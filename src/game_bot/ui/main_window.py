from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from task_engine import ADBClient, ADBError, load_task, save_task, RunLogger, StepSpec, TaskSpec, TaskRunner, VisionEngine
from task_engine.models import SUPPORTED_STEP_TYPES


class StepDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, step: StepSpec | None = None):
        super().__init__(parent)
        self.setWindowTitle("Step")
        self.resize(700, 560)

        form = QFormLayout(self)
        self.id_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(sorted(SUPPORTED_STEP_TYPES))
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.0, 1.0)
        self.threshold.setSingleStep(0.01)
        self.threshold.setValue(0.85)
        self.timeout_ms = QSpinBox()
        self.timeout_ms.setRange(100, 120000)
        self.timeout_ms.setValue(5000)
        self.retry = QSpinBox()
        self.retry.setRange(0, 99)
        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(True)
        self.target_edit = QPlainTextEdit("{}")
        self.action_edit = QPlainTextEdit("{}")

        form.addRow("id", self.id_edit)
        form.addRow("type", self.type_combo)
        form.addRow("threshold", self.threshold)
        form.addRow("timeout_ms", self.timeout_ms)
        form.addRow("retry", self.retry)
        form.addRow("", self.enabled)
        form.addRow("target(JSON)", self.target_edit)
        form.addRow("action(JSON)", self.action_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if step:
            self.id_edit.setText(step.id)
            self.type_combo.setCurrentText(step.type)
            self.threshold.setValue(step.threshold)
            self.timeout_ms.setValue(step.timeout_ms)
            self.retry.setValue(step.retry)
            self.enabled.setChecked(step.enabled)
            self.target_edit.setPlainText(json.dumps(step.target, ensure_ascii=False, indent=2))
            self.action_edit.setPlainText(json.dumps(step.action, ensure_ascii=False, indent=2))

    def get_step(self) -> StepSpec:
        sid = self.id_edit.text().strip()
        if not sid:
            raise ValueError("Step id is required.")
        target = _safe_json(self.target_edit.toPlainText(), "target")
        action = _safe_json(self.action_edit.toPlainText(), "action")
        return StepSpec(
            id=sid,
            type=self.type_combo.currentText(),
            target=target,
            threshold=self.threshold.value(),
            timeout_ms=self.timeout_ms.value(),
            retry=self.retry.value(),
            action=action,
            enabled=self.enabled.isChecked(),
        )


class RunnerWorker(QObject):
    progress = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, task: TaskSpec):
        super().__init__()
        self.task = task
        self.runner: TaskRunner | None = None

    @Slot()
    def run(self) -> None:
        try:
            adb = ADBClient(adb_path=self.task.device.adb_path, serial=self.task.device.serial)
            vision = VisionEngine(enable_ocr=self.task.ocr.enabled, ocr_lang=self.task.ocr.lang)
            logger = RunLogger()
            self.runner = TaskRunner(
                task=self.task,
                adb_client=adb,
                vision=vision,
                logger=logger,
                event_callback=self.progress.emit,
            )
            results = self.runner.run()
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Bot (MuMu First)")
        self.resize(1200, 820)

        # Load .env file for default configuration
        self._load_env_config()

        self.task = TaskSpec()
        self.current_file: Path | None = None
        self.worker: RunnerWorker | None = None
        self.thread: QThread | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_top_panel())
        layout.addWidget(self._build_step_panel(), 1)
        layout.addWidget(self._build_log_panel(), 1)
        self._refresh_step_table()

    def _build_top_panel(self) -> QWidget:
        box = QGroupBox("Task Settings")
        grid = QGridLayout(box)

        self.name_edit = QLineEdit(self.task.meta.name)
        self.design_w = QSpinBox()
        self.design_h = QSpinBox()
        self.design_w.setRange(320, 5000)
        self.design_h.setRange(320, 5000)
        self.design_w.setValue(self.task.meta.design_resolution[0])
        self.design_h.setValue(self.task.meta.design_resolution[1])
        self.loop_count = QSpinBox()
        self.loop_count.setRange(1, 9999)
        self.loop_count.setValue(self.task.meta.loop_count)

        self.delay_min = QSpinBox()
        self.delay_max = QSpinBox()
        self.delay_min.setRange(0, 5000)
        self.delay_max.setRange(0, 5000)
        self.delay_min.setValue(self.task.meta.random_delay_ms[0])
        self.delay_max.setValue(self.task.meta.random_delay_ms[1])

        self.adb_path_edit = QLineEdit(self._env_adb_path or self.task.device.adb_path)
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self.refresh_devices)

        # Custom serial input and connect button
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("e.g., 127.0.0.1:5555")
        # Set default serial from .env if available
        if self._env_serial:
            self.serial_input.setText(self._env_serial)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)

        self.ocr_enabled = QCheckBox("Enable OCR")
        self.ocr_enabled.setChecked(self.task.ocr.enabled)
        self.ocr_lang = QComboBox()
        self.ocr_lang.addItems(["ch", "en"])
        self.ocr_lang.setCurrentText(self.task.ocr.lang)
        self.ocr_min_conf = QDoubleSpinBox()
        self.ocr_min_conf.setRange(0.0, 1.0)
        self.ocr_min_conf.setSingleStep(0.05)
        self.ocr_min_conf.setValue(self.task.ocr.min_confidence)

        row = 0
        grid.addWidget(QLabel("Task Name"), row, 0)
        grid.addWidget(self.name_edit, row, 1)
        grid.addWidget(QLabel("Loop Count"), row, 2)
        grid.addWidget(self.loop_count, row, 3)
        row += 1

        grid.addWidget(QLabel("Design Width"), row, 0)
        grid.addWidget(self.design_w, row, 1)
        grid.addWidget(QLabel("Design Height"), row, 2)
        grid.addWidget(self.design_h, row, 3)
        row += 1

        grid.addWidget(QLabel("Random Delay Min(ms)"), row, 0)
        grid.addWidget(self.delay_min, row, 1)
        grid.addWidget(QLabel("Random Delay Max(ms)"), row, 2)
        grid.addWidget(self.delay_max, row, 3)
        row += 1

        grid.addWidget(QLabel("ADB Path"), row, 0)
        grid.addWidget(self.adb_path_edit, row, 1)
        grid.addWidget(QLabel("Device Serial"), row, 2)
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(self.refresh_btn)
        grid.addWidget(device_row, row, 3)
        row += 1

        # Custom serial input row
        grid.addWidget(QLabel("Custom Serial"), row, 0)
        serial_input_row = QWidget()
        serial_input_layout = QHBoxLayout(serial_input_row)
        serial_input_layout.setContentsMargins(0, 0, 0, 0)
        serial_input_layout.addWidget(self.serial_input, 1)
        serial_input_layout.addWidget(self.connect_btn)
        grid.addWidget(serial_input_row, row, 1, 1, 3)
        row += 1

        grid.addWidget(self.ocr_enabled, row, 0)
        grid.addWidget(QLabel("OCR Lang"), row, 1)
        grid.addWidget(self.ocr_lang, row, 2)
        grid.addWidget(self.ocr_min_conf, row, 3)
        row += 1

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.load_btn = QPushButton("Load YAML")
        self.save_btn = QPushButton("Save YAML")
        self.screenshot_btn = QPushButton("Screenshot")
        self.run_btn = QPushButton("Run")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.screenshot_btn)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        grid.addWidget(btn_row, row, 0, 1, 4)

        self.load_btn.clicked.connect(self.load_yaml)
        self.save_btn.clicked.connect(self.save_yaml)
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.run_btn.clicked.connect(self.start_run)
        self.stop_btn.clicked.connect(self.stop_run)

        self.refresh_devices()
        return box

    def _build_step_panel(self) -> QWidget:
        box = QGroupBox("Steps")
        layout = QVBoxLayout(box)
        self.step_table = QTableWidget(0, 8)
        self.step_table.setHorizontalHeaderLabels(
            ["id", "type", "threshold", "timeout_ms", "retry", "enabled", "target", "action"]
        )
        self.step_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.step_table, 1)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.add_step_btn = QPushButton("Add Step")
        self.edit_step_btn = QPushButton("Edit Step")
        self.delete_step_btn = QPushButton("Delete Step")
        button_layout.addWidget(self.add_step_btn)
        button_layout.addWidget(self.edit_step_btn)
        button_layout.addWidget(self.delete_step_btn)
        layout.addWidget(button_row)

        self.add_step_btn.clicked.connect(self.add_step)
        self.edit_step_btn.clicked.connect(self.edit_step)
        self.delete_step_btn.clicked.connect(self.delete_step)
        return box

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("Run Log")
        layout = QVBoxLayout(box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)
        return box

    def refresh_devices(self) -> None:
        self.device_combo.clear()
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            devices = ADBClient.list_devices(adb_path=adb_path)
        except ADBError as exc:
            self.device_combo.addItem("")
            if hasattr(self, "log_view") and self.log_view is not None:
                self._append_log(f"[WARN] {exc}")
            else:
                QMessageBox.warning(self, "ADB Warning", str(exc))
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
            # Refresh device list and select the connected device
            self.refresh_devices()
            idx = self.device_combo.findText(serial)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "Connect", f"Successfully connected to {serial}")
        except ADBError as exc:
            QMessageBox.critical(self, "Connect Failed", str(exc))
            self._append_log(f"[ERROR] Connect failed: {exc}")

    def add_step(self) -> None:
        dlg = StepDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            step = dlg.get_step()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Step", str(exc))
            return
        self.task.steps.append(step)
        self._refresh_step_table()

    def edit_step(self) -> None:
        idx = self._selected_step_index()
        if idx is None:
            return
        dlg = StepDialog(self, self.task.steps[idx])
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.task.steps[idx] = dlg.get_step()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Step", str(exc))
            return
        self._refresh_step_table()

    def delete_step(self) -> None:
        idx = self._selected_step_index()
        if idx is None:
            return
        self.task.steps.pop(idx)
        self._refresh_step_table()

    def load_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Task YAML", str(Path.cwd()), "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            self.task = load_task(path)
            self.current_file = Path(path)
            self._load_task_to_form()
            self._append_log(f"Loaded task: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", str(exc))

    def save_yaml(self) -> None:
        try:
            self._apply_form_to_task()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Config", str(exc))
            return
        default_name = str(self.current_file) if self.current_file else str(Path.cwd() / "task.yaml")
        path, _ = QFileDialog.getSaveFileName(self, "Save Task YAML", default_name, "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            save_task(self.task, path)
            self.current_file = Path(path)
            self._append_log(f"Saved task: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def take_screenshot(self) -> None:
        """Take a screenshot from the connected device and save it."""
        adb_path = self.adb_path_edit.text().strip() or "adb"
        serial = self.device_combo.currentText().strip() or None

        try:
            adb = ADBClient(adb_path=adb_path, serial=serial)
            adb.ensure_device()
            screenshot = adb.screenshot()

            # Save screenshot to file
            from pathlib import Path as PathLib
            timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            default_dir = PathLib.cwd() / "screenshots"
            default_dir.mkdir(parents=True, exist_ok=True)
            default_path = default_dir / f"screenshot_{timestamp}.png"

            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                str(default_path),
                "PNG (*.png)"
            )
            if not path:
                return

            import cv2
            cv2.imwrite(path, screenshot)
            self._append_log(f"Screenshot saved: {path}")
            QMessageBox.information(self, "Screenshot", f"Screenshot saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Screenshot Failed", str(exc))
            self._append_log(f"[ERROR] Screenshot failed: {exc}")

    def start_run(self) -> None:
        try:
            self._apply_form_to_task()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Config", str(exc))
            return
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "Busy", "Task is already running.")
            return

        task_copy = copy.deepcopy(self.task)
        self.thread = QThread(self)
        self.worker = RunnerWorker(task_copy)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._append_log)
        self.worker.error.connect(self._on_run_error)
        self.worker.finished.connect(self._on_run_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.start()

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._append_log("Run started.")

    def stop_run(self) -> None:
        if self.worker and self.worker.runner:
            self.worker.runner.stop()
            self._append_log("Stop requested.")
        self.stop_btn.setEnabled(False)

    def _on_run_finished(self, results: list[Any]) -> None:
        ok = sum(1 for x in results if x.success)
        total = len(results)
        self._append_log(f"Run finished: {ok}/{total} success.")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_run_error(self, message: str) -> None:
        self._append_log(f"[ERROR] {message}")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _apply_form_to_task(self) -> None:
        serial = self.device_combo.currentText().strip() or None
        min_delay = self.delay_min.value()
        max_delay = self.delay_max.value()
        if min_delay > max_delay:
            raise ValueError("Random delay min cannot be greater than max.")

        self.task.meta.name = self.name_edit.text().strip() or "New Task"
        self.task.meta.design_resolution = (self.design_w.value(), self.design_h.value())
        self.task.meta.loop_count = self.loop_count.value()
        self.task.meta.random_delay_ms = (min_delay, max_delay)
        self.task.device.adb_path = self.adb_path_edit.text().strip() or "adb"
        self.task.device.serial = serial
        self.task.ocr.enabled = self.ocr_enabled.isChecked()
        self.task.ocr.lang = self.ocr_lang.currentText()
        self.task.ocr.min_confidence = self.ocr_min_conf.value()

        ids = [step.id for step in self.task.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step id must be unique.")

    def _load_task_to_form(self) -> None:
        self.name_edit.setText(self.task.meta.name)
        self.design_w.setValue(self.task.meta.design_resolution[0])
        self.design_h.setValue(self.task.meta.design_resolution[1])
        self.loop_count.setValue(self.task.meta.loop_count)
        self.delay_min.setValue(self.task.meta.random_delay_ms[0])
        self.delay_max.setValue(self.task.meta.random_delay_ms[1])
        self.adb_path_edit.setText(self.task.device.adb_path)
        self.refresh_devices()
        if self.task.device.serial:
            idx = self.device_combo.findText(self.task.device.serial)
            if idx < 0:
                self.device_combo.addItem(self.task.device.serial)
                idx = self.device_combo.findText(self.task.device.serial)
            self.device_combo.setCurrentIndex(idx)
        self.ocr_enabled.setChecked(self.task.ocr.enabled)
        self.ocr_lang.setCurrentText(self.task.ocr.lang)
        self.ocr_min_conf.setValue(self.task.ocr.min_confidence)
        self._refresh_step_table()

    def _load_env_config(self) -> None:
        """Load default ADB configuration from .env file."""
        # Load .env file from project root
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Try current working directory
            load_dotenv()

        # Read environment variables
        default_adb_path = os.getenv("DEFAULT_ADB_PATH")
        default_serial = os.getenv("DEFAULT_ADB_SERIAL")

        # Store for later use in _build_top_panel
        self._env_adb_path = default_adb_path
        self._env_serial = default_serial

    def _refresh_step_table(self) -> None:
        self.step_table.setRowCount(len(self.task.steps))
        for row, step in enumerate(self.task.steps):
            self.step_table.setItem(row, 0, QTableWidgetItem(step.id))
            self.step_table.setItem(row, 1, QTableWidgetItem(step.type))
            self.step_table.setItem(row, 2, QTableWidgetItem(f"{step.threshold:.2f}"))
            self.step_table.setItem(row, 3, QTableWidgetItem(str(step.timeout_ms)))
            self.step_table.setItem(row, 4, QTableWidgetItem(str(step.retry)))
            self.step_table.setItem(row, 5, QTableWidgetItem(str(step.enabled)))
            self.step_table.setItem(
                row,
                6,
                QTableWidgetItem(json.dumps(step.target, ensure_ascii=False)),
            )
            self.step_table.setItem(
                row,
                7,
                QTableWidgetItem(json.dumps(step.action, ensure_ascii=False)),
            )

    def _selected_step_index(self) -> int | None:
        row = self.step_table.currentRow()
        if row < 0 or row >= len(self.task.steps):
            QMessageBox.information(self, "Select Step", "Please select one step.")
            return None
        return row

    def _append_log(self, text: str) -> None:
        self.log_view.append(text)


def _safe_json(text: str, name: str) -> dict[str, Any]:
    text = text.strip() or "{}"
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return raw
