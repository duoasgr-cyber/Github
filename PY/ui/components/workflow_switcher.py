from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from core.config_manager import ConfigManager


class WorkflowSwitcher(QWidget):
    """方案切换器：下拉选择当前工作流 + 管理按钮。"""

    workflow_changed = pyqtSignal(str)
    manage_requested = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("方案")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        layout.addWidget(title)

        row = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setFont(QFont("Microsoft YaHei", 10))
        self._combo.currentTextChanged.connect(self.workflow_changed.emit)
        row.addWidget(self._combo, stretch=1)

        self._btn_manage = QPushButton("管理")
        self._btn_manage.setFixedHeight(28)
        self._btn_manage.clicked.connect(self.manage_requested.emit)
        row.addWidget(self._btn_manage)
        layout.addLayout(row)

        self.refresh()

    def refresh(self) -> None:
        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()
        workflows = self._config_manager.get_all_workflows()
        for name in sorted(workflows.keys()):
            self._combo.addItem(name)
        idx = self._combo.findText(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self._combo.blockSignals(False)

    def current_workflow(self) -> str:
        return self._combo.currentText()

    def set_current_workflow(self, name: str) -> None:
        idx = self._combo.findText(name)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)