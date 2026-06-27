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
    QGraphicsRectItem,
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

        # 选点模式边框 overlay（独立于 pixmap，避免每帧重绘）
        self._pickup_border_item = None

        # 设备分辨率（像素），用于坐标映射
        self._device_width: int = 0
        self._device_height: int = 0
        self._resolution_from_frame: bool = False  # True 表示正在使用帧尺寸作为回退

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
        """设置设备物理分辨率，用于坐标映射。

        Args:
            width: 设备宽度（像素）
            height: 设备高度（像素）
        """
        old_w, old_h = self._device_width, self._device_height
        self._device_width = width
        self._device_height = height
        self._resolution_from_frame = False

        # 检测分辨率变化（用于诊断）
        if old_w > 0 and old_h > 0 and (width != old_w or height != old_h):
            logger.info(
                "设备分辨率更新: %dx%d -> %dx%d %s",
                old_w, old_h, width, height,
                "(覆盖帧尺寸回退)" if getattr(self, '_resolution_from_frame', False) else ""
            )

        logger.debug("设置真实设备分辨率: %dx%d", width, height)

    def get_device_resolution(self) -> Tuple[int, int]:
        """返回当前使用的设备分辨率。"""
        return (self._device_width, self._device_height)

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

        # 保存旧值（在赋值前，用于变化检测）
        old_w, old_h = self._frame_width, self._frame_height

        self._frame_width = w
        self._frame_height = h

        # 检测帧尺寸变化（可能由设备旋转、scrcpy 重连等原因导致）
        if old_w > 0 and old_h > 0 and (w != old_w or h != old_h):
            logger.info(
                "帧尺寸变化: %dx%d -> %dx%d（可能设备旋转或重连）",
                old_w, old_h, w, h
            )
            # 帧尺寸变化时更新 pickup 边框位置
            self._update_pickup_border()
            # 注意：此处不自动更新设备分辨率，
            # 由外部的旋转检测逻辑负责同步更新

        # 不再使用帧尺寸作为回退值（会导致坐标不准确）
        # 分辨率必须由外部通过 set_device_resolution() 设置正确的物理分辨率
        # 如果 _device_width == 0，点击将被忽略（返回 (0,0)），这是预期行为

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
        self._update_pickup_border()
        # 仅在有标记或校准网格时才需要立即刷新
        if self._markers or self._calibration_mode:
            self._update_display()

    def _update_pickup_border(self):
        """更新选点模式蓝色边框 overlay。"""
        if self._pickup_mode and self._pixmap_item is not None:
            if self._pickup_border_item is None:
                self._pickup_border_item = QGraphicsRectItem()
                pen = QPen(QColor(88, 166, 255, 180), 4)  # #58a6ff 半透明蓝色
                self._pickup_border_item.setPen(pen)
                self._pickup_border_item.setBrush(QBrush(Qt.NoBrush))
                self._pickup_border_item.setZValue(1)
                self._scene.addItem(self._pickup_border_item)
            # 更新边框位置以匹配当前帧尺寸
            self._pickup_border_item.setRect(2, 2, self._frame_width - 4, self._frame_height - 4)
        else:
            if self._pickup_border_item is not None:
                self._scene.removeItem(self._pickup_border_item)
                self._pickup_border_item = None

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
            # 分辨率未就绪时，输出一次提示（避免刷屏）
            if not hasattr(self, '_resolution_warned'):
                self._resolution_warned = True
                logger.warning(
                    "⚠️ 点击被忽略: 设备分辨率尚未设置 "
                    "(start() 中的同步获取可能失败，请检查 ADB 连接)"
                )
            return (0, 0)

        scene_pos = self.mapToScene(view_x, view_y)
        px = scene_pos.x()
        py = scene_pos.y()
        pw = self._frame_width
        ph = self._frame_height

        if pw == 0 or ph == 0:
            return (0, 0)

        # === 坐标一致性验证 ===
        # 检查帧与设备的缩放比例是否一致（允许 ±10% 误差）
        if self._device_width > 0 and self._device_height > 0 and pw > 0 and ph > 0:
            scale_x = self._device_width / pw
            scale_y = self._device_height / ph
            # 如果两个轴的缩放比例差异超过 10%，说明可能有问题
            if abs(scale_x - scale_y) / max(scale_x, scale_y) > 0.1:
                logger.warning(
                    "⚠️ 坐标映射比例异常: X=%.2f, Y=%.2f (frame=%dx%d, device=%dx%d) "
                    "%s",
                    scale_x, scale_y, pw, ph,
                    self._device_width, self._device_height,
                    "(使用帧尺寸回退)" if getattr(self, '_resolution_from_frame', False) else ""
                )

        # 验证坐标是否在有效范围内
        if px < 0 or py < 0 or px > pw or py > ph:
            logger.debug(
                "坐标超出帧范围: scene=(%.1f, %.1f), frame=%dx%d",
                px, py, pw, ph
            )

        dev_x = int(px * self._device_width / pw)
        dev_y = int(py * self._device_height / ph)
        dev_x = max(0, min(dev_x, self._device_width - 1))
        dev_y = max(0, min(dev_y, self._device_height - 1))

        # 调试日志（限制输出频率）
        if not hasattr(self, '_click_count'):
            self._click_count = 0
        if self._click_count < 5:
            self._click_count += 1
            logger.debug(
                "坐标映射 #%d: view(%d,%d)->scene(%.1f,%.1f)->dev(%d,%d) "
                "[frame=%dx%d, device=%dx%d, scale=%.2fx%.2f, fallback=%s]",
                self._click_count,
                view_x, view_y, px, py, dev_x, dev_y,
                pw, ph, self._device_width, self._device_height,
                self._device_width / pw if pw > 0 else 0,
                self._device_height / ph if ph > 0 else 0,
                getattr(self, '_resolution_from_frame', False)
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
        # _scene.clear() 移除了 pickup border item，需要重建
        self._pickup_border_item = None
        self._update_pickup_border()

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
                if self._resolution_from_frame:
                    logger.debug("使用帧尺寸回退发送点击: device=(%d,%d)", dev_x, dev_y)
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
                logger.warning("点击被忽略: _device_width=0 (分辨率尚未设置)")
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
        # 更新右下角坐标悬浮标签（即使暂用帧尺寸回退也显示，便于排查）
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
            # 信号驱动帧更新：新帧到达立即通知 UI（零延迟），
            # 替代固定 8ms 轮询，显示唤醒延迟从 0~8ms 降到 ~0ms。
            # 信号队列不会堆积：_update_frame 用版本号跳过已渲染帧。
            self._screen_capture.frame_ready.connect(self._on_frame_ready, Qt.QueuedConnection)
            self._screen_capture.connection_lost.connect(self._on_connection_lost)
            self._screen_capture.connection_restored.connect(self._on_connection_restored)

    def _on_frame_captured(self, frame: np.ndarray):
        """接收到新帧。"""
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)

    def _on_frame_ready(self):
        """frame_ready 信号回调：新帧已就绪，立即拉取并渲染。

        信号驱动替代 8ms 轮询，将显示唤醒延迟从 0~8ms 降到 ~0ms。
        若多个信号在 UI 忙碌时排队，版本号检查确保只渲染最新帧。
        """
        self._update_frame()

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

        # ① 关键改进：同步获取设备分辨率（阻塞最多 3 秒）
        #    确保在帧更新开始前分辨率已就绪，避免使用不准确的帧尺寸回退值
        success = self._get_device_resolution_sync(timeout=3.0)
        if not success:
            logger.warning(
                "⚠️ 未能在启动时同步获取到精确分辨率，"
                "当前可能使用估算值（坐标可能略有偏差）"
            )

        # ② 启动旋转检测（检测初始方向）
        self._start_rotation_detection()

        # ③ 最后启动帧更新（此时分辨率已经就绪！）
        self._start_frame_update()

        # ④ 异步刷新（用于处理后续的旋转等变化）
        QTimer.singleShot(2000, self._ensure_resolution_ready)

    def stop(self):
        """停止投屏。"""
        self._connected = False
        self._status_label.setText("未连接")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")

        # 停止旋转检测
        self._stop_rotation_detection()

        # 停止帧更新
        self._stop_frame_update()

    def _get_device_resolution_sync(self, timeout: float = 3.0) -> bool:
        """同步获取设备分辨率（阻塞等待）。

        在启动帧更新之前调用，确保分辨率已就绪。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True 表示成功获取到真实分辨率，False 表示使用了估算值或失败
        """
        if not self._device_serial:
            logger.warning("同步获取分辨率跳过: _device_serial 为空")
            return False

        import concurrent.futures

        def _fetch():
            """执行 ADB 命令获取分辨率。"""
            resolution = None
            method = None

            # 方法 1: wm size（标准方法）
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO,
                )
                if result.returncode == 0:
                    match = re.search(r"(\d+)x(\d+)", result.stdout)
                    if match:
                        resolution = (int(match.group(1)), int(match.group(2)))
                        method = "sync/wm size"
                    else:
                        logger.warning(
                            "sync/wm size 返回格式异常: stdout=[%s]",
                            result.stdout.strip()[:100]
                        )
                else:
                    logger.warning(
                        "sync/wm size 命令失败 (returncode=%d): %s",
                        result.returncode,
                        result.stderr.strip()[:100]
                    )
            except Exception as e:
                logger.warning("sync/wm size 执行异常: %s", e)

            # 方法 2: dumpsys window（备选方法）
            if resolution is None:
                try:
                    result = subprocess.run(
                        ["adb", "-s", self._device_serial, "shell",
                         "dumpsys", "window", "displays"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        creationflags=_NO_WINDOW,
                        startupinfo=_STARTUPINFO,
                    )
                    if result.returncode == 0:
                        match = re.search(r"init=(\d+)x(\d+)", result.stdout)
                        if match:
                            resolution = (int(match.group(1)), int(match.group(2)))
                            method = "sync/dumpsys window"
                        else:
                            logger.debug(
                                "sync/dumpsys window 未找到分辨率: stdout=[%s]",
                                result.stdout.strip()[:200]
                            )
                    else:
                        logger.debug(
                            "sync/dumpsys window 失败 (returncode=%d)",
                            result.returncode
                        )
                except Exception as e:
                    logger.debug("sync/dumpsys window 异常: %s", e)

            return resolution, method

        # 使用线程池执行，支持超时控制
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch)
            try:
                resolution, method = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "⚠️ 同步获取分辨率超时 (%.1f秒)，将使用估算值",
                    timeout
                )
                resolution, method = None, None
            except Exception as e:
                logger.error("❌ 同步获取分辨率异常: %s", e)
                resolution, method = None, None

        # 应用结果
        if resolution:
            width, height = resolution
            self._set_resolution(width, height, method or "sync")
            return True
        else:
            # 使用智能估算作为最后手段
            estimated = self._estimate_resolution_from_frame()
            if estimated:
                width, height = estimated
                self._set_resolution(
                    width, height,
                    f"估算(帧{self._view._frame_width}x{self._view._frame_height})"
                )
                logger.warning(
                    "⚠️ 使用估算分辨率: %dx%d (ADB 同步获取失败)",
                    width, height
                )
                return False
            else:
                logger.error(
                    "❌ 无法获取也无法估算分辨率！将依赖后续异步重试。"
                )
                return False

    def _estimate_resolution_from_frame(self):
        """基于当前帧尺寸和常见设备分辨率列表估算真实分辨率。

        当 ADB 命令完全失败时的最后手段。
        准确率约 80%（基于宽高比匹配）。

        Returns:
            (width, height) 或 None（如果无法估算）
        """
        fw = getattr(self._view, '_frame_width', 0)
        fh = getattr(self._view, '_frame_height', 0)

        if fw <= 0 or fh <= 0:
            return None

        # 常见设备分辨率列表（按流行度排序）
        common_resolutions = [
            # 竖屏 (16:9, 19.5:9, 20:9 等)
            (720, 1280), (720, 1440), (720, 1520), (720, 1560),
            (720, 1600),
            (1080, 1920), (1080, 2340), (1080, 2400), (1080, 2460),
            (1080, 2520),
            (1440, 2560), (1440, 2960), (1440, 3200),
            # 横屏
            (1280, 720), (1920, 1080), (2560, 1440),
            # 特殊比例
            (768, 1024), (1024, 768),  # iPad
            (800, 1280), (1200, 1920),  # 其他
        ]

        frame_ratio = fw / fh if fh > 0 else 1

        # 寻找宽高比最接近的分辨率
        best_match = None
        min_diff = float('inf')
        for rw, rh in common_resolutions:
            res_ratio = rw / rh if rh > 0 else 1
            diff = abs(frame_ratio - res_ratio)
            if diff < min_diff:
                min_diff = diff
                best_match = (rw, rh)

        # 只有当宽高比差异小于 10% 时才接受
        if best_match and min_diff < 0.1:
            return best_match
        else:
            logger.debug(
                "无法找到匹配的分辨率 (帧=%dx%d, 最小差异=%.3f)",
                fw, fh, min_diff
            )
            return None

    def _ensure_resolution_ready(self):
        """确保设备分辨率已正确设置（超时保护）。

        每 2 秒检查一次，最多重试 10 次（20 秒）。
        如果仍然失败，降低重试频率为每 5 秒一次（避免资源浪费）。
        """
        if not self._connected:
            logger.debug("_ensure_resolution_ready(): 已断开连接，停止重试")
            return

        is_fallback = getattr(self._view, '_resolution_from_frame', False)

        # 初始化计数器（如果不存在）
        if not hasattr(self, '_resolution_retry_count'):
            self._resolution_retry_count = 0

        if is_fallback:
            self._resolution_retry_count += 1

            if self._resolution_retry_count <= 10:
                # 前 20 秒：快速重试（每 2 秒）
                logger.warning(
                    "⚠️ [%d/10] 分辨率仍为帧尺寸回退值，重试获取... (已等待约 %d 秒)",
                    self._resolution_retry_count,
                    self._resolution_retry_count * 2
                )
                self._get_device_resolution()
                QTimer.singleShot(2000, self._ensure_resolution_ready)
            elif self._resolution_retry_count == 11:
                # 第 11 次：切换到慢速重试模式
                logger.error(
                    "❌ 分辨率获取持续失败（已重试 20 秒），"
                    "切换到慢速重试模式（每 5 秒）。坐标将持续不准确。"
                )
                self._get_device_resolution()
                QTimer.singleShot(5000, self._ensure_resolution_ready)
            else:
                # 之后：慢速重试（每 5 秒）
                self._get_device_resolution()
                QTimer.singleShot(5000, self._ensure_resolution_ready)
        else:
            # 成功获取到真实分辨率
            if hasattr(self, '_resolution_retry_count') and self._resolution_retry_count > 0:
                logger.info(
                    "✅ 分辨率最终在第 %d 次重试后获取成功",
                    self._resolution_retry_count
                )
            # 清理状态
            self._resolution_retry_count = 0

    def _get_device_resolution(self):
        """获取设备分辨率。

        使用多种方法按优先级尝试：
        1. wm size（标准方法）
        2. dumpsys window（备选方法）
        """
        if not self._device_serial:
            logger.warning("_get_device_resolution() 跳过: _device_serial 为空")
            return

        def _detect():
            """在后台线程中执行 ADB 命令获取分辨率。"""
            resolution = None
            method = None

            # 方法 1: wm size（标准方法）
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO,
                )
                if result.returncode == 0:
                    match = re.search(r"(\d+)x(\d+)", result.stdout)
                    if match:
                        resolution = (int(match.group(1)), int(match.group(2)))
                        method = "wm size"
                    else:
                        logger.warning(
                            "wm size 返回格式异常: stdout=[%s] stderr=[%s]",
                            result.stdout.strip()[:100],
                            result.stderr.strip()[:100]
                        )
                else:
                    logger.warning(
                        "wm size 命令失败 (returncode=%d): %s",
                        result.returncode,
                        result.stderr.strip()[:100]
                    )
            except Exception as e:
                logger.warning("wm size 执行异常: %s", e)

            # 方法 2: dumpsys window（备选方法，如果 wm size 失败）
            if resolution is None:
                try:
                    result = subprocess.run(
                        ["adb", "-s", self._device_serial, "shell",
                         "dumpsys", "window", "displays"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        creationflags=_NO_WINDOW,
                        startupinfo=_STARTUPINFO,
                    )
                    if result.returncode == 0:
                        # 解析 "init=1080x1920  cur=1080x1920  app=1080x1920"
                        match = re.search(r"init=(\d+)x(\d+)", result.stdout)
                        if match:
                            resolution = (int(match.group(1)), int(match.group(2)))
                            method = "dumpsys window"
                        else:
                            logger.debug(
                                "dumpsys window 未找到分辨率: stdout=[%s]",
                                result.stdout.strip()[:200]
                            )
                    else:
                        logger.debug(
                            "dumpsys window 失败 (returncode=%d)",
                            result.returncode
                        )
                except Exception as e:
                    logger.debug("dumpsys window 异常: %s", e)

            # 应用结果
            if resolution:
                width, height = resolution
                QTimer.singleShot(
                    0,
                    lambda w=width, h=height, m=method: self._set_resolution(w, h, m)
                )
            else:
                logger.error(
                    "❌ 所有获取分辨率的方法都失败！将使用帧尺寸回退值（坐标可能不准确）"
                )

        threading.Thread(target=_detect, daemon=True).start()

    def _set_resolution(self, width: int, height: int, method: str = "unknown"):
        """设置分辨率。

        Args:
            width: 设备宽度
            height: 设备高度
            method: 获取方法名称（用于日志）
        """
        # 检查是否真的更新了（避免重复日志）
        old_w, old_h = self._device_width, self._device_height
        was_fallback = getattr(self._view, '_resolution_from_frame', False)

        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        self._resolution_label.setText(f"分辨率: {width}x{height}")

        # 根据上下文选择日志级别和信息
        if was_fallback:
            logger.info(
                "✅ 分辨率已修正: %dx%d -> %dx%d (来源: %s, 替换了帧尺寸回退)",
                old_w, old_h, width, height, method
            )
        else:
            logger.info("设备分辨率: %dx%d (来源: %s)", width, height, method)

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

            # 交换宽高（仅当方向改变时：竖屏↔横屏）
            if (old in (0, 2)) != (new_rotation in (0, 2)):
                old_res = (self._device_width, self._device_height)
                self._device_width, self._device_height = (self._device_height, self._device_width)

                logger.info(
                    "旋转交换分辨率: %dx%d -> %dx%d (rotation %d->%d)",
                    old_res[0], old_res[1],
                    self._device_width, self._device_height,
                    old, new_rotation
                )

                self._view.set_device_resolution(self._device_width, self._device_height)
                self._resolution_label.setText(f"分辨率: {self._device_width}x{self._device_height}")

                # 旋转后延迟刷新分辨率（防止使用过期值或重复交换）
                # 延迟 500ms 执行，给 scrcpy 时间输出新方向的帧，给 wm size 时间更新
                QTimer.singleShot(500, self._get_device_resolution)

            # 自动适配
            QTimer.singleShot(100, self._on_fit)

    def _start_frame_update(self):
        """启动帧更新。

        主要由 frame_ready 信号驱动（零延迟通知）。
        保留低频定时器作为 fallback（100ms），防止信号丢失时画面停滞。
        原 8ms 轮询已被信号驱动替代。
        """
        if self._frame_timer:
            return

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._update_frame)
        self._frame_timer.start(100)  # 100ms fallback（原 8ms 高频轮询）

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
