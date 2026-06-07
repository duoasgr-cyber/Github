import copy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu, QAction
)

STEP_TYPES = [
    ("tap", "Tap"),
    ("long_press", "Long Press"),
    ("swipe", "Swipe"),
    ("keyevent", "Key Event"),
    ("wait", "Wait"),
    ("wifi", "WiFi Control"),
    ("force_stop", "Force Stop"),
    ("launch", "Launch App"),
    ("screenshot", "Screenshot"),
    ("pull_file", "Pull File"),
    ("delete_file", "Delete File"),
    ("check_image", "Image Match"),
    ("ocr_region", "OCR Recognition"),
    ("tap_point", "Precise Tap"),
    ("call_workflow", "Call Workflow"),
    ("condition", "Condition"),
    ("loop", "Loop"),
    ("input_text", "Input Text"),
    ("variable", "Variable"),
    ("adb_command", "ADB Command"),
    ("expression", "Expression"),
]

STEP_TYPE_DISPLAY = {t[0]: t[1] for t in STEP_TYPES}

# step type color map for left bar indicator
STEP_TYPE_COLORS = {
    "tap": "#1f6feb",
    "long_press": "#1f6feb",
    "swipe": "#1f6feb",
    "tap_point": "#1f6feb",
    "keyevent": "#58a6ff",
    "wait": "#8b949e",
    "wifi": "#a371f7",
    "force_stop": "#da3633",
    "launch": "#3fb950",
    "screenshot": "#d29922",
    "pull_file": "#d29922",
    "delete_file": "#da3633",
    "check_image": "#3fb950",
    "ocr_region": "#3fb950",
    "call_workflow": "#a371f7",
    "condition": "#d29922",
    "loop": "#d29922",
    "input_text": "#58a6ff",
    "variable": "#a371f7",
    "adb_command": "#f0883e",
    "expression": "#a371f7",
}

# Unified step execution states
STEP_STATE_COLORS = {
    "pending": {"fg": "#8b949e", "bg": None, "bold": False},
    "running": {"fg": "#ffffff", "bg": "#1f6feb", "bold": True},
    "success": {"fg": "#3fb950", "bg": None, "bold": False},
    "fail": {"fg": "#f85149", "bg": None, "bold": False},
    "skip": {"fg": "#d29922", "bg": None, "bold": False},
    "disabled": {"fg": "#484f58", "bg": None, "bold": False},
}


class StepListWidget(QListWidget):
    step_order_changed = pyqtSignal()
    step_clicked = pyqtSignal(int)
    step_copy_requested = pyqtSignal(int)
    step_delete_requested = pyqtSignal(int)
    step_toggle_enabled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.currentRowChanged.connect(self._on_row_changed)
        self._expanded = True
        self._raw_steps: list = []
        self._step_states: dict = {}  # index -> state string
        self.itemDoubleClicked.connect(self._toggle_expand)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _on_row_changed(self, row: int):
        self.step_clicked.emit(row)

    def load_steps(self, steps: list):
        self._raw_steps = list(steps) if steps else []
        self._step_states = {}
        self._refresh_display()

    def set_step_state(self, index: int, state: str):
        """Set the execution state of a step for unified highlighting.

        States: pending, running, success, fail, skip, disabled
        """
        self._step_states[index] = state
        if 0 <= index < self.count():
            self._apply_step_state(index, state)

    def clear_step_states(self):
        """Reset all step states to pending."""
        self._step_states.clear()
        for i in range(self.count()):
            self._apply_step_state(i, "pending")

    def _apply_step_state(self, index: int, state: str):
        """Apply visual state to a list item."""
        item = self.item(index)
        if item is None:
            return

        state_style = STEP_STATE_COLORS.get(state, STEP_STATE_COLORS["pending"])

        if state_style["bg"]:
            item.setBackground(QColor(state_style["bg"]))
        else:
            item.setBackground(QColor(0, 0, 0, 0))

        item.setForeground(QColor(state_style["fg"]))

        font = item.font()
        font.setBold(state_style["bold"])
        font.setStrikeOut(state == "disabled")
        item.setFont(font)

    def _refresh_display(self):
        self.blockSignals(True)
        self.clear()
        if not self._raw_steps:
            empty = QListWidgetItem("No steps - click 'Add Step' to begin")
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            empty.setForeground(QColor("#484f58"))
            f = empty.font()
            f.setItalic(True)
            empty.setFont(f)
            self.addItem(empty)
            self.blockSignals(False)
            return

        if self._expanded:
            for i, step in enumerate(self._raw_steps):
                step_type = step.get("type", "unknown")
                comment = step.get("comment", "")
                enabled = step.get("enabled", True)
                type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
                text = f"{i + 1}. {type_display}"
                if comment:
                    text += f" - {comment}"
                if not enabled:
                    text += " [disabled]"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, i)
                color = STEP_TYPE_COLORS.get(step_type, "#8b949e")
                item.setData(Qt.UserRole + 1, color)
                if not enabled:
                    item.setForeground(Qt.gray)
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                self.addItem(item)
                # Apply saved state
                state = self._step_states.get(i, "pending")
                if not enabled:
                    state = "disabled"
                self._apply_step_state(i, state)
        else:
            type_counts = {}
            for step in self._raw_steps:
                step_type = step.get("type", "unknown")
                type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
                type_counts[type_display] = type_counts.get(type_display, 0) + 1
            summary = "  |  ".join(f"{name}({cnt})" for name, cnt in type_counts.items())
            total = len(self._raw_steps)
            item = QListWidgetItem(f"Total {total} steps: {summary}")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.addItem(item)

        self.blockSignals(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._expanded:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        for i in range(self.count()):
            item = self.item(i)
            color_hex = item.data(Qt.UserRole + 1)
            if not color_hex:
                continue
            rect = self.visualRect(self.indexFromItem(item))
            if not rect.isValid():
                continue
            color = QColor(color_hex)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect.x(), rect.y() + 4, 4, rect.height() - 8, 2, 2)
        painter.end()

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        index = item.data(Qt.UserRole)
        if index is None:
            return

        menu = QMenu(self)

        act_copy = menu.addAction("Copy Step")
        act_delete = menu.addAction("Delete Step")
        menu.addSeparator()
        step = self._raw_steps[index] if index < len(self._raw_steps) else {}
        enabled = step.get("enabled", True)
        act_toggle = menu.addAction("Disable" if enabled else "Enable")
        menu.addSeparator()
        act_up = menu.addAction("Move Up")
        act_down = menu.addAction("Move Down")

        act_up.setEnabled(index > 0)
        act_down.setEnabled(index < len(self._raw_steps) - 1)

        action = menu.exec_(self.mapToGlobal(pos))
        if action == act_copy:
            self.step_copy_requested.emit(index)
        elif action == act_delete:
            self.step_delete_requested.emit(index)
        elif action == act_toggle:
            self.step_toggle_enabled.emit(index)
        elif action == act_up:
            self._move_step(index, index - 1)
        elif action == act_down:
            self._move_step(index, index + 1)

    def _move_step(self, from_idx, to_idx):
        if 0 <= from_idx < len(self._raw_steps) and 0 <= to_idx < len(self._raw_steps):
            self._raw_steps[from_idx], self._raw_steps[to_idx] = \
                self._raw_steps[to_idx], self._raw_steps[from_idx]
            self._refresh_display()
            self.setCurrentRow(to_idx)
            self.step_order_changed.emit()

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._refresh_display()
