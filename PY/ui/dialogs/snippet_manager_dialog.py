import json
import os
import copy
import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QInputDialog, QMessageBox, QWidget, QTextEdit
)

logger = logging.getLogger(__name__)


class SnippetManager:
    """Manage code snippets for workflow steps."""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._snippets_path = os.path.join(base_dir, "snippets", "snippets.json")
        self._snippets = {}
        self._load()

    def _load(self):
        if os.path.exists(self._snippets_path):
            try:
                with open(self._snippets_path, "r", encoding="utf-8") as f:
                    self._snippets = json.load(f)
            except Exception as e:
                logger.warning("Failed to load snippets: %s", e)
                self._snippets = {}
        else:
            self._snippets = {}

    def _save(self):
        os.makedirs(os.path.dirname(self._snippets_path), exist_ok=True)
        with open(self._snippets_path, "w", encoding="utf-8") as f:
            json.dump(self._snippets, f, ensure_ascii=False, indent=2)

    def list_snippets(self) -> list:
        return list(self._snippets.keys())

    def get_snippet(self, snippet_id: str) -> dict:
        return self._snippets.get(snippet_id, {})

    def add_snippet(self, snippet_id: str, steps: list):
        self._snippets[snippet_id] = {"id": snippet_id, "steps": steps}
        self._save()

    def delete_snippet(self, snippet_id: str):
        if snippet_id in self._snippets:
            del self._snippets[snippet_id]
            self._save()

    def instantiate_snippet(self, snippet_id: str) -> list:
        snippet = self._snippets.get(snippet_id, {})
        return copy.deepcopy(snippet.get("steps", []))


class SnippetManagerDialog(QDialog):
    """Dialog for managing and selecting code snippets."""

    snippet_selected = pyqtSignal(str)

    def __init__(self, snippet_manager: SnippetManager, parent=None):
        super().__init__(parent)
        self._manager = snippet_manager
        self.setWindowTitle("代码片段管理")
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("代码片段")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self._list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("新建")
        btn_add.clicked.connect(self._add_snippet)
        btn_layout.addWidget(btn_add)

        btn_delete = QPushButton("删除")
        btn_delete.clicked.connect(self._delete_snippet)
        btn_layout.addWidget(btn_delete)

        btn_layout.addStretch()

        btn_use = QPushButton("使用")
        btn_use.clicked.connect(self._use_snippet)
        btn_layout.addWidget(btn_use)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        self._list.clear()
        for name in self._manager.list_snippets():
            self._list.addItem(name)

    def _add_snippet(self):
        name, ok = QInputDialog.getText(self, "新建片段", "片段名称")
        if not ok or not name.strip():
            return
        self._manager.add_snippet(name.strip(), [])
        self._refresh_list()

    def _delete_snippet(self):
        row = self._list.currentRow()
        if row < 0:
            return
        name = self._list.item(row).text()
        reply = QMessageBox.question(self, "删除", f"确定删除片段 '{name}' 吗?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._manager.delete_snippet(name)
            self._refresh_list()

    def _use_snippet(self):
        row = self._list.currentRow()
        if row < 0:
            return
        name = self._list.item(row).text()
        self.snippet_selected.emit(name)
        self.accept()
