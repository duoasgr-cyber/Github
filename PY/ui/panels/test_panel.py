from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.step_executor import StepExecutor
from ui.components.step_list_widget import STEP_TYPE_DISPLAY


class _StepTestWorker(QThread):
    step_started = pyqtSignal(int, str)
    step_completed = pyqtSignal(int, str)
    step_failed = pyqtSignal(int, str, str)
    workflow_completed = pyqtSignal(str)
    workflow_failed = pyqtSignal(str, str)
    workflow_paused = pyqtSignal()
    workflow_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)
    finished_signal = pyqtSignal()

    def __init__(self, step_executor, mode, workflow_name, step_index=0, parent=None):
        super().__init__(parent)
        self._step_executor = step_executor
        self._mode = mode
        self._workflow_name = workflow_name
        self._step_index = step_index

    def run(self):
        self._step_executor.step_started.connect(self.step_started.emit)
        self._step_executor.step_completed.connect(self.step_completed.emit)
        self._step_executor.step_failed.connect(self.step_failed.emit)
        self._step_executor.workflow_completed.connect(self.workflow_completed.emit)
        self._step_executor.workflow_failed.connect(self.workflow_failed.emit)
        self._step_executor.workflow_paused.connect(self.workflow_paused.emit)
        self._step_executor.workflow_stopped.connect(self.workflow_stopped.emit)
        self._step_executor.progress_updated.connect(self.progress_updated.emit)

        if self._mode == "single":
            self._step_executor.execute_step(self._workflow_name, self._step_index)
        elif self._mode == "from_step":
            self._step_executor.execute_workflow(self._workflow_name, self._step_index)
        elif self._mode == "full":
            self._step_executor.execute_workflow(self._workflow_name, 0)

        self._step_executor.step_started.disconnect(self.step_started.emit)
        self._step_executor.step_completed.disconnect(self.step_completed.emit)
        self._step_executor.step_failed.disconnect(self.step_failed.emit)
        self._step_executor.workflow_completed.disconnect(self.workflow_completed.emit)
        self._step_executor.workflow_failed.disconnect(self.workflow_failed.emit)
        self._step_executor.workflow_paused.disconnect(self.workflow_paused.emit)
        self._step_executor.workflow_stopped.disconnect(self.workflow_stopped.emit)
        self._step_executor.progress_updated.disconnect(self.progress_updated.emit)

        self.finished_signal.emit()


