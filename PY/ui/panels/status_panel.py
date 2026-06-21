from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QGroupBox
)


class StatusPanel(QWidget):
    """Status monitoring panel for workflow execution."""

    start_monitoring = pyqtSignal()
    stop_monitoring = pyqtSignal()
    pause_monitoring = pyqtSignal()
    resume_monitoring = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Status display
        status_group = QGroupBox("运行状态")
        status_layout = QVBoxLayout(status_group)

        self._status_label = QLabel("状态: 空闲")
        self._status_label.setFont(QFont("Microsoft YaHei", 12))
        self._status_label.setStyleSheet("color: #a0a0a0;")
        status_layout.addWidget(self._status_label)

        self._workflow_label = QLabel("工作流: 无")
        self._workflow_label.setFont(QFont("Microsoft YaHei", 10))
        status_layout.addWidget(self._workflow_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        status_layout.addWidget(self._progress_bar)

        layout.addWidget(status_group)

        # Control buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_start = QPushButton("启动监控")
        self._btn_start.setFixedHeight(32)
        self._btn_start.clicked.connect(self.start_monitoring.emit)
        btn_layout.addWidget(self._btn_start)

        self._btn_pause = QPushButton("暂停")
        self._btn_pause.setFixedHeight(32)
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self.pause_monitoring.emit)
        btn_layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setFixedHeight(32)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_monitoring.emit)
        btn_layout.addWidget(self._btn_stop)

        layout.addLayout(btn_layout)

        # Log area
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFontFamily("Consolas")
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #e6edf3; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

    def update_status(self, status: str, color: str = "#a0a0a0"):
        self._status_label.setText(f"状态: {status}")
        self._status_label.setStyleSheet(f"color: {color};")
        running = status in ("运行中",)
        self._btn_start.setEnabled(not running)
        self._btn_pause.setEnabled(running)
        self._btn_stop.setEnabled(running or status == "暂停中")

    def update_current_workflow(self, name: str):
        self._workflow_label.setText(f"工作流: {name}")
