"""嵌入式高清投屏组件 - 可嵌入到其他窗口中的投屏视图。

基于 MirrorGraphicsView，提供：
- 高清渲染、缩放、平移
- 坐标映射和点击事件
- 坐标标记功能（用于截图选择）
- 设备旋转检测
"""

import logging
import re
import subprocess
import sys
import threading
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QPointF, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QCursor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Windows 下隐藏子进程控制台窗口
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    _STARTUPINFO = None


class EmbeddedMirrorView(QGraphicsView):
    """嵌入式高清镜像视图，支持缩放、平移、点击映射、坐标标记。"""

    point_clicked = pyqtSignal(int, int)  # 设备坐标
    mouse_moved = pyqtSignal(int, int)  # 设备坐标（悬停）
    pickup_completed = pyqtSignal(int, int)  # 选点模式完成（设备坐标）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # 画面 item
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None

        # 设备分辨率（像素），用于坐标映射
        self._device_width: int = 0
        self._device_height: int = 0

        # 当前画面原始尺寸
        self._frame_width: int = 0
        self._frame_height: int = 0

        # 缩放控制
        self._zoom_factor: float = 1.0
        self._min_zoom: float = 0.1
        self._max_zoom: float = 10.0

        # 拖拽平移
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()

        # 坐标标记
        self._markers: List[Tuple[int, int]] = []
        self._active_marker: int = -1
        self._calibration_mode: bool = False

        # 坐标选择模式
        self._pickup_mode: bool = False

        # 渲染优化：视频帧不需要抗锯齿和平滑变换，关闭以提升性能
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor("#1a1a2e")))

        # 鼠标追踪（用于悬停坐标显示）
        self.setMouseTracking(True)

        # 十字光标
        self._cross_cursor = QCursor(Qt.CrossCursor)
        self.setCursor(self._cross_cursor)

        # 右下角坐标悬浮标签（QLabel 作为 viewport 子控件）
        self._coord_overlay = QLabel("(-, -)", self.viewport())
        self._coord_overlay.setStyleSheet(
            "QLabel { background-color: rgba(0, 0, 0, 180); color: #58a6ff; "
            "font-family: Consolas; font-size: 12px; "
            "padding: 4px 8px; border-radius: 4px; }"
        )
        self._coord_overlay.setAlignment(Qt.AlignCenter)
        self._coord_overlay.adjustSize()
        self._coord_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._coord_overlay.hide()
        self._last_coord: Tuple[int, int] = (0, 0)

    # -- 公开接口 --

    def set_device_resolution(self, width: int, height: int):
        """设置设备物理分辨率，用于坐标映射。"""
        self._device_width = width
        self._device_height = height

    def update_frame(self, frame: np.ndarray):
        """更新显示帧（RGB numpy array）。

        PyAV 解码输出 rgb24，直接使用 Format_RGB888 构建 QImage，
        无需 rgbSwapped() 额外拷贝。
        """
        if frame is None or frame.size == 0:
            return
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        # 确保数组内存连续，QImage 需要连续内存
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)
        # 保持 numpy 数组引用，防止 QImage 使用期间被 GC 回收
        self._current_frame_ref = frame
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)

        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._pixmap_item.setZValue(0)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._frame_width = w
        self._frame_height = h

        # 检测帧尺寸变化（可能由设备旋转、scrcpy 重连等原因导致）
        old_w, old_h = self._frame_width, self._frame_height
        if old_w > 0 and old_h > 0 and (w != old_w or h != old_h):
            logger.info(
                "帧尺寸变化: %dx%d -> %dx%d（可能设备旋转或重连）",
                old_w, old_h, w, h
            )
            # 注意：此处不自动更新设备分辨率，
            # 由外部的旋转检测逻辑负责同步更新

        # 不再自动初始化设备分辨率，等待外部通过 set_device_resolution() 设置正确的物理分辨率
        # 这样可以避免因 scrcpy max_size 缩放导致的帧尺寸与实际分辨率不匹配问题

    def fit_to_view(self):
        """自适应窗口大小。"""
        if self._pixmap_item is None:
            return
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._zoom_factor = self.transform().m11()

    def reset_view(self):
        """重置为 1:1 显示。"""
        self.resetTransform()
        self._zoom_factor = 1.0
        if self._pixmap_item:
            self.centerOn(self._pixmap_item)

    def zoom_to(self, factor: float):
        """缩放到指定倍率。"""
        factor = max(self._min_zoom, min(factor, self._max_zoom))
        self.resetTransform()
        self.scale(factor, factor)
        self._zoom_factor = factor

    def get_zoom(self) -> float:
        return self._zoom_factor

    # -- 坐标标记 --

    def add_marker(self, x: int, y: int):
        """添加坐标标记。"""
        self._markers.append((x, y))
        self._active_marker = len(self._markers) - 1
        self._update_display()

    def clear_markers(self):
        """清除所有标记。"""
        self._markers.clear()
        self._active_marker = -1
        self._update_display()

    def get_markers(self) -> List[Tuple[int, int]]:
        """获取所有标记。"""
        return list(self._markers)

    def get_active_marker(self) -> Optional[Tuple[int, int]]:
        """获取当前活动标记。"""
        if 0 <= self._active_marker < len(self._markers):
            return self._markers[self._active_marker]
        return None

    def set_calibration_mode(self, enabled: bool):
        """设置校准模式。"""
        self._calibration_mode = enabled
        self._update_display()

    def set_pickup_mode(self, enabled: bool):
        """设置坐标选择模式。"""
        self._pickup_mode = enabled
        self._update_display()

    # -- 坐标悬浮标签 --

    def _update_coord_overlay(self, x: int, y: int):
        """更新右下角坐标悬浮标签。"""
        self._coord_overlay.setText(f"({x}, {y})")
        self._coord_overlay.adjustSize()
        self._last_coord = (x, y)
        # 定位到 viewport 右下角
        margin = 10
        vp = self.viewport()
        x_pos = vp.width() - self._coord_overlay.width() - margin
        y_pos = vp.height() - self._coord_overlay.height() - margin
        self._coord_overlay.move(x_pos, y_pos)
        self._coord_overlay.show()

    # -- 坐标映射 --

    def _view_to_device(self, view_x: int, view_y: int) -> Tuple[int, int]:
        """视图坐标 -> 设备坐标。"""
        if self._pixmap_item is None or self._device_width == 0:
            return (0, 0)
        scene_pos = self.mapToScene(view_x, view_y)
        px = scene_pos.x()
        py = scene_pos.y()
        pw = self._frame_width
        ph = self._frame_height
        if pw == 0 or ph == 0:
            return (0, 0)

        # 验证坐标是否在有效范围内（防止缩放比例异常导致的坐标越界）
        if px < 0 or py < 0 or px > pw or py > ph:
            logger.debug(
                "坐标超出帧范围: scene=(%.1f, %.1f), frame=%dx%d",
                px, py, pw, ph
            )

        dev_x = int(px * self._device_width / pw)
        dev_y = int(py * self._device_height / ph)
        dev_x = max(0, min(dev_x, self._device_width - 1))
        dev_y = max(0, min(dev_y, self._device_height - 1))

        # 调试日志：输出坐标映射详情（仅在首几次点击时输出，避免日志过多）
        if not hasattr(self, '_click_count'):
            self._click_count = 0
        if self._click_count < 5:
            self._click_count += 1
            logger.debug(
                "坐标映射: view=(%d,%d) -> scene=(%.1f,%.1f) -> device=(%d,%d) "
                "[frame=%dx%d, device=%dx%d]",
                view_x, view_y, px, py, dev_x, dev_y,
                pw, ph, self._device_width, self._device_height
            )

        return (dev_x, dev_y)

    def _device_to_view(self, dev_x: int, dev_y: int) -> Tuple[int, int]:
        """设备坐标 -> 视图坐标。"""
        if self._pixmap_item is None or self._device_width == 0:
            return (0, 0)
        pw = self._frame_width
        ph = self._frame_height
        if pw == 0 or ph == 0:
            return (0, 0)
        px = dev_x * pw / self._device_width
        py = dev_y * ph / self._device_height
        view_pos = self.mapFromScene(px, py)
        return (view_pos.x(), view_pos.y())

    # -- 显示更新 --

    def _update_display(self):
        """更新显示（包括标记）。"""
        if self._pixmap_item is None:
            return

        # 获取当前 pixmap
        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            return

        # 创建绘制副本
        draw_pixmap = QPixmap(pixmap)
        painter = QPainter(draw_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制校准网格
        if self._calibration_mode:
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            grid_step = 100
            for x in range(0, draw_pixmap.width(), grid_step):
                painter.drawLine(x, 0, x, draw_pixmap.height())
            for y in range(0, draw_pixmap.height(), grid_step):
                painter.drawLine(0, y, draw_pixmap.width(), y)

        # 绘制标记
        for i, (mx, my) in enumerate(self._markers):
            is_active = i == self._active_marker
            pen_width = 3 if is_active else 2
            cross_size = 12 if is_active else 8

            # 阴影
            shadow_pen = QPen(QColor(0, 0, 0, 160), pen_width + 1)
            painter.setPen(shadow_pen)
            painter.drawLine(mx - cross_size, my, mx + cross_size, my)
            painter.drawLine(mx, my - cross_size, mx, my + cross_size)

            # 十字标记
            color = QColor("#ff0000") if not is_active else QColor("#00ffff")
            pen = QPen(color, pen_width)
            painter.setPen(pen)
            painter.drawLine(mx - cross_size, my, mx + cross_size, my)
            painter.drawLine(mx, my - cross_size, mx, my + cross_size)

            # 活动标记的圆圈
            if is_active:
                painter.setPen(QPen(QColor("#00ffff"), 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(mx - 15, my - 15, 30, 30)

            # 坐标文本
            dev_x, dev_y = self._view_to_device(mx, my)
            text = f"({dev_x}, {dev_y})"
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            font = QFont("Consolas", 9)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text) + 8
            th = fm.height() + 4
            text_x = mx + 8
            if text_x + tw > draw_pixmap.width():
                text_x = mx - tw - 8
            text_y = my - th
            if text_y < 0:
                text_y = my + 8
            text_rect = QRect(text_x, text_y, tw, th)
            painter.fillRect(text_rect, QColor(0, 0, 0, 160))
            painter.drawText(text_rect, Qt.AlignCenter, text)

        painter.end()

        # 更新场景
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(draw_pixmap)
        self._pixmap_item.setZValue(0)

    # -- 鼠标事件 --

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            dev_x, dev_y = self._view_to_device(event.pos().x(), event.pos().y())
            if self._device_width > 0:
                if self._pickup_mode:
                    # 选点模式：发射 pickup_completed，不做标记
                    self.pickup_completed.emit(dev_x, dev_y)
                elif self._calibration_mode:
                    # 校准模式：添加标记 + 发射 point_clicked
                    scene_pos = self.mapToScene(event.pos())
                    self.add_marker(int(scene_pos.x()), int(scene_pos.y()))
                    self.point_clicked.emit(dev_x, dev_y)
                else:
                    # 普通模式：仅发射 point_clicked，不添加标记
                    self.point_clicked.emit(dev_x, dev_y)
            else:
                logger.debug("点击被忽略: _device_width=0 (分辨率尚未设置)")
            event.accept()
            return
        if event.button() == Qt.RightButton:
            # 右键删除最后一个标记
            if self._markers:
                self._markers.pop()
                self._active_marker = len(self._markers) - 1
                self._update_display()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 悬停坐标
        dev_x, dev_y = self._view_to_device(event.pos().x(), event.pos().y())
        if self._device_width > 0:
            self.mouse_moved.emit(dev_x, dev_y)
            # 更新右下角坐标悬浮标签
            self._update_coord_overlay(dev_x, dev_y)
        # 拖拽平移
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(self._cross_cursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            factor = 1.15
        else:
            factor = 1.0 / 1.15
        new_zoom = self._zoom_factor * factor
        new_zoom = max(self._min_zoom, min(new_zoom, self._max_zoom))
        self.scale(factor, factor)
        self._zoom_factor = new_zoom
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 如果坐标标签可见，重新定位到右下角
        if self._coord_overlay.isVisible():
            self._update_coord_overlay(*self._last_coord)

    def leaveEvent(self, event):
        """鼠标离开视图时隐藏坐标标签。"""
        self._coord_overlay.hide()
        super().leaveEvent(event)


class EmbeddedMirrorWidget(QWidget):
    """嵌入式高清投屏组件，可嵌入到其他窗口中。"""

    # 信号
    point_selected = pyqtSignal(int, int)  # 坐标选择信号
    mouse_moved = pyqtSignal(int, int)  # 鼠标移动信号
    connection_status_changed = pyqtSignal(bool)  # 连接状态变化

    def __init__(self, screen_capture=None, adb_core=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._adb_core = adb_core
        self._device_serial: str = ""
        self._connected: bool = False

        # 设备信息
        self._device_width: int = 0
        self._device_height: int = 0
        self._device_rotation: int = 0

        # 旋转检测定时器
        self._rotation_timer: Optional[QTimer] = None
        self._rotation_thread: Optional[threading.Thread] = None

        # 帧更新定时器
        self._frame_timer: Optional[QTimer] = None

        # 上次渲染的帧版本号，用于跳过重复帧
        self._last_rendered_version: int = 0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        btn_style = (
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; "
            "padding: 4px 8px; min-width: 50px; }"
            "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
            "QPushButton:pressed { background-color: #161b22; }"
        )

        self._btn_fit = QPushButton("适配")
        self._btn_fit.setStyleSheet(btn_style)
        self._btn_fit.clicked.connect(self._on_fit)
        toolbar.addWidget(self._btn_fit)

        self._btn_1to1 = QPushButton("1:1")
        self._btn_1to1.setStyleSheet(btn_style)
        self._btn_1to1.clicked.connect(self._on_1to1)
        toolbar.addWidget(self._btn_1to1)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setStyleSheet(btn_style)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        # 缩放百分比
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._zoom_label.setMinimumWidth(40)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(self._zoom_label)

        toolbar.addStretch()

        # 坐标显示
        self._coord_label = QLabel("坐标: (-, -)")
        self._coord_label.setStyleSheet("color: #58a6ff; font-size: 12px; font-family: Consolas;")
        self._coord_label.setMinimumWidth(100)
        self._coord_label.setMaximumWidth(160)
        toolbar.addWidget(self._coord_label)

        # 状态指示
        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._status_label.setMinimumWidth(60)
        toolbar.addWidget(self._status_label)

        layout.addLayout(toolbar)

        # 投屏视图
        self._view = EmbeddedMirrorView()
        self._view.point_clicked.connect(self._on_point_clicked)
        self._view.mouse_moved.connect(self._on_mouse_moved)
        layout.addWidget(self._view, stretch=1)

        # 底部信息栏
        info_bar = QHBoxLayout()
        self._resolution_label = QLabel("分辨率: -")
        self._resolution_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        info_bar.addWidget(self._resolution_label)

        info_bar.addStretch()

        self._markers_label = QLabel("标记: 0")
        self._markers_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        info_bar.addWidget(self._markers_label)

        layout.addLayout(info_bar)

    def _connect_signals(self):
        """连接信号。"""
        if self._screen_capture:
            # 不连接 frame_captured 信号，改用定时器轮询避免事件队列堆积
            self._screen_capture.connection_lost.connect(self._on_connection_lost)
            self._screen_capture.connection_restored.connect(self._on_connection_restored)

    def _on_frame_captured(self, frame: np.ndarray):
        """接收到新帧。"""
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)

    def _on_connection_lost(self):
        """连接断开。"""
        self._connected = False
        self._status_label.setText("断开")
        self._status_label.setStyleSheet("color: #f85149; font-size: 12px;")
        self.connection_status_changed.emit(False)

    def _on_connection_restored(self):
        """连接恢复。"""
        self._connected = True
        self._status_label.setText("已连接")
        self._status_label.setStyleSheet("color: #3fb950; font-size: 12px;")
        self.connection_status_changed.emit(True)

    def _on_point_clicked(self, dev_x: int, dev_y: int):
        """坐标点击。"""
        self._coord_label.setText(f"坐标: ({dev_x}, {dev_y})")
        self.point_selected.emit(dev_x, dev_y)
        self._update_markers_label()

    def _on_mouse_moved(self, dev_x: int, dev_y: int):
        """鼠标移动。"""
        self._coord_label.setText(f"坐标: ({dev_x}, {dev_y})")
        self.mouse_moved.emit(dev_x, dev_y)

    def _update_markers_label(self):
        """更新标记数量显示。"""
        markers = self._view.get_markers()
        self._markers_label.setText(f"标记: {len(markers)}")

    # -- 工具栏操作 --

    def _on_fit(self):
        """适配窗口。"""
        self._view.fit_to_view()
        self._sync_zoom_label()

    def _on_1to1(self):
        """1:1 显示。"""
        self._view.zoom_to(1.0)
        self._sync_zoom_label()

    def _on_reset(self):
        """重置视图。"""
        self._view.reset_view()
        self._sync_zoom_label()

    def _sync_zoom_label(self):
        """同步缩放标签。"""
        zoom = self._view.get_zoom()
        self._zoom_label.setText(f"{int(zoom * 100)}%")

    # -- 公开接口 --

    def start(self, serial: str):
        """启动投屏。"""
        self._device_serial = serial
        self._connected = True
        self._status_label.setText("已连接")
        self._status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

        # 获取设备分辨率
        self._get_device_resolution()

        # 启动旋转检测
        self._start_rotation_detection()

        # 启动帧更新
        self._start_frame_update()

    def stop(self):
        """停止投屏。"""
        self._connected = False
        self._status_label.setText("未连接")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")

        # 停止旋转检测
        self._stop_rotation_detection()

        # 停止帧更新
        self._stop_frame_update()

    def _get_device_resolution(self):
        """获取设备分辨率。"""
        if not self._device_serial:
            return

        def _detect():
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO,
                )
                match = re.search(r"(\d+)x(\d+)", result.stdout)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                    QTimer.singleShot(0, lambda: self._set_resolution(width, height))
            except Exception as e:
                logger.debug("获取分辨率失败: %s", e)

        threading.Thread(target=_detect, daemon=True).start()

    def _set_resolution(self, width: int, height: int):
        """设置分辨率。"""
        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        self._resolution_label.setText(f"分辨率: {width}x{height}")
        logger.info("设备分辨率: %dx%d", width, height)

    def _start_rotation_detection(self):
        """启动旋转检测。"""
        if self._rotation_timer:
            return

        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._check_rotation)
        self._rotation_timer.start(2000)  # 每2秒检测一次

    def _stop_rotation_detection(self):
        """停止旋转检测。"""
        if self._rotation_timer:
            self._rotation_timer.stop()
            self._rotation_timer = None

    def _check_rotation(self):
        """检测设备旋转状态。"""
        if not self._connected or not self._device_serial:
            return

        if self._rotation_thread and self._rotation_thread.is_alive():
            return

        def _detect():
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "dumpsys", "input"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO,
                )
                match = re.search(r"SurfaceOrientation:\s*(\d)", result.stdout)
                if match:
                    new_rotation = int(match.group(1))
                    QTimer.singleShot(0, lambda: self._on_rotation_detected(new_rotation))
            except Exception as e:
                logger.debug("检测旋转失败: %s", e)

        self._rotation_thread = threading.Thread(target=_detect, daemon=True)
        self._rotation_thread.start()

    def _on_rotation_detected(self, new_rotation: int):
        """旋转检测回调。"""
        if new_rotation != self._device_rotation:
            old = self._device_rotation
            self._device_rotation = new_rotation
            logger.info("设备旋转: %d -> %d", old, new_rotation)

            # 交换宽高
            if (old in (0, 2)) != (new_rotation in (0, 2)):
                self._device_width, self._device_height = (self._device_height, self._device_width)
                self._view.set_device_resolution(self._device_width, self._device_height)
                self._resolution_label.setText(f"分辨率: {self._device_width}x{self._device_height}")

            # 自动适配
            QTimer.singleShot(100, self._on_fit)

    def _start_frame_update(self):
        """启动帧更新定时器。"""
        if self._frame_timer:
            return

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._update_frame)
        self._frame_timer.start(8)  # ~120fps

    def _stop_frame_update(self):
        """停止帧更新定时器。"""
        if self._frame_timer:
            self._frame_timer.stop()
            self._frame_timer = None

    def _update_frame(self):
        """更新帧。使用版本号机制跳过重复帧。"""
        if not self._connected or not self._screen_capture:
            return

        result = self._screen_capture.get_current_frame_if_new(self._last_rendered_version)
        if result is not None:
            frame, version = result
            self._view.update_frame(frame)
            self._last_rendered_version = version

    # -- 坐标标记接口 --

    def clear_markers(self):
        """清除所有标记。"""
        self._view.clear_markers()
        self._update_markers_label()

    def get_selected_point(self) -> Optional[Tuple[int, int]]:
        """获取选中的坐标点。"""
        return self._view.get_active_marker()

    def set_calibration_mode(self, enabled: bool):
        """设置校准模式。"""
        self._view.set_calibration_mode(enabled)
