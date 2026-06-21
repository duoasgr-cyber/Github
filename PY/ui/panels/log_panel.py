import logging

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox, QPushButton, QLabel

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
    """Log display panel with level filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        label = QLabel("日志级别:")
        label.setFont(QFont("Microsoft YaHei", 9))
        toolbar.addWidget(label)

        self._level_combo = QComboBox()
        self._level_combo.setFont(QFont("Microsoft YaHei", 9))
        self._level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("INFO")
        self._level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)

        self._btn_clear = QPushButton("清空")
        self._btn_clear.setFixedHeight(24)
        self._btn_clear.clicked.connect(self._clear_log)
        toolbar.addWidget(self._btn_clear)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Log text area
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFontFamily("Consolas")
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #e6edf3; font-size: 12px; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

        self._min_level = logging.INFO

    def _on_level_changed(self, level_name: str):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
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
        html = f'<span style="color:{color};">{escaped}</span>'
        self._log_edit.append(html)
        self._log_edit.moveCursor(QTextCursor.End)
