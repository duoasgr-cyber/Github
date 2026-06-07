"""Snippet manager dialog for reusing workflow step templates."""
import json
import os
import copy
import logging
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QFileDialog,
    QSplitter, QTextEdit, QWidget, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

logger = logging.getLogger(__name__)


class SnippetManager:
    """Manages workflow step snippets (reusable templates)."""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._snippets_path = os.path.join(base_dir, "snippets", "snippets.json")
        self._user_snippets_path = os.path.join(base_dir, "config", "user_snippets.json")
        self._snippets: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load built-in and user snippets."""
        self._snippets.clear()

        # Load built-in snippets
        if os.path.exists(self._snippets_path):
            try:
                with open(self._snippets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._snippets.update(data.get("snippets", {}))
                logger.info("Loaded %d built-in snippets", len(data.get("snippets", {})))
            except Exception as e:
                logger.warning("Failed to load built-in snippets: %s", e)

        # Load user snippets (override built-in)
        if os.path.exists(self._user_snippets_path):
            try:
                with open(self._user_snippets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._snippets.update(data.get("snippets", {}))
                logger.info("Loaded %d user snippets", len(data.get("snippets", {})))
            except Exception as e:
                logger.warning("Failed to load user snippets: %s", e)

    def save_user_snippet(self, snippet_id: str, snippet: dict):
        """Save a user-defined snippet."""
        user_snippets = {}
        if os.path.exists(self._user_snippets_path):
            try:
                with open(self._user_snippets_path, "r", encoding="utf-8") as f:
                    user_snippets = json.load(f)
            except Exception:
                pass

        if "snippets" not in user_snippets:
            user_snippets["snippets"] = {}
        user_snippets["snippets"][snippet_id] = snippet

        os.makedirs(os.path.dirname(self._user_snippets_path), exist_ok=True)
        with open(self._user_snippets_path, "w", encoding="utf-8") as f:
            json.dump(user_snippets, f, ensure_ascii=False, indent=2)

        self._snippets[snippet_id] = snippet
        logger.info("Saved user snippet: %s", snippet_id)

    def delete_snippet(self, snippet_id: str):
        """Delete a snippet (only user snippets can be deleted)."""
        if snippet_id in self._snippets:
            del self._snippets[snippet_id]

        if os.path.exists(self._user_snippets_path):
            try:
                with open(self._user_snippets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if snippet_id in data.get("snippets", {}):
                    del data["snippets"][snippet_id]
                    with open(self._user_snippets_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("Failed to delete snippet: %s", e)

    def get_snippet(self, snippet_id: str) -> Optional[dict]:
        return self._snippets.get(snippet_id)

    def get_all_snippets(self) -> Dict[str, dict]:
        return dict(self._snippets)

    def get_snippets_by_category(self, category: str) -> Dict[str, dict]:
        return {k: v for k, v in self._snippets.items() if v.get("category") == category}

    def instantiate_snippet(self, snippet_id: str, params: dict = None) -> list:
        """Create step(s) from a snippet with given parameters."""
        snippet = self.get_snippet(snippet_id)
        if not snippet:
            return []

        params = params or {}
        step_template = copy.deepcopy(snippet.get("step_template", {}))

        # Apply parameters to the step
        self._apply_params(step_template, params, snippet.get("parameters", []))
        steps = [step_template]

        # Add follow-up step if defined
        follow_up = snippet.get("follow_up")
        if follow_up:
            fu_step = copy.deepcopy(follow_up)
            self._apply_params(fu_step, params, snippet.get("parameters", []))
            steps.append(fu_step)

        return steps

    def _apply_params(self, step: dict, params: dict, param_defs: list):
        """Apply parameter values to a step dict."""
        for pdef in param_defs:
            name = pdef["name"]
            if name in params:
                value = params[name]
            else:
                value = pdef.get("default", "")

            # Handle nested paths like "region.left"
            if "." in name:
                parts = name.split(".")
                target = step
                for part in parts[:-1]:
                    target = target.get(part, {})
                target[parts[-1]] = value
            else:
                # For condition/template params
                if name == "template" and "condition" in step:
                    step["condition"]["template"] = value
                elif name == "template":
                    step[name] = value
                else:
                    step[name] = value

    def import_snippet(self, file_path: str) -> Optional[str]:
        """Import a snippet from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            snippet_id = data.get("id", os.path.splitext(os.path.basename(file_path))[0])
            self.save_user_snippet(snippet_id, data)
            return snippet_id
        except Exception as e:
            logger.error("Failed to import snippet: %s", e)
            return None

    def export_snippet(self, snippet_id: str, file_path: str) -> bool:
        """Export a snippet to a JSON file."""
        snippet = self.get_snippet(snippet_id)
        if not snippet:
            return False
        try:
            data = dict(snippet)
            data["id"] = snippet_id
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error("Failed to export snippet: %s", e)
            return False


