"""Toast 通知组件 — 右上角短暂弹出提示。"""

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QFont, QColor, QPainter, QPen


class ToastNotification(QWidget):
    """单条 Toast 通知。"""

    def __init__(self, message, toast_type="info", parent=None):
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._message = message
        self._toast_type = toast_type
        self._duration = 2500  # 显示时长 ms

        self._init_ui()
        self._init_animation()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        # 图标 + 消息
        row = QHBoxLayout()
        row.setSpacing(8)

        icons = {
            "info": "ℹ",
            "success": "✓",
            "warning": "⚠",
            "error": "✗",
        }
        colors = {
            "info": "#58a6ff",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#f85149",
        }

        icon_label = QLabel(icons.get(self._toast_type, "ℹ"))
        icon_label.setStyleSheet(f"color: {colors.get(self._toast_type, '#58a6ff')}; font-size: 16px; font-weight: bold;")
        row.addWidget(icon_label)

        msg_label = QLabel(self._message)
        msg_label.setFont(QFont("Microsoft YaHei", 10))
        msg_label.setStyleSheet("color: #e6edf3;")
        msg_label.setWordWrap(True)
        msg_label.setMaximumWidth(300)
        row.addWidget(msg_label, stretch=1)

        layout.addLayout(row)

    def _init_animation(self):
        """初始化淡入淡出动画。"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # 淡入动画
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.InOutCubic)

        # 淡出动画
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InOutCubic)
        self._fade_out.finished.connect(self.close)

    def show_toast(self):
        """显示 Toast 通知。"""
        self.show()
        self.raise_()
        self._fade_in.start()

        # 定时淡出
        QTimer.singleShot(self._duration, self._fade_out.start)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        colors = {
            "info": "#1f6feb",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#da3633",
        }
        accent_color = colors.get(self._toast_type, "#1f6feb")

        # 背景
        painter.setBrush(QColor("#161b22"))
        painter.setPen(QPen(QColor("#30363d"), 1))
        painter.drawRoundedRect(self.rect(), 8, 8)

        # 左侧强调线
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(accent_color))
        painter.drawRoundedRect(0, 0, 3, self.height(), 2, 2)

        painter.end()


class ToastManager:
    """Toast 通知管理器 — 管理多条通知的堆叠显示。"""

    def __init__(self, parent=None):
        self._parent = parent
        self._active_toasts = []
        self._spacing = 8
        self._margin_top = 60
        self._margin_right = 20

    def show(self, message, toast_type="info", duration=2500):
        """显示一条 Toast 通知。"""
        toast = ToastNotification(message, toast_type, self._parent)
        toast._duration = duration

        # 计算位置（右上角堆叠）
        if self._parent:
            parent_rect = self._parent.rect()
            x = parent_rect.right() - toast.width() - self._margin_right
        else:
            x = 1600

        y_offset = self._margin_top
        for t in self._active_toasts:
            if t.isVisible():
                y_offset += t.height() + self._spacing

        toast.move(x, y_offset)
        toast.show_toast()
        toast.destroyed.connect(lambda: self._on_toast_destroyed(toast))
        self._active_toasts.append(toast)

    def _on_toast_destroyed(self, toast):
        """Toast 销毁时从列表移除。"""
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)

    def info(self, message, duration=2500):
        self.show(message, "info", duration)

    def success(self, message, duration=2500):
        self.show(message, "success", duration)

    def warning(self, message, duration=3000):
        self.show(message, "warning", duration)

    def error(self, message, duration=4000):
        self.show(message, "error", duration)
