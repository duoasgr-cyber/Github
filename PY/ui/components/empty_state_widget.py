"""Empty state and blocking reason widgets for unified UX.

Provides consistent empty states and blocking indicators across all panels.
"""
from enum import Enum
from typing import Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPainter, QColor


class BlockingReason(Enum):
    """Standard blocking reasons across the application."""
    NO_DEVICE = "no_device"
    NO_WORKFLOW = "no_workflow"
    NO_OCR = "no_ocr"
    NO_SCREEN_CAPTURE = "no_screen_capture"
    DEVICE_DISCONNECTED = "device_disconnected"
    OCR_LOADING = "ocr_loading"
    WORKFLOW_EMPTY = "workflow_empty"
    SCRCPY_FAILED = "scrcpy_failed"
    ADB_NOT_FOUND = "adb_not_found"
    CONFIG_MISSING = "config_missing"
    CUSTOM = "custom"


BLOCKING_MESSAGES = {
    BlockingReason.NO_DEVICE: {
        "icon": "📱",
        "title": "No Device Connected",
        "hint": "Connect a device via USB and select it from the sidebar or Device Management panel.",
    },
    BlockingReason.NO_WORKFLOW: {
        "icon": "📋",
        "title": "No Workflow Selected",
        "hint": "Select a workflow from the sidebar or create a new one in the Workflow Editor.",
    },
    BlockingReason.NO_OCR: {
        "icon": "🔍",
        "title": "OCR Not Available",
        "hint": "EasyOCR models are not loaded. OCR recognition features are disabled.",
    },
    BlockingReason.NO_SCREEN_CAPTURE: {
        "icon": "📺",
        "title": "Screen Capture Not Available",
        "hint": "Start screen capture from a connected device to use image recognition features.",
    },
    BlockingReason.DEVICE_DISCONNECTED: {
        "icon": "🔌",
        "title": "Device Disconnected",
        "hint": "The connected device has been disconnected. Reconnect and try again.",
    },
    BlockingReason.OCR_LOADING: {
        "icon": "⏳",
        "title": "Loading OCR Models...",
        "hint": "OCR models are loading. This may take 10-30 seconds on first use.",
    },
    BlockingReason.WORKFLOW_EMPTY: {
        "icon": "📝",
        "title": "Workflow Has No Steps",
        "hint": "Add steps to this workflow using the Workflow Editor before running.",
    },
    BlockingReason.SCRCPY_FAILED: {
        "icon": "⚠️",
        "title": "Screen Capture Failed",
        "hint": "Could not start screen capture. Check device connection and scrcpy-server.jar.",
    },
    BlockingReason.ADB_NOT_FOUND: {
        "icon": "❌",
        "title": "ADB Not Found",
        "hint": "Install Android SDK Platform Tools and add adb to your system PATH.",
    },
    BlockingReason.CONFIG_MISSING: {
        "icon": "⚙️",
        "title": "Configuration Missing",
        "hint": "Required configuration files are missing. They will be created from defaults.",
    },
}


class EmptyStateWidget(QWidget):
    """Empty state placeholder with icon text and message."""

    action_clicked = pyqtSignal()

    def __init__(self, icon="", message="", hint="", action_text="", parent=None):
        super().__init__(parent)
        self._icon_text = icon
        self._message = message
        self._hint = hint
        self._action_text = action_text
        self._blocking_reason: Optional[BlockingReason] = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def set_state(self, icon="", message="", hint="", action_text=""):
        self._icon_text = icon
        self._message = message
        self._hint = hint
        self._action_text = action_text
        self._blocking_reason = None
        self.update()

    def set_blocking(self, reason: BlockingReason, custom_message: str = "", custom_hint: str = ""):
        """Set a standardized blocking state."""
        self._blocking_reason = reason
        info = BLOCKING_MESSAGES.get(reason, {})
        self._icon_text = info.get("icon", "⚠️")
        self._message = custom_message or info.get("title", "Unknown Issue")
        self._hint = custom_hint or info.get("hint", "")
        self.update()

    def clear_blocking(self):
        self._blocking_reason = None
        self._icon_text = ""
        self._message = ""
        self._hint = ""
        self.update()

    def get_blocking_reason(self) -> Optional[BlockingReason]:
        return self._blocking_reason

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() // 2
        cy = self.height() // 2

        # Background tint for blocking states
        if self._blocking_reason:
            painter.fillRect(self.rect(), QColor(13, 17, 23, 40))

        # Icon
        if self._icon_text:
            painter.setFont(QFont("Segoe UI Emoji", 36))
            painter.setPen(QColor("#30363d"))
            icon_rect = painter.boundingRect(
                0, cy - 80, self.width(), 60,
                Qt.AlignCenter, self._icon_text
            )
            painter.drawText(icon_rect, Qt.AlignCenter, self._icon_text)

        # Message
        if self._message:
            painter.setFont(QFont("Microsoft YaHei", 13))
            painter.setPen(QColor("#8b949e"))
            msg_rect = painter.boundingRect(
                0, cy, self.width(), 30,
                Qt.AlignCenter, self._message
            )
            painter.drawText(msg_rect, Qt.AlignCenter, self._message)

        # Hint
        if self._hint:
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.setPen(QColor("#484f58"))
            hint_rect = painter.boundingRect(
                0, cy + 35, self.width(), 48,
                Qt.AlignCenter, self._hint
            )
            painter.drawText(hint_rect, Qt.AlignCenter | Qt.TextWordWrap, self._hint)

        painter.end()


class LoadingOverlay(QWidget):
    """Semi-transparent loading overlay with spinner text."""

    def __init__(self, text="Loading...", parent=None):
        super().__init__(parent)
        self._text = text
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()

    def start(self, text=None):
        if text:
            self._text = text
        self._angle = 0
        self.show()
        self._timer.start(50)
        if self.parent():
            self.resize(self.parent().size())

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(13, 17, 23, 160))

        cx = self.width() // 2
        cy = self.height() // 2

        # Spinner arc
        from PyQt5.QtCore import QRectF
        painter.setPen(QColor("#1f6feb"))
        pen = painter.pen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        arc_rect = QRectF(cx - 16, cy - 36, 32, 32)
        painter.drawArc(arc_rect, self._angle * 16, 270 * 16)

        # Text
        painter.setFont(QFont("Microsoft YaHei", 11))
        painter.setPen(QColor("#8b949e"))
        painter.drawText(
            0, cy + 10, self.width(), 24,
            Qt.AlignCenter, self._text
        )
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
