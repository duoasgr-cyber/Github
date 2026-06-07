"""First-run setup wizard that checks for required dependencies.

Detects: ADB, ffmpeg, scrcpy-server, EasyOCR models, and screen capture.
Provides actionable fix suggestions for each issue found.
"""
import os
import shutil
import subprocess
import sys
import logging
from typing import List, Tuple

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QCheckBox, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class _CheckWorker(QThread):
    """Background worker for dependency checks."""
    check_complete = pyqtSignal(str, str, str, str)
    all_complete = pyqtSignal()

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self._base_dir = base_dir

    def run(self):
        # (name, status, message, fix_hint)
        results = []
        results.append(self._check_adb())
        results.append(self._check_ffmpeg())
        results.append(self._check_scrcpy())
        results.append(self._check_ocr_models())
        results.append(self._check_config_files())

        for name, status, msg, fix in results:
            self.check_complete.emit(name, status, msg, fix)

        self.all_complete.emit()

    def _check_adb(self) -> Tuple[str, str, str, str]:
        adb_path = shutil.which("adb")
        if adb_path:
            try:
                result = subprocess.run(
                    ["adb", "version"], capture_output=True, text=True, timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                if result.returncode == 0:
                    version = result.stdout.strip().split("\n")[0]
                    return ("ADB", "ok", f"Found: {version}", "")
            except Exception:
                pass
            return ("ADB", "ok", f"Found at: {adb_path}", "")
        return ("ADB", "error", "ADB not found in PATH",
                "Install Android SDK Platform Tools and add to PATH.\n"
                "Download: https://developer.android.com/studio/releases/platform-tools")

    def _check_ffmpeg(self) -> Tuple[str, str, str, str]:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ("FFmpeg", "ok", f"Found at: {ffmpeg_path}", "")
        return ("FFmpeg", "warning", "FFmpeg not found - screen capture will use fallback mode",
                "Install FFmpeg and add to PATH for better screen capture.\n"
                "Download: https://ffmpeg.org/download.html")

    def _check_scrcpy(self) -> Tuple[str, str, str, str]:
        server_path = os.path.join(self._base_dir, "lib", "scrcpy-server.jar")
        if os.path.exists(server_path):
            size_kb = os.path.getsize(server_path) / 1024
            return ("Scrcpy Server", "ok", f"Found ({size_kb:.0f} KB)", "")
        return ("Scrcpy Server", "error",
                f"Not found at: {server_path}",
                "Place scrcpy-server.jar in the lib/ directory.\n"
                "Download from: https://github.com/Genymobile/scrcpy/releases")

    def _check_ocr_models(self) -> Tuple[str, str, str, str]:
        easyocr_dir = os.path.join(self._base_dir, "models_easyocr")
        if os.path.isdir(easyocr_dir) and os.listdir(easyocr_dir):
            files = os.listdir(easyocr_dir)
            return ("OCR Models", "ok", f"Found {len(files)} model file(s)", "")
        # Check alternative locations
        for alt in ["easyocr_models", "models"]:
            alt_dir = os.path.join(self._base_dir, alt)
            if os.path.isdir(alt_dir) and os.listdir(alt_dir):
                files = os.listdir(alt_dir)
                return ("OCR Models", "ok", f"Found in {alt}/ ({len(files)} files)", "")
        return ("OCR Models", "warning",
                "OCR model files not found - OCR features may be degraded",
                "EasyOCR will download models on first use (requires internet).\n"
                "Or place model files in models_easyocr/ directory.")

    def _check_config_files(self) -> Tuple[str, str, str, str]:
        config_dir = os.path.join(self._base_dir, "config")
        config_path = os.path.join(config_dir, "config.json")
        workflows_path = os.path.join(config_dir, "workflows.json")

        missing = []
        if not os.path.exists(config_path):
            missing.append("config.json")
        if not os.path.exists(workflows_path):
            missing.append("workflows.json")

        if not missing:
            return ("Config Files", "ok", "config.json and workflows.json found", "")
        return ("Config Files", "warning",
                f"Missing: {', '.join(missing)} (will be created from defaults)",
                "Missing config files will be auto-created with default values on startup.")


class SetupWizardDialog(QDialog):
    """First-run setup wizard dialog.

    Checks for all required dependencies and provides fix suggestions.
    Can be triggered on first launch or from the settings menu.
    """

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self._base_dir = base_dir
        self._results: List[Tuple[str, str, str, str]] = []
        self._dont_show_again = False
        self.setWindowTitle("Setup Wizard - Dependency Check")
        self.setMinimumSize(550, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        title = QLabel("Welcome! Checking dependencies...")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(title)

        self._progress = QProgressBar()
        self._progress.setMaximum(5)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # Results area
        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setFontFamily("Consolas")
        self._results_text.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #e6edf3; }"
        )
        layout.addWidget(self._results_text)

        # Summary
        self._summary_label = QLabel("")
        self._summary_label.setFont(QFont("Microsoft YaHei", 11))
        layout.addWidget(self._summary_label)

        # Bottom buttons
        btn_row = QHBoxLayout()

        self._chk_dont_show = QCheckBox("Don't show again (if all OK)")
        self._chk_dont_show.stateChanged.connect(lambda s: setattr(self, '_dont_show_again', s == Qt.Checked))
        btn_row.addWidget(self._chk_dont_show)

        btn_row.addStretch()

        self._btn_recheck = QPushButton("Re-check")
        self._btn_recheck.clicked.connect(self._start_checks)
        btn_row.addWidget(self._btn_recheck)

        self._btn_close = QPushButton("Close")
        self._btn_close.setProperty("class", "primary")
        self._btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_close)

        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        self._start_checks()

    def _start_checks(self):
        self._results.clear()
        self._results_text.clear()
        self._progress.setValue(0)
        self._summary_label.setText("Checking...")
        self._btn_recheck.setEnabled(False)

        self._worker = _CheckWorker(self._base_dir, self)
        self._worker.check_complete.connect(self._on_check_complete)
        self._worker.all_complete.connect(self._on_all_complete)
        self._worker.start()

    def _on_check_complete(self, name: str, status: str, message: str, fix_hint: str):
        self._results.append((name, status, message, fix_hint))
        self._progress.setValue(len(self._results))

        icon_map = {"ok": "✅", "warning": "⚠️", "error": "❌"}
        icon = icon_map.get(status, "❓")

        html = f'<p style="margin:4px 0;"><b>{icon} {name}</b>: {message}</p>'
        if fix_hint:
            html += f'<p style="margin:2px 0 8px 20px; color:#d29922;">Fix: {fix_hint.replace(chr(10), "<br>")}</p>'

        self._results_text.append(html)

    def _on_all_complete(self):
        self._btn_recheck.setEnabled(True)

        errors = sum(1 for _, s, _, _ in self._results if s == "error")
        warnings = sum(1 for _, s, _, _ in self._results if s == "warning")
        oks = sum(1 for _, s, _, _ in self._results if s == "ok")

        if errors == 0 and warnings == 0:
            self._summary_label.setText(f"All {oks} checks passed! Ready to go.")
            self._summary_label.setStyleSheet("color: #3fb950; font-weight: bold;")
        elif errors == 0:
            self._summary_label.setText(
                f"{oks} passed, {warnings} warnings. App will work but some features may be limited."
            )
            self._summary_label.setStyleSheet("color: #d29922; font-weight: bold;")
        else:
            self._summary_label.setText(
                f"{errors} error(s), {warnings} warning(s). Please fix errors before using."
            )
            self._summary_label.setStyleSheet("color: #f85149; font-weight: bold;")

    def should_show_again(self) -> bool:
        return not self._dont_show_again

    @staticmethod
    def should_show_on_startup(base_dir: str) -> bool:
        """Check if we should show the wizard on startup."""
        flag_path = os.path.join(base_dir, "config", ".wizard_done")
        if os.path.exists(flag_path):
            return False
        return True

    def accept(self):
        """Save the 'don't show again' flag."""
        if self._dont_show_again:
            flag_path = os.path.join(self._base_dir, "config", ".wizard_done")
            try:
                os.makedirs(os.path.dirname(flag_path), exist_ok=True)
                with open(flag_path, "w") as f:
                    f.write("done")
            except Exception:
                pass
        super().accept()
