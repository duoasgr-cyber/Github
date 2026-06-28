"""截图选择器组件 - 基于嵌入式投屏的坐标选择器。

使用 EmbeddedMirrorView 实现高清投屏和坐标选择功能。
"""

import logging
import re
import subprocess
import sys
import threading
import time

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import numpy as np

from ui.components.embedded_mirror_widget import EmbeddedMirrorView

logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._markers: list[tuple[int, int]] = []
        self._active_marker: int = -1
        self._zoom: float = 1.0
        self._calibration_mode: bool = False
        self._calibration_offset: QPoint = QPoint(0, 0)
        self._base_resolution: tuple[int, int] = (2400, 1080)
        self._drag_start: QPoint | None = None
        self._dragging_marker: int = -1
        self.setMinimumSize(200, 150)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._update_display()

    def set_zoom(self, zoom: float):
        self._zoom = max(0.1, min(zoom, 5.0))
        self._update_display()

    def set_calibration_mode(self, enabled: bool):
        self._calibration_mode = enabled
        self._update_display()

    def set_base_resolution(self, width: int, height: int):
        self._base_resolution = (width, height)

    def add_marker(self, x: int, y: int):
        self._markers.append((x, y))
        self._active_marker = len(self._markers) - 1
        self._update_display()

    def clear_markers(self):
        self._markers.clear()
        self._active_marker = -1
        self._calibration_offset = QPoint(0, 0)
        self._update_display()

    def get_markers(self) -> list[tuple[int, int]]:
        return list(self._markers)

    def get_active_marker(self) -> tuple[int, int] | None:
        if 0 <= self._active_marker < len(self._markers):
            return self._markers[self._active_marker]
        return None

    def _img_to_display(self, ix: int, iy: int) -> tuple[int, int]:
        dx = int(ix * self._zoom)
        dy = int(iy * self._zoom)
        return dx, dy

    def _display_to_img(self, dx: int, dy: int) -> tuple[int, int]:
        ix = int(dx / self._zoom)
        iy = int(dy / self._zoom)
        return ix, iy

    def _img_to_device(self, ix: int, iy: int) -> tuple[int, int]:
        if self._pixmap is None:
            return ix, iy
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        if pw == 0 or ph == 0:
            return ix, iy
        bw, bh = self._base_resolution
        dev_x = int(round(ix * bw / pw))
        dev_y = int(round(iy * bh / ph))
        return dev_x, dev_y

    def _device_to_img(self, dev_x: int, dev_y: int) -> tuple[int, int]:
        if self._pixmap is None:
            return dev_x, dev_y
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        bw, bh = self._base_resolution
        if bw == 0 or bh == 0:
            return dev_x, dev_y
        ix = int(dev_x * pw / bw)
        iy = int(dev_y * ph / bh)
        return ix, iy

    def _update_display(self):
        if self._pixmap is None:
            return
        new_w = int(self._pixmap.width() * self._zoom)
        new_h = int(self._pixmap.height() * self._zoom)
        if new_w <= 0 or new_h <= 0:
            return
        scaled = self._pixmap.scaled(new_w, new_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        draw_pixmap = QPixmap(scaled)
        painter = QPainter(draw_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._calibration_mode:
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            grid_step = int(100 * self._zoom)
            if grid_step > 0:
                x = grid_step
                while x < new_w:
                    painter.drawLine(x, 0, x, new_h)
                    x += grid_step
                y = grid_step
                while y < new_h:
                    painter.drawLine(0, y, new_w, y)
                    y += grid_step

        for i, (mx, my) in enumerate(self._markers):
            dx, dy = self._img_to_display(mx, my)
            is_active = (i == self._active_marker)
            pen_width = 3 if is_active else 2
            cross_size = 12 if is_active else 8

            shadow_pen = QPen(QColor(0, 0, 0, 160), pen_width + 1)
            painter.setPen(shadow_pen)
            painter.drawLine(dx - cross_size, dy, dx + cross_size, dy)
            painter.drawLine(dx, dy - cross_size, dx, dy + cross_size)

            color = QColor("#ff0000") if not is_active else QColor("#00ffff")
            pen = QPen(color, pen_width)
            painter.setPen(pen)
            painter.drawLine(dx - cross_size, dy, dx + cross_size, dy)
            painter.drawLine(dx, dy - cross_size, dy, dy + cross_size)

            if is_active:
                painter.setPen(QPen(QColor("#00ffff"), 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(dx - 15, dy - 15, 30, 30)

            dev_x, dev_y = self._img_to_device(mx, my)
            text = f"({dev_x}, {dev_y})"
            if self._calibration_mode and is_active:
                ox = self._calibration_offset.x()
                oy = self._calibration_offset.y()
                if ox != 0 or oy != 0:
                    text += f" Δ({ox},{oy})"
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            font = QFont("Consolas", 9)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text) + 8
            th = fm.height() + 4
            text_rect = QRect(dx + 8, dy - th, tw, th)
            painter.fillRect(text_rect, QColor(0, 0, 0, 160))
            painter.drawText(text_rect, Qt.AlignCenter, text)

        painter.end()
        self.setPixmap(draw_pixmap)
        self.setMinimumSize(new_w, new_h)

    def mousePressEvent(self, event):
        if self._pixmap is None:
            return
        if event.button() == Qt.LeftButton:
            ix, iy = self._display_to_img(event.pos().x(), event.pos().y())
            if 0 <= ix < self._pixmap.width() and 0 <= iy < self._pixmap.height():
                self._markers.append((ix, iy))
                self._active_marker = len(self._markers) - 1
                dev_x, dev_y = self._img_to_device(ix, iy)
                self.point_clicked.emit(dev_x, dev_y)
                self._update_display()
        elif event.button() == Qt.RightButton:
            if self._markers:
                self._markers.pop()
                self._active_marker = len(self._markers) - 1
                self._update_display()

    def mouseMoveEvent(self, event):
        if self._pixmap is None:
            return
        ix, iy = self._display_to_img(event.pos().x(), event.pos().y())
        if 0 <= ix < self._pixmap.width() and 0 <= iy < self._pixmap.height():
            dev_x, dev_y = self._img_to_device(ix, iy)
            self.mouse_position.emit(dev_x, dev_y)

    def keyPressEvent(self, event):
        if not self._calibration_mode or self._active_marker < 0:
            return super().keyPressEvent(event)
        if self._active_marker >= len(self._markers):
            return super().keyPressEvent(event)

        step = 1
        if event.modifiers() & Qt.ShiftModifier:
            step = 5

        mx, my = self._markers[self._active_marker]
        if event.key() == Qt.Key_Left:
            mx -= step
        elif event.key() == Qt.Key_Right:
            mx += step
        elif event.key() == Qt.Key_Up:
            my -= step
        elif event.key() == Qt.Key_Down:
            my += step
        else:
            return super().keyPressEvent(event)

        self._markers[self._active_marker] = (mx, my)
        self._calibration_offset = QPoint(
            mx - self._markers[self._active_marker][0] if self._markers else 0,
            my - self._markers[self._active_marker][1] if self._markers else 0,
        )
        dev_x, dev_y = self._img_to_device(mx, my)
        self.point_clicked.emit(dev_x, dev_y)
        self._update_display()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self._zoom * 1.1, 5.0)
        elif delta < 0:
            self._zoom = max(self._zoom / 1.1, 0.1)
        self._update_display()


class ScreenshotPicker(QWidget):
    """截图选择器 - 嵌入式投屏坐标选择器。"""

    point_selected = pyqtSignal(int, int)
    mouse_moved = pyqtSignal(int, int)
    pickup_completed = pyqtSignal(int, int)  # 选点模式完成（设备坐标）

    def __init__(self, screen_capture=None, device_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._device_manager = device_manager
        self._config_manager = config_manager
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 工具栏容器（使用 QWidget 包装以确保正确的层级和高度）
        toolbar_container = QWidget()
        toolbar_container.setFixedHeight(34)
        toolbar_container.setStyleSheet("background-color: #161b22;")
        
        toolbar = QHBoxLayout(toolbar_container)
        toolbar.setContentsMargins(4, 4, 4, 4)
        toolbar.setSpacing(4)

        btn_style = (
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; "
            "padding: 4px 8px; min-width: 50px; }"
            "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
            "QPushButton:pressed { background-color: #161b22; }"
        )

        self._btn_clear = QPushButton("清除标注")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.setStyleSheet(btn_style)
        self._btn_clear.clicked.connect(self.clear_markers)
        toolbar.addWidget(self._btn_clear)

        self._btn_fit = QPushButton("适配窗口")
        self._btn_fit.setFixedHeight(26)
        self._btn_fit.setStyleSheet(btn_style)
        self._btn_fit.clicked.connect(self._on_fit)
        toolbar.addWidget(self._btn_fit)

        self._btn_1to1 = QPushButton("1:1")
        self._btn_1to1.setFixedHeight(26)
        self._btn_1to1.setStyleSheet(btn_style)
        self._btn_1to1.clicked.connect(self._on_1to1)
        toolbar.addWidget(self._btn_1to1)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setFixedHeight(26)
        self._btn_reset.setStyleSheet(btn_style)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        # 缩放百分比 - 已隐藏
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._zoom_label.setMinimumWidth(40)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        # toolbar.addWidget(self._zoom_label)

        toolbar.addStretch()

        # 校准模式按钮
        self._btn_calibrate = QPushButton("校准模式")
        self._btn_calibrate.setFixedHeight(26)
        self._btn_calibrate.setStyleSheet(btn_style)
        self._btn_calibrate.setCheckable(True)
        self._btn_calibrate.clicked.connect(self._on_calibrate_toggled)
        toolbar.addWidget(self._btn_calibrate)

        # 状态指示 - 已隐藏
        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._status_label.setMinimumWidth(60)
        # toolbar.addWidget(self._status_label)

        layout.addWidget(toolbar_container)

        # 投屏视图
        self._view = EmbeddedMirrorView()
        self._view.point_clicked.connect(self._on_point_clicked)
        self._view.mouse_moved.connect(self._on_mouse_moved)
        self._view.pickup_completed.connect(self._on_pickup_completed)
        layout.addWidget(self._view, stretch=1)

        # 底部信息栏 - 已隐藏
        self._coord_label = QLabel("设备坐标: (-, -)")
        self._coord_label.setFont(QFont("Consolas", 10))
        
        self._resolution_label = QLabel("分辨率: -")
        self._resolution_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        
        self._markers_label = QLabel("标记: 0")
        self._markers_label.setStyleSheet("color: #8b949e; font-size: 11px;")

    def _connect_signals(self):
        """连接信号。"""
        if self._screen_capture:
            # 不连接 frame_captured 信号，改用定时器轮询避免事件队列堆积
            self._screen_capture.connection_lost.connect(self._on_connection_lost)
            self._screen_capture.connection_restored.connect(self._on_connection_restored)

    def _on_frame_captured(self, frame: np.ndarray):
        """接收到新帧（已弃用，改用定时器轮询）。"""
        pass

    def _poll_latest_frame(self):
        """定时轮询最新帧（替代信号槽，避免事件队列堆积）。"""
        if not self._connected or not self._screen_capture:
            return
        frame = self._screen_capture.get_current_frame()
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)
            # 同步分辨率信息（确保与 view 一致）
            h, w = frame.shape[:2]
            if self._device_width == 0 and w > 0:
                self._device_width = w
                self._device_height = h
                # 关键修复：同步设置 view 的设备分辨率，否则 EmbeddedMirrorView._device_width
                # 始终为 0，导致所有点击被忽略（"点击被忽略: _device_width=0"）
                self._view.set_device_resolution(w, h)
            # 如果 view 已通过帧尺寸回退获得分辨率，也同步到自身，
            # 保证后续 tap 发送和坐标显示使用一致的分辨率。
            view_w, view_h = self._view.get_device_resolution()
            if self._device_width == 0 and view_w > 0:
                self._device_width = view_w
                self._device_height = view_h

    def _display_frame(self, frame: np.ndarray):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        if hasattr(QImage, "Format_BGR888"):
            q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        else:
            q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_img)
        self._sync_base_resolution(w, h)
        self._image_label.set_pixmap(pixmap)

    def _sync_base_resolution(self, frame_w: int, frame_h: int):
        """Ensure base_resolution matches the device's real resolution in the
        frame's orientation.

        The captured frame is pre-scaled by scrcpy/screencap and rendered in
        the device's current orientation. The image-pixel -> device-pixel
        mapping in _img_to_device is only correct when base_resolution equals
        the real device resolution AND shares the frame's orientation. Without
        this sync, base_resolution stays at the hardcoded default and the
        computed device coordinates land in the wrong place.
        """
        dw, dh = 0, 0

        if self._device_manager is not None:
            try:
                res = self._device_manager.get_device_resolution()
            except Exception:
                res = None
            if res:
                dw, dh = res

        if (dw <= 0 or dh <= 0) and self._config_manager is not None:
            try:
                base = self._config_manager.get_config("device.base_resolution", {}) or {}
            except Exception:
                base = {}
            if isinstance(base, dict):
                bw_cfg = base.get("width", 0)
                bh_cfg = base.get("height", 0)
                if bw_cfg > 0 and bh_cfg > 0:
                    dw, dh = bw_cfg, bh_cfg

        if dw <= 0 or dh <= 0:
            # No reliable source available; keep current base_resolution.
            return

        # wm size reports the natural orientation, but the frame is captured in
        # the device's current orientation. Align them so X/Y are not swapped.
        if (frame_w >= frame_h) != (dw >= dh):
            dw, dh = dh, dw

        self._image_label.set_base_resolution(dw, dh)

    def clear_markers(self):
        """清除所有标记。"""
        self._view.clear_markers()
        # self._coord_label.setText("设备坐标: (-, -)")
        # self._update_markers_label()

    def get_selected_point(self):
        """获取选中的坐标点。"""
        return self._view.get_active_marker()

    def set_calibration_mode(self, enabled: bool):
        """设置校准模式。"""
        self._btn_calibrate.setChecked(enabled)
        self._on_calibrate_toggled(enabled)

    def set_base_resolution(self, width: int, height: int):
        """设置设备分辨率（外部调用）。"""
        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        # self._resolution_label.setText(f"分辨率: {width}x{height}")

    def update_frame(self, frame: np.ndarray):
        """更新帧（外部调用）。"""
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)

    def enter_pickup_mode(self):
        """进入坐标选择模式 — 投屏变灰，等待用户点击。"""
        self._view.set_pickup_mode(True)

    def exit_pickup_mode(self):
        """退出坐标选择模式 — 恢复正常显示。"""
        self._view.set_pickup_mode(False)
