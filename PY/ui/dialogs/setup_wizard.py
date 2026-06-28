import os
import json
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QLineEdit, QGroupBox,
    QScrollArea, QWidget, QMessageBox
)

logger = logging.getLogger(__name__)


class SetupWizardDialog(QDialog):
    """First-run setup wizard dialog."""

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self._base_dir = base_dir
        self.setWindowTitle("初始设置向导")
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("欢迎使用三角洲自动抢购工具")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)

        desc = QLabel("请完成以下初始设置，或跳过使用默认配置。")
        desc.setFont(QFont("Microsoft YaHei", 10))
        desc.setStyleSheet("color: #8b949e;")
        layout.addWidget(desc)

        # ADB path
        adb_group = QGroupBox("ADB 设置")
        adb_layout = QVBoxLayout(adb_group)
        adb_path_layout = QHBoxLayout()
        self._adb_path_edit = QLineEdit("adb")
        self._adb_path_edit.setFont(QFont("Microsoft YaHei", 10))
        adb_path_layout.addWidget(QLabel("ADB 路径:"))
        adb_path_layout.addWidget(self._adb_path_edit, stretch=1)
        adb_layout.addLayout(adb_path_layout)
        layout.addWidget(adb_group)

        # OCR settings
        ocr_group = QGroupBox("OCR 设置")
        ocr_layout = QVBoxLayout(ocr_group)
        self._ocr_gpu_check = QCheckBox("使用 GPU 加速 OCR")
        self._ocr_gpu_check.setFont(QFont("Microsoft YaHei", 10))
        ocr_layout.addWidget(self._ocr_gpu_check)
        layout.addWidget(ocr_group)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_skip = QPushButton("跳过")
        btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(btn_skip)

        btn_finish = QPushButton("完成")
        btn_finish.clicked.connect(self._on_finish)
        btn_layout.addWidget(btn_finish)

        layout.addLayout(btn_layout)

    def _on_finish(self):
        self.accept()

    @staticmethod
    def should_show_on_startup(base_dir: str) -> bool:
        """Check if the setup wizard should be shown on first run."""
        wizard_flag = os.path.join(base_dir, "config", ".wizard_done")
        return not os.path.exists(wizard_flag)
