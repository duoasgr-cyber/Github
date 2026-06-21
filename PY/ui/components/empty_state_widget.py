"""Empty state and blocking reason widgets for unified UX.

Provides consistent empty states and blocking indicators across all panels.
"""
from enum import Enum
from typing import Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect
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
        "title": "未连接设备",
        "hint": "通过 USB 连接设备后从侧边栏或设备管理面板选择。",
        "action_text": "前往设备管理",
    },
    BlockingReason.NO_WORKFLOW: {
        "icon": "📋",
        "title": "未选择工作流",
        "hint": "从侧边栏选择工作流，或在工作流编辑器中创建新工作流。",
        "action_text": "创建工作流",
    },
    BlockingReason.NO_OCR: {
        "icon": "🔍",
        "title": "OCR 不可用",
        "hint": "EasyOCR 模型未加载，OCR 识别功能已禁用。",
        "action_text": "",
    },
    BlockingReason.NO_SCREEN_CAPTURE: {
        "icon": "📺",
        "title": "屏幕采集不可用",
        "hint": "从已连接设备启动屏幕采集以使用图像识别功能。",
        "action_text": "",
    },
    BlockingReason.DEVICE_DISCONNECTED: {
        "icon": "🔌",
        "title": "设备已断开",
        "hint": "已连接的设备已断开，请重新连接后再试。",
        "action_text": "重新连接",
    },
    BlockingReason.OCR_LOADING: {
        "icon": "⏳",
        "title": "正在加载 OCR 模型...",
        "hint": "OCR 模型正在加载，首次使用可能需要 10-30 秒。",
        "action_text": "",
    },
    BlockingReason.WORKFLOW_EMPTY: {
        "icon": "📝",
        "title": "工作流无步骤",
        "hint": "运行前请先在工作流编辑器中添加步骤。",
        "action_text": "添加步骤",
    },
    BlockingReason.SCRCPY_FAILED: {
        "icon": "⚠️",
        "title": "屏幕采集失败",
        "hint": "无法启动屏幕采集，请检查设备连接和 scrcpy-server.jar。",
        "action_text": "",
    },
    BlockingReason.ADB_NOT_FOUND: {
        "icon": "❌",
        "title": "未找到 ADB",
        "hint": "请安装 Android SDK Platform Tools 并将 adb 添加到系统 PATH。",
        "action_text": "",
    },
    BlockingReason.CONFIG_MISSING: {
        "icon": "⚙️",
        "title": "配置缺失",
        "hint": "必需的配置文件缺失，将从默认值创建。",
        "action_text": "",
    },
}


class EmptyStateWidget(QWidget):
    """空状态占位组件 — 支持图标、消息、提示和操作按钮。"""

    action_clicked = pyqtSignal()

    def __init__(self, icon="", message="", hint="", action_text="", parent=None):
        super().__init__(parent)
        self._icon_text = icon
        self._message = message
        self._hint = hint
        self._action_text = action_text
        self._blocking_reason: Optional[BlockingReason] = None
        self._action_button: Optional[QPushButton] = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._rebuild_layout()

    def _rebuild_layout(self):
        """重建布局（当状态改变时调用）。"""
        # 清除现有子控件
        if hasattr(self, '_layout'):
            while self._layout.count():
                item = self._layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        else:
            self._layout = QVBoxLayout(self)
            self._layout.setAlignment(Qt.AlignCenter)
            self._layout.setSpacing(8)

        # 操作按钮
        if self._action_text:
            self._action_button = QPushButton(self._action_text)
            self._action_button.setObjectName("emptyStateAction")
            self._action_button.setProperty("class", "primary")
            self._action_button.setFixedHeight(32)
            self._action_button.setCursor(Qt.PointingHandCursor)
            self._action_button.clicked.connect(self.action_clicked.emit)
            self._action_button.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self._layout.addWidget(self._action_button, alignment=Qt.AlignCenter)
        else:
            self._action_button = None

    def set_state(self, icon="", message="", hint="", action_text=""):
        self._icon_text = icon
        self._message = message
        self._hint = hint
        self._action_text = action_text
        self._blocking_reason = None
        self._rebuild_layout()
        self.update()

    def set_blocking(self, reason: BlockingReason, custom_message: str = "", custom_hint: str = ""):
        """Set a standardized blocking state."""
        self._blocking_reason = reason
        info = BLOCKING_MESSAGES.get(reason, {})
        self._icon_text = info.get("icon", "⚠️")
        self._message = custom_message or info.get("title", "未知问题")
        self._hint = custom_hint or info.get("hint", "")
        self._action_text = info.get("action_text", "")
        self._rebuild_layout()
        self.update()

    def clear_blocking(self):
        self._blocking_reason = None
        self._icon_text = ""
        self._message = ""
        self._hint = ""
        self._action_text = ""
        self._rebuild_layout()
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

    def __init__(self, text="加载中...", parent=None):
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