class TestPanel(QWidget):
    def __init__(self, step_executor, config_manager, parent=None):
        super().__init__(parent)
        self._step_executor = step_executor
        self._config_manager = config_manager
        self._current_workflow_name = ""
        self._worker = None
        self._step_states = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        wf_layout = QHBoxLayout()
        wf_layout.setSpacing(4)
        self._workflow_combo = QComboBox()
        self._workflow_combo.setFont(QFont("Microsoft YaHei", 10))
        wf_layout.addWidget(self._workflow_combo, stretch=1)
        layout.addLayout(wf_layout)

        self._step_list = QListWidget()
        self._step_list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self._step_list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_test_step = QPushButton("测试此步骤")
        self._btn_test_step.setFixedHeight(28)
        btn_layout.addWidget(self._btn_test_step)

        self._btn_run_from = QPushButton("从此步运行")
        self._btn_run_from.setFixedHeight(28)
        btn_layout.addWidget(self._btn_run_from)

        self._btn_run_workflow = QPushButton("运行整个工作流")
        self._btn_run_workflow.setFixedHeight(28)
        btn_layout.addWidget(self._btn_run_workflow)

        self._btn_pause = QPushButton("暂停")
        self._btn_pause.setFixedHeight(28)
        self._btn_pause.setEnabled(False)
        btn_layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setFixedHeight(28)
        self._btn_stop.setEnabled(False)
        btn_layout.addWidget(self._btn_stop)

        layout.addLayout(btn_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFontFamily("Consolas")
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #e6edf3; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

    def _connect_signals(self):
        self._workflow_combo.currentIndexChanged.connect(self._on_workflow_changed)
        self._btn_test_step.clicked.connect(self.test_single_step)
        self._btn_run_from.clicked.connect(self.run_from_step)
        self._btn_run_workflow.clicked.connect(self.run_workflow)
        self._btn_pause.clicked.connect(self.pause_execution)
        self._btn_stop.clicked.connect(self.stop_execution)

    def _on_workflow_changed(self, index):
        if index < 0:
            self._current_workflow_name = ""
            self._step_list.clear()
            self._step_states.clear()
            return
        name = self._workflow_combo.itemText(index)
        self.set_workflow(name)

    def load_workflows(self):
        self._workflow_combo.blockSignals(True)
        self._workflow_combo.clear()
        workflows = self._config_manager.get_all_workflows()
        for name in workflows:
            self._workflow_combo.addItem(name)
        self._workflow_combo.blockSignals(False)
        if self._workflow_combo.count() > 0:
            self._workflow_combo.setCurrentIndex(0)

    def set_workflow(self, workflow_name: str):
        self._current_workflow_name = workflow_name
        self._load_steps()

    def _load_steps(self):
        self._step_list.clear()
        self._step_states.clear()
        self._progress_bar.setValue(0)

        if not self._current_workflow_name:
            return

        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return

        steps = workflow.get("steps", [])
        for i, step in enumerate(steps):
            step_type = step.get("type", "unknown")
            comment = step.get("comment", "")
            type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
            text = f"{i + 1}. {type_display}"
            if comment:
                text += f" - {comment}"
            item = QListWidgetItem(text)
            self._step_list.addItem(item)
            self._step_states.append("pending")

    def _set_step_state(self, index: int, state: str):
        if index < 0 or index >= self._step_list.count():
            return
        self._step_states[index] = state
        item = self._step_list.item(index)

        if state == "running":
            item.setBackground(QBrush(QColor(0, 100, 220)))
            item.setForeground(QBrush(QColor(255, 255, 255)))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        elif state == "completed":
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            item.setForeground(QBrush(QColor(0, 200, 80)))
            font = item.font()
            font.setBold(False)
            item.setFont(font)
        elif state == "failed":
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            item.setForeground(QBrush(QColor(255, 60, 60)))
            font = item.font()
            font.setBold(False)
            item.setFont(font)
        else:
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            item.setForeground(QBrush(QColor(200, 200, 200)))
            font = item.font()
            font.setBold(False)
            item.setFont(font)

    def _set_running_ui(self, running: bool):
        self._btn_test_step.setEnabled(not running)
        self._btn_run_from.setEnabled(not running)
        self._btn_run_workflow.setEnabled(not running)
        self._btn_pause.setEnabled(running)
        self._btn_stop.setEnabled(running)
        self._workflow_combo.setEnabled(not running)
        if running:
            self._btn_pause.setText("暂停")
        if not running:
            self._worker = None

    def _start_worker(self, mode: str, step_index: int = 0):
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._current_workflow_name:
            return

        self._load_steps()

        self._worker = _StepTestWorker(
            self._step_executor, mode,
            self._current_workflow_name, step_index
        )
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_completed.connect(self._on_step_completed)
        self._worker.step_failed.connect(self._on_step_failed)
        self._worker.workflow_completed.connect(self._on_workflow_completed)
        self._worker.workflow_failed.connect(self._on_workflow_failed)
        self._worker.workflow_paused.connect(self._on_workflow_paused)
        self._worker.workflow_stopped.connect(self._on_workflow_stopped)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.finished_signal.connect(self._on_worker_finished)

        self._set_running_ui(True)
        self._worker.start()

    def test_single_step(self):
        row = self._step_list.currentRow()
        if row < 0:
            self._append_log("请先选择一个步骤")
            return
        self._append_log(f"测试步骤 {row + 1}")
        self._start_worker("single", row)

    def run_from_step(self):
        row = self._step_list.currentRow()
        if row < 0:
            self._append_log("请先选择一个步骤")
            return
        self._append_log(f"从步骤 {row + 1} 开始运行工作流")
        self._start_worker("from_step", row)

    def run_workflow(self):
        if not self._current_workflow_name:
            self._append_log("请先选择工作流")
            return
        self._append_log(f"运行整个工作流: {self._current_workflow_name}")
        self._start_worker("full", 0)

    def pause_execution(self):
        if self._step_executor.is_paused():
            self._step_executor.resume()
            self._btn_pause.setText("暂停")
            self._append_log("工作流已恢复")
        else:
            self._step_executor.pause()
            self._btn_pause.setText("继续")
            self._append_log("工作流已暂停")

    def stop_execution(self):
        self._step_executor.stop()
        self._append_log("正在停止工作流...")

    def _on_step_started(self, index: int, step_type: str):
        type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
        self._set_step_state(index, "running")
        self._step_list.setCurrentRow(index)
        self._append_log(f"▶ 步骤 {index + 1} ({type_display}) 开始执行")

    def _on_step_completed(self, index: int, step_type: str):
        type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
        self._set_step_state(index, "completed")
        self._append_log(f"✓ 步骤 {index + 1} ({type_display}) 执行完成")

    def _on_step_failed(self, index: int, step_type: str, error: str):
        type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
        self._set_step_state(index, "failed")
        self._append_log(f"✗ 步骤 {index + 1} ({type_display}) 执行失败: {error}")

    def _on_workflow_completed(self, name: str):
        self._append_log(f"工作流 '{name}' 执行完成")

    def _on_workflow_failed(self, name: str, error: str):
        self._append_log(f"工作流 '{name}' 执行失败: {error}")

    def _on_workflow_paused(self):
        self._append_log("工作流已暂停")

    def _on_workflow_stopped(self):
        self._append_log("工作流已停止")

    def _on_progress_updated(self, current: int, total: int):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)

    def _on_worker_finished(self):
        self._set_running_ui(False)

    def _append_log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = f'<span style="color:#8b949e;">[{timestamp}]</span> {escaped}'
        self._log_edit.append(html)
        self._log_edit.verticalScrollBar().setValue(
            self._log_edit.verticalScrollBar().maximum()
        )