class SnippetManagerDialog(QDialog):
    """Dialog for managing workflow step snippets."""

    snippet_selected = pyqtSignal(str)  # emits snippet_id when user selects one to use

    def __init__(self, snippet_manager: SnippetManager, parent=None):
        super().__init__(parent)
        self._manager = snippet_manager
        self.setWindowTitle("Step Snippet Library")
        self.setMinimumSize(600, 450)
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Category filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Category:"))
        self._category_combo = QComboBox()
        self._category_combo.addItem("All")
        self._category_combo.currentIndexChanged.connect(self._refresh_list)
        filter_row.addWidget(self._category_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Horizontal)

        # Snippet list
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setFont(QFont("Microsoft YaHei", 10))
        self._list.currentItemChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self._list)
        splitter.addWidget(list_widget)

        # Preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFontFamily("Consolas")
        self._preview.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #e6edf3; }"
        )
        preview_layout.addWidget(QLabel("Preview:"))
        preview_layout.addWidget(self._preview)
        splitter.addWidget(preview_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Buttons
        btn_row = QHBoxLayout()
        btn_use = QPushButton("Use Snippet")
        btn_use.setProperty("class", "primary")
        btn_use.clicked.connect(self._on_use)
        btn_row.addWidget(btn_use)

        btn_import = QPushButton("Import")
        btn_import.clicked.connect(self._on_import)
        btn_row.addWidget(btn_import)

        btn_export = QPushButton("Export")
        btn_export.clicked.connect(self._on_export)
        btn_row.addWidget(btn_export)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _refresh_list(self):
        self._list.clear()
        category = self._category_combo.currentText()
        snippets = self._manager.get_all_snippets()

        categories = set()
        for sid, snippet in snippets.items():
            cat = snippet.get("category", "general")
            categories.add(cat)
            if category != "All" and cat != category:
                continue
            name = snippet.get("name", sid)
            item = QListWidgetItem(f"{name} ({sid})")
            item.setData(Qt.UserRole, sid)
            self._list.addItem(item)

        # Update category combo
        current = self._category_combo.currentText()
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        self._category_combo.addItem("All")
        for cat in sorted(categories):
            self._category_combo.addItem(cat)
        idx = self._category_combo.findText(current)
        self._category_combo.setCurrentIndex(max(0, idx))
        self._category_combo.blockSignals(False)

    def _on_selection_changed(self, current, previous):
        if current is None:
            self._preview.clear()
            return
        snippet_id = current.data(Qt.UserRole)
        snippet = self._manager.get_snippet(snippet_id)
        if snippet:
            self._preview.setPlainText(json.dumps(snippet, indent=2, ensure_ascii=False))

    def _on_use(self):
        current = self._list.currentItem()
        if current is None:
            return
        snippet_id = current.data(Qt.UserRole)
        self.snippet_selected.emit(snippet_id)
        self.accept()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Snippet", "", "JSON (*.json)")
        if path:
            result = self._manager.import_snippet(path)
            if result:
                self._refresh_list()
                QMessageBox.information(self, "Imported", f"Snippet '{result}' imported.")
            else:
                QMessageBox.warning(self, "Failed", "Could not import snippet.")

    def _on_export(self):
        current = self._list.currentItem()
        if current is None:
            return
        snippet_id = current.data(Qt.UserRole)
        path, _ = QFileDialog.getSaveFileName(self, "Export Snippet", f"{snippet_id}.json", "JSON (*.json)")
        if path:
            if self._manager.export_snippet(snippet_id, path):
                QMessageBox.information(self, "Exported", f"Snippet exported to {path}")
            else:
                QMessageBox.warning(self, "Failed", "Could not export snippet.")
