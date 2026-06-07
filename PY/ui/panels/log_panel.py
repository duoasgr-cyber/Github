import logging
import os
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout,
    QWidget, QFileDialog, QMessageBox
)

from core.structured_log import get_log_collector


class QtLogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str, int)

    def __init__(self, parent=None):
        logging.Handler.__init__(self, level=logging.NOTSET)
        QObject.__init__(self, parent)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)


class LogPanel(QWidget):
    LOG_COLORS = {
        logging.DEBUG: "#8b949e",
        logging.INFO: "#e6edf3",
        logging.WARNING: "#d29922",
        logging.ERROR: "#f85149",
    }

    LEVEL_NAMES = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_entries = []
        self._current_filter = None
        self._handler = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._filter_buttons = {}

        btn_all = QPushButton("ALL")
        btn_all.setCheckable(True)
        btn_all.setChecked(True)
        btn_all.setFixedHeight(28)
        btn_all.clicked.connect(lambda: self._set_filter(None))
        self._filter_buttons[None] = btn_all
        toolbar.addWidget(btn_all)

        for level, name in self.LEVEL_NAMES.items():
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, lv=level: self._set_filter(lv))
            self._filter_buttons[level] = btn
            toolbar.addWidget(btn)

        toolbar.addStretch()

        btn_export_json = QPushButton("Export JSON")
        btn_export_json.setFixedHeight(28)
        btn_export_json.clicked.connect(self._export_json)
        toolbar.addWidget(btn_export_json)

        btn_export_csv = QPushButton("Export CSV")
        btn_export_csv.setFixedHeight(28)
        btn_export_csv.clicked.connect(self._export_csv)
        toolbar.addWidget(btn_export_csv)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedHeight(28)
        btn_clear.clicked.connect(self._clear_logs)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFontFamily("Consolas")
        self._text_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; }"
        )
        layout.addWidget(self._text_edit)

    def _set_filter(self, level):
        self._current_filter = level
        for lv, btn in self._filter_buttons.items():
            btn.setChecked(lv == level)
        self._render_logs()

    def _clear_logs(self):
        self._log_entries.clear()
        self._text_edit.clear()

    def _append_log(self, message, level):
        self._log_entries.append((message, level))
        if self._current_filter is not None and level != self._current_filter:
            return
        color = self.LOG_COLORS.get(level, "#e6edf3")
        escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = '<span style="color:{};">{}</span>'.format(color, escaped)
        self._text_edit.append(html)
        self._text_edit.verticalScrollBar().setValue(
            self._text_edit.verticalScrollBar().maximum()
        )

    def _render_logs(self):
        self._text_edit.clear()
        parts = []
        for message, level in self._log_entries:
            if self._current_filter is not None and level != self._current_filter:
                continue
            color = self.LOG_COLORS.get(level, "#e6edf3")
            escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append('<span style="color:{};">{}</span>'.format(color, escaped))
        if parts:
            self._text_edit.setHtml("<br>".join(parts))
            self._text_edit.verticalScrollBar().setValue(
                self._text_edit.verticalScrollBar().maximum()
            )

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs (JSON)", f"logs_{datetime.now():%Y%m%d_%H%M%S}.jsonl",
            "JSON Lines (*.jsonl);;All Files (*)"
        )
        if path:
            collector = get_log_collector()
            if collector.export_json(path):
                QMessageBox.information(self, "Exported", f"Logs exported to:\n{path}\n({collector.count} entries)")
            else:
                QMessageBox.warning(self, "Failed", "Could not export logs.")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs (CSV)", f"logs_{datetime.now():%Y%m%d_%H%M%S}.csv",
            "CSV (*.csv);;All Files (*)"
        )
        if path:
            collector = get_log_collector()
            if collector.export_csv(path):
                QMessageBox.information(self, "Exported", f"Logs exported to:\n{path}\n({collector.count} entries)")
            else:
                QMessageBox.warning(self, "Failed", "Could not export logs.")

    def setup_logger(self, logger_name=""):
        logger = logging.getLogger(logger_name)

        self._handler = QtLogHandler(self)
        self._handler.log_signal.connect(self._append_log)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        )
        self._handler.setFormatter(formatter)
        logger.addHandler(self._handler)

        # Add structured log collector handler
        from core.structured_log import CollectingLogHandler
        collector_handler = CollectingLogHandler()
        collector_handler.setLevel(logging.DEBUG)
        logger.addHandler(collector_handler)

        log_path = os.path.join(os.getcwd(), "app.log")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
