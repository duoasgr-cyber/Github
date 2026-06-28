import logging

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QComboBox, QPushButton, QLabel, QSizePolicy,
)

logger = logging.getLogger(__name__)


class QtLogHandler(QObject, logging.Handler):
    """Logging handler that emits Qt signals for UI display."""
    log_signal = pyqtSignal(str, int)  # message, level

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg, record.levelno)


class LogPanel(QWidget):
    """Log display panel with level filtering and script control buttons."""

    # ---- 脚本控制信号（由 MainWindow 接收） ----
    request_run_from = pyqtSignal()    # 从当前步骤启动
    request_run_full = pyqtSignal()    # 从头启动脚本
    request_stop = pyqtSignal()        # 停止执行

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        label = QLabel("\u65e5\u5fd7\u7ea7\u522b:")
        label.setFont(QFont("Microsoft YaHei", 9))
        toolbar.addWidget(label)

        self._level_combo = QComboBox()
        self._level_combo.setFont(QFont("Microsoft YaHei", 9))
        self._level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("INFO")
        self._level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)

        self._btn_clear = QPushButton("\u6e05\u7a7a")
        self._btn_clear.setFixedHeight(24)
        self._btn_clear.clicked.connect(self._clear_log)
        toolbar.addWidget(self._btn_clear)

        # ---- 分隔 ----
        sep = QLabel("\u2502")
        sep.setStyleSheet("color: #30363d; font-size: 14px;")
        toolbar.addWidget(sep)

        # ---- 脚本控制按钮 ----
        self._btn_run_from = QPushButton("\u25b6 \u4ece\u5f53\u524d\u6b65\u9aa4\u542f\u52a8")
        self._btn_run_from.setFixedHeight(24)
        self._btn_run_from.setToolTip("\u4ece\u5f53\u524d\u9009\u4e2d\u7684\u6b65\u9aa4\u5f00\u59cb\u6267\u884c\u5de5\u4f5c\u6d41")
        self._btn_run_from.clicked.connect(self.request_run_from.emit)
        toolbar.addWidget(self._btn_run_from)

        self._btn_run_full = QPushButton("\u23f5 \u4ece\u5934\u542f\u52a8\u811a\u672c")
        self._btn_run_full.setFixedHeight(24)
        self._btn_run_full.setToolTip("\u4ece\u7b2c\u4e00\u6b65\u5f00\u59cb\u6267\u884c\u6574\u4e2a\u5de5\u4f5c\u6d41")
        self._btn_run_full.clicked.connect(self.request_run_full.emit)
        toolbar.addWidget(self._btn_run_full)

        self._btn_stop = QPushButton("\u23f9 \u505c\u6b62")
        self._btn_stop.setFixedHeight(24)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setToolTip("\u8bf7\u6c42\u505c\u6b62\u5f53\u524d\u6267\u884c")
        self._btn_stop.clicked.connect(self.request_stop.emit)
        toolbar.addWidget(self._btn_stop)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ---- Log text area ----
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFontFamily("Consolas")
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; "
            "color: #e6edf3; font-size: 12px; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

        self._min_level = logging.INFO

    # ---- 公开接口：由 MainWindow 调用来切换运行状态 ----

    def set_running(self, running: bool):
        """切换按钮到运行/空闲状态。"""
        self._btn_run_from.setEnabled(not running)
        self._btn_run_full.setEnabled(not running)
        self._btn_stop.setEnabled(running)

    # ---- 内部方法 ----

    def _on_level_changed(self, level_name: str):
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        self._min_level = level_map.get(level_name, logging.INFO)

    def _clear_log(self):
        self._log_edit.clear()

    def _append_log(self, message: str, level: int = logging.INFO):
        if level < self._min_level:
            return
        color_map = {
            logging.DEBUG: "#8b949e",
            logging.INFO: "#e6edf3",
            logging.WARNING: "#d29922",
            logging.ERROR: "#f85149",
            logging.CRITICAL: "#f85149",
        }
        color = color_map.get(level, "#e6edf3")
        escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = '<span style="color:' + color + ';">' + escaped + '</span>'
        self._log_edit.append(html)
        self._log_edit.moveCursor(QTextCursor.End)
