"""高清投屏窗口 - 独立镜像窗口，支持高清渲染、坐标映射、旋转跟随。

点击主界面按钮后打开此窗口，提供：
- QGraphicsView 高清自适应显示
- 鼠标滚轮缩放、拖拽平移
- 点击直接映射设备坐标（发送 tap 事件）
- 自动检测设备旋转方向并跟随
- 工具栏：适配窗口、1:1、重置、旋转锁定
"""

import logging
import subprocess
import re
import sys
import time
import threading
from typing import Optional, Tuple

import numpy as np
import cv2
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QPointF, QRectF, QSizeF
)
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QBrush,
    QFont, QCursor, QKeySequence
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QToolBar, QAction, QSizePolicy,
    QStatusBar, QShortcut, QSpinBox, QComboBox, QCheckBox
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


# ---------------------------------------------------------------------------
#  QGraphicsView 子类：高清渲染 + 坐标映射
# ---------------------------------------------------------------------------

class MirrorGraphicsView(QGraphicsView):
    """高清镜像视图，支持缩放、平移、点击映射。"""

    point_clicked = pyqtSignal(int, int)       # 设备坐标
    mouse_moved = pyqtSignal(int, int)         # 设备坐标（悬停）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # 画面 item
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None

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
        """更新显示帧（RGB numpy array）。"""
        if frame is None or frame.size == 0:
            return
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(
            frame.data, w, h, bytes_per_line, QImage.Format_RGB888
        )
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

        # 不再使用帧尺寸作为回退值（会导致坐标不准确）
        # 分辨率必须由外部通过 set_device_resolution() 设置正确的物理分辨率

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

    # -- 鼠标事件 --

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            dev_x, dev_y = self._view_to_device(
                event.pos().x(), event.pos().y()
            )
            if self._device_width > 0:
                if self._resolution_from_frame:
                    logger.debug("使用帧尺寸回退发送点击: device=(%d,%d)", dev_x, dev_y)
                self.point_clicked.emit(dev_x, dev_y)
            else:
                logger.warning("点击被忽略: _device_width=0 (分辨率尚未设置)")
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 悬停坐标
        dev_x, dev_y = self._view_to_device(
            event.pos().x(), event.pos().y()
        )
        if self._device_width > 0:
            self.mouse_moved.emit(dev_x, dev_y)
        # 更新右下角坐标悬浮标签（即使暂用帧尺寸回退也显示，便于排查）
        self._update_coord_overlay(dev_x, dev_y)
        # 拖拽平移
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
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
        # 窗口大小变化时不强制重绘，保持用户缩放
        # 如果坐标标签可见，重新定位到右下角
        if self._coord_overlay.isVisible():
            self._update_coord_overlay(*self._last_coord)

    def leaveEvent(self, event):
        """鼠标离开视图时隐藏坐标标签。"""
        self._coord_overlay.hide()
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
#  高清投屏主窗口
# ---------------------------------------------------------------------------

class MirrorWindow(QWidget):
    """独立高清投屏窗口。

    通过 screen_capture 接收帧流，提供高清渲染、坐标点击、旋转跟随。
    """

    # 点击坐标信号（供外部如 step_executor 使用）
    device_point_clicked = pyqtSignal(int, int)
    # 内部信号：后台线程更新 UI
    _tap_finished = pyqtSignal(bool, int, int, str)   # success, x, y, method
    _rotation_detected = pyqtSignal(int)          # rotation value
    _resolution_failed = pyqtSignal()             # 分辨率获取失败

    # tap 最小间隔（秒），防止快速连击堆积
    _TAP_MIN_INTERVAL = 0.05

    def __init__(self, screen_capture, adb_core=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._adb_core = adb_core
        self._device_serial: str = ""

        # 设备信息
        self._device_width: int = 0
        self._device_height: int = 0
        self._device_rotation: int = 0   # 0/1/2/3
        self._rotation_locked: bool = False

        # 旋转检测定时器
        self._rotation_timer: Optional[QTimer] = None

        # 帧轮询定时器（替代信号槽，避免事件队列堆积）
        self._frame_timer: Optional[QTimer] = None
        self._frame_interval = 16  # ~60fps，匹配 scrcpy server 输出帧率

        # 上次渲染的帧版本号，用于跳过重复帧
        self._last_rendered_version: int = 0

        # 窗口是否已关闭
        self._closed: bool = False

        # tap 速率限制
        self._last_tap_time: float = 0.0
        self._tap_lock = threading.Lock()

        # 后台旋转检测线程引用（避免重复启动）
        self._rotation_thread: Optional[threading.Thread] = None

        # sendevent 触摸注入相关
        self._touch_device_path: Optional[str] = None  # /dev/input/eventX
        self._touch_device_detected: bool = False
        self._use_sendevent: bool = True  # 优先使用 sendevent
        self._touch_max_x: int = 0  # 触摸设备最大 X 坐标
        self._touch_max_y: int = 0  # 触摸设备最大 Y 坐标
        self._tracking_id: int = 0  # 触摸跟踪 ID

        self._init_window()
        self._init_ui()
        self._init_shortcuts()

        # 连接内部信号
        self._tap_finished.connect(self._on_tap_finished)
        self._rotation_detected.connect(self._on_rotation_detected_from_thread)
        self._resolution_failed.connect(self._on_resolution_failed)

    # -----------------------------------------------------------------------
    #  窗口初始化
    # -----------------------------------------------------------------------

    def _init_window(self):
        self.setWindowTitle("高清投屏")
        self.setMinimumSize(900, 500)
        # 默认大小：屏幕的 70%
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            w = int(geo.width() * 0.7)
            h = int(geo.height() * 0.7)
            self.resize(w, h)
            # 居中
            self.move(
                geo.x() + (geo.width() - w) // 2,
                geo.y() + (geo.height() - h) // 2
            )
        else:
            self.resize(1024, 768)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- 工具栏 --
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(6)

        btn_style = (
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; "
            "padding: 4px 12px; min-width: 60px; }"
            "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
            "QPushButton:pressed { background-color: #161b22; }"
        )

        self._btn_fit = QPushButton("适配窗口")
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

        # 缩放百分比显示
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._zoom_label.setMinimumWidth(40)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(self._zoom_label)

        toolbar.addStretch()

        # 旋转锁定 + 方向选择
        self._chk_rotation_lock = QCheckBox("锁定旋转")
        self._chk_rotation_lock.setStyleSheet(
            "QCheckBox { color: #8b949e; font-size: 12px; }"
        )
        self._chk_rotation_lock.toggled.connect(self._on_rotation_lock_toggled)
        toolbar.addWidget(self._chk_rotation_lock)

        self._combo_rotation = QComboBox()
        self._combo_rotation.addItems(["跟随设备", "竖屏(0°)", "横屏(90°)", "竖屏(180°)", "横屏(270°)"])
        self._combo_rotation.setMinimumWidth(80)
        self._combo_rotation.setMaximumWidth(110)
        self._combo_rotation.setStyleSheet(
            "QComboBox { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; padding: 2px 6px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #21262d; "
            "color: #c9d1d9; selection-background-color: #30363d; }"
        )
        self._combo_rotation.setEnabled(False)
        self._combo_rotation.currentIndexChanged.connect(self._on_rotation_target_changed)
        toolbar.addWidget(self._combo_rotation)

        # 坐标显示
        self._coord_label = QLabel("坐标: (-, -)")
        self._coord_label.setStyleSheet(
            "color: #58a6ff; font-size: 12px; font-family: Consolas;"
        )
        self._coord_label.setMinimumWidth(100)
        self._coord_label.setMaximumWidth(160)
        toolbar.addWidget(self._coord_label)

        # 缩放百分比
        self._zoom_spin = QSpinBox()
        self._zoom_spin.setRange(10, 1000)
        self._zoom_spin.setValue(100)
        self._zoom_spin.setSuffix("%")
        self._zoom_spin.setFixedWidth(70)
        self._zoom_spin.setStyleSheet(
            "QSpinBox { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; padding: 2px; }"
        )
        self._zoom_spin.valueChanged.connect(self._on_zoom_spin_changed)
        toolbar.addWidget(self._zoom_spin)

        main_layout.addLayout(toolbar)

        # -- 图形视图 --
        self._view = MirrorGraphicsView()
        self._view.point_clicked.connect(self._on_point_clicked)
        self._view.mouse_moved.connect(self._on_mouse_moved)
        main_layout.addWidget(self._view, stretch=1)

        # -- 状态栏 --
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(8, 2, 8, 2)

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        status_bar.addWidget(self._status_label)

        status_bar.addStretch()

        self._resolution_label = QLabel("分辨率: --")
        self._resolution_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        status_bar.addWidget(self._resolution_label)

        self._rotation_label = QLabel("方向: --")
        self._rotation_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        status_bar.addWidget(self._rotation_label)

        main_layout.addLayout(status_bar)

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+0"), self, self._on_fit)
        QShortcut(QKeySequence("Ctrl+1"), self, self._on_1to1)
        QShortcut(QKeySequence("Ctrl+R"), self, self._on_reset)

    # -----------------------------------------------------------------------
    #  公开接口
    # -----------------------------------------------------------------------

    def start(self, device_serial: str):
        """启动投屏显示。"""
        self._device_serial = device_serial
        self._closed = False
        self.setWindowTitle(f"高清投屏 - {device_serial}")

        # ① 关键改进：同步获取设备分辨率（阻塞最多 3 秒）
        #    确保在帧更新开始前分辨率已就绪
        success = self._fetch_device_resolution_sync(timeout=3.0)
        if not success:
            logger.warning(
                "⚠️ 未能在启动时同步获取到精确分辨率，"
                "当前可能使用估算值（坐标可能略有偏差）"
            )

        if self._device_width == 0 or self._device_height == 0:
            logger.error("设备分辨率获取失败，点击功能将不可用")
            self._resolution_failed.emit()

        # 检测触摸输入设备（用于 sendevent）
        self._detect_touch_device()

        # 立即检测当前旋转状态（不等定时器）
        self._detect_rotation_immediate()

        # 设置视图设备分辨率
        if self._device_width > 0 and self._device_height > 0:
            self._view.set_device_resolution(
                self._device_width, self._device_height
            )

        # 信号驱动帧更新：新帧到达立即通知 UI（零延迟），
        # 替代固定 16ms 轮询，显示唤醒延迟从 0~16ms 降到 ~0ms。
        # 版本号机制确保信号队列不堆积。
        if self._screen_capture:
            self._screen_capture.frame_ready.connect(
                self._on_frame_ready, Qt.QueuedConnection
            )

        # 启动帧轮询定时器作为 fallback（100ms，防止信号丢失）
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(100)  # fallback（原 16ms 高频轮询）
        self._frame_timer.timeout.connect(self._poll_latest_frame)
        self._frame_timer.start()

        # 启动旋转检测定时器
        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(2000)  # 每2秒检测
        self._rotation_timer.timeout.connect(self._check_rotation)
        self._rotation_timer.start()

        self._status_label.setText("已连接")
        self._status_label.setStyleSheet("color: #3fb950; font-size: 11px;")
        self._update_resolution_label()
        self._update_rotation_label()

        # 首次自适应
        QTimer.singleShot(500, self._on_fit)

    def stop(self):
        """停止投屏显示。"""
        self._closed = True
        # 停止帧轮询定时器
        if self._frame_timer:
            self._frame_timer.stop()
            self._frame_timer = None
        # 断开 frame_ready 信号
        if self._screen_capture:
            try:
                self._screen_capture.frame_ready.disconnect(self._on_frame_ready)
            except (TypeError, RuntimeError):
                pass  # 信号未连接或已断开
        if self._rotation_timer:
            self._rotation_timer.stop()

    # -----------------------------------------------------------------------
    #  帧处理
    # -----------------------------------------------------------------------

    def _poll_latest_frame(self):
        """定时轮询最新帧（fallback，防止信号丢失）。

        使用版本号机制跳过重复帧，避免不必要的 QImage/Pixmap 构建。
        """
        if self._closed:
            return
        result = self._screen_capture.get_current_frame_if_new(
            self._last_rendered_version
        )
        if result is not None:
            frame, version = result
            self._view.update_frame(frame)
            self._last_rendered_version = version

    def _on_frame_ready(self):
        """frame_ready 信号回调：新帧已就绪，立即拉取并渲染。

        信号驱动替代 16ms 轮询，将显示唤醒延迟从 0~16ms 降到 ~0ms。
        若多个信号在 UI 忙碌时排队，版本号检查确保只渲染最新帧。
        """
        if self._closed:
            return
        self._poll_latest_frame()

    # -----------------------------------------------------------------------
    #  设备信息
    # -----------------------------------------------------------------------

    def _fetch_device_resolution(self):
        """通过 adb 获取设备分辨率。

        使用多种方法按优先级尝试：
        1. wm size（标准方法，区分 Override/Physical）
        2. dumpsys window（备选方法）
        """
        if not self._device_serial:
            logger.warning("_fetch_device_resolution() 跳过: _device_serial 为空")
            return

        def _detect():
            """在后台线程中执行 ADB 命令获取分辨率。"""
            resolution = None
            method = None

            # 方法 1: wm size（标准方法）
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO
                )
                if result.returncode == 0:
                    # 解析所有匹配的分辨率行
                    lines = result.stdout.strip().splitlines()
                    override_w, override_h = 0, 0
                    physical_w, physical_h = 0, 0
                    for line in lines:
                        match = re.search(r"(\d+)x(\d+)", line)
                        if match:
                            w, h = int(match.group(1)), int(match.group(2))
                            if "Override" in line:
                                override_w, override_h = w, h
                            elif "Physical" in line:
                                physical_w, physical_h = w, h

                    # 优先使用 Override size
                    if override_w > 0 and override_h > 0:
                        resolution = (override_w, override_h)
                        method = "wm size (Override)"
                    elif physical_w > 0 and physical_h > 0:
                        resolution = (physical_w, physical_h)
                        method = "wm size (Physical)"
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
                        capture_output=True, text=True, timeout=5,
                        creationflags=_NO_WINDOW,
                        startupinfo=_STARTUPINFO
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
                    lambda w=width, h=height, m=method: self._apply_resolution(w, h, m)
                )
            else:
                logger.error(
                    "❌ 所有获取分辨率的方法都失败！将使用帧尺寸回退值（坐标可能不准确）"
                )

        threading.Thread(target=_detect, daemon=True).start()

    def _apply_resolution(self, width: int, height: int, method: str = "unknown"):
        """应用获取到的设备分辨率。

        Args:
            width: 设备宽度
            height: 设备高度
            method: 获取方法名称（用于日志）
        """
        old_w, old_h = self._device_width, self._device_height
        was_fallback = getattr(self._view, '_resolution_from_frame', False)

        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        self._update_resolution_label()

        if was_fallback:
            logger.info(
                "✅ 分辨率已修正: %dx%d -> %dx%d (来源: %s, 替换了帧尺寸回退)",
                old_w, old_h, width, height, method
            )
        else:
            logger.info("设备分辨率: %dx%d (来源: %s)", width, height, method)

    def _fetch_device_resolution_sync(self, timeout: float = 3.0) -> bool:
        """同步获取设备分辨率（阻塞等待）。

        在启动时调用，确保分辨率在帧更新前就绪。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True 表示成功获取到真实分辨率
        """
        if not self._device_serial:
            logger.warning("同步获取分辨率跳过: _device_serial 为空")
            return False

        import concurrent.futures

        def _fetch():
            """执行 ADB 命令。"""
            resolution = None
            method = None

            # 方法 1: wm size
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().splitlines()
                    override_w, override_h = 0, 0
                    physical_w, physical_h = 0, 0
                    for line in lines:
                        match = re.search(r"(\d+)x(\d+)", line)
                        if match:
                            w, h = int(match.group(1)), int(match.group(2))
                            if "Override" in line:
                                override_w, override_h = w, h
                            elif "Physical" in line:
                                physical_w, physical_h = w, h

                    if override_w > 0 and override_h > 0:
                        resolution = (override_w, override_h)
                        method = "sync/wm size (Override)"
                    elif physical_w > 0 and physical_h > 0:
                        resolution = (physical_w, physical_h)
                        method = "sync/wm size (Physical)"
                    else:
                        logger.warning(
                            "sync/wm size 返回格式异常: stdout=[%s]",
                            result.stdout.strip()[:100]
                        )
                else:
                    logger.warning(
                        "sync/wm size 失败 (returncode=%d): %s",
                        result.returncode,
                        result.stderr.strip()[:100]
                    )
            except Exception as e:
                logger.warning("sync/wm size 异常: %s", e)

            # 方法 2: dumpsys window
            if resolution is None:
                try:
                    result = subprocess.run(
                        ["adb", "-s", self._device_serial, "shell",
                         "dumpsys", "window", "displays"],
                        capture_output=True, text=True, timeout=5,
                        creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
                    )
                    if result.returncode == 0:
                        match = re.search(r"init=(\d+)x(\d+)", result.stdout)
                        if match:
                            resolution = (int(match.group(1)), int(match.group(2)))
                            method = "sync/dumpsys window"
                except Exception as e:
                    logger.debug("sync/dumpsys window 异常: %s", e)

            return resolution, method

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

        if resolution:
            width, height = resolution
            self._apply_resolution(width, height, method or "sync")
            return True
        else:
            # 智能估算
            estimated = self._estimate_resolution_from_frame()
            if estimated:
                width, height = estimated
                self._apply_resolution(
                    width, height,
                    f"估算(帧{self._view._frame_width}x{self._view._frame_height})"
                )
                logger.warning(
                    "⚠️ 使用估算分辨率: %dx%d (ADB 同步获取失败)",
                    width, height
                )
                return False
            else:
                logger.error("❌ 无法获取也无法估算分辨率！")
                return False

    def _estimate_resolution_from_frame(self):
        """基于帧尺寸和常见分辨率列表估算真实分辨率。"""
        fw = getattr(self._view, '_frame_width', 0)
        fh = getattr(self._view, '_frame_height', 0)

        if fw <= 0 or fh <= 0:
            return None

        common_resolutions = [
            (720, 1280), (720, 1440), (720, 1520), (720, 1560),
            (720, 1600),
            (1080, 1920), (1080, 2340), (1080, 2400), (1080, 2460),
            (1080, 2520),
            (1440, 2560), (1440, 2960), (1440, 3200),
            (1280, 720), (1920, 1080), (2560, 1440),
            (768, 1024), (1024, 768),
            (800, 1280), (1200, 1920),
        ]

        frame_ratio = fw / fh if fh > 0 else 1
        best_match = None
        min_diff = float('inf')
        for rw, rh in common_resolutions:
            res_ratio = rw / rh if rh > 0 else 1
            diff = abs(frame_ratio - res_ratio)
            if diff < min_diff:
                min_diff = diff
                best_match = (rw, rh)

        if best_match and min_diff < 0.1:
            return best_match
        return None

    def _detect_touch_device(self):
        """检测设备的触摸输入设备路径。

        通过 getevent -pl 获取触摸设备信息，找到支持 ABS_MT_POSITION_X/Y 的设备。
        """
        if not self._device_serial or self._touch_device_detected:
            return

        try:
            result = subprocess.run(
                ["adb", "-s", self._device_serial, "shell", "getevent", "-pl"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )

            if result.returncode != 0:
                logger.warning("getevent -pl 失败: %s", result.stderr.strip())
                self._use_sendevent = False
                return

            # 解析输出，找到触摸设备
            current_device = None
            has_mt_x = False
            has_mt_y = False
            max_x = 0
            max_y = 0

            for line in result.stdout.splitlines():
                # 检测设备路径行，如 "add device 1: /dev/input/event2"
                device_match = re.match(r"add device \d+: (/dev/input/event\d+)", line)
                if device_match:
                    # 保存上一个设备的信息（如果找到触摸设备）
                    if current_device and has_mt_x and has_mt_y:
                        self._touch_device_path = current_device
                        self._touch_max_x = max_x
                        self._touch_max_y = max_y
                        self._touch_device_detected = True
                        logger.info(
                            "检测到触摸设备: %s (max: %dx%d)",
                            current_device, max_x, max_y
                        )
                        return

                    current_device = device_match.group(1)
                    has_mt_x = False
                    has_mt_y = False
                    max_x = 0
                    max_y = 0
                    continue

                # 检测 ABS_MT_POSITION_X
                if "ABS_MT_POSITION_X" in line:
                    has_mt_x = True
                    # 解析 max 值，如 "    0035  : value 0, min 0, max 1079, fuzz 0, flat 0, resolution 0"
                    max_match = re.search(r"max (\d+)", line)
                    if max_match:
                        max_x = int(max_match.group(1))

                # 检测 ABS_MT_POSITION_Y
                if "ABS_MT_POSITION_Y" in line:
                    has_mt_y = True
                    max_match = re.search(r"max (\d+)", line)
                    if max_match:
                        max_y = int(max_match.group(1))

            # 检查最后一个设备
            if current_device and has_mt_x and has_mt_y:
                self._touch_device_path = current_device
                self._touch_max_x = max_x
                self._touch_max_y = max_y
                self._touch_device_detected = True
                logger.info(
                    "检测到触摸设备: %s (max: %dx%d)",
                    current_device, max_x, max_y
                )
            else:
                logger.warning("未找到触摸输入设备，将使用 input tap")
                self._use_sendevent = False

        except Exception as e:
            logger.warning("检测触摸设备失败: %s", e)
            self._use_sendevent = False

    def _sendevent_tap(self, x: int, y: int) -> bool:
        """使用 sendevent 发送触摸事件。

        直接写入内核输入设备，绕过 Android 输入过滤。
        需要 root 权限，使用 su 提权执行。

        Args:
            x: 设备 X 坐标
            y: 设备 Y 坐标

        Returns:
            是否成功
        """
        if not self._touch_device_path or not self._touch_device_detected:
            return False

        try:
            # 将设备坐标映射到触摸设备坐标
            # 触摸设备坐标范围是 [0, touch_max_x/y]
            # 设备坐标范围是 [0, device_width/height]
            if self._touch_max_x > 0 and self._touch_max_y > 0:
                touch_x = int(x * self._touch_max_x / self._device_width)
                touch_y = int(y * self._touch_max_y / self._device_height)
            else:
                # 如果没有获取到触摸设备最大值，假设与设备分辨率相同
                touch_x = x
                touch_y = y

            # 限制坐标范围
            touch_x = max(0, min(touch_x, self._touch_max_x if self._touch_max_x > 0 else self._device_width))
            touch_y = max(0, min(touch_y, self._touch_max_y if self._touch_max_y > 0 else self._device_height))

            # 递增跟踪 ID
            self._tracking_id = (self._tracking_id + 1) % 65535

            dev = self._touch_device_path

            # 构建触摸事件命令（使用 su 提权）
            # EV_ABS ABS_MT_TRACKING_ID <id>
            # EV_ABS ABS_MT_POSITION_X <x>
            # EV_ABS ABS_MT_POSITION_Y <y>
            # EV_KEY BTN_TOUCH 1
            # EV_SYN SYN_REPORT 0
            events = [
                # 触摸按下
                f"sendevent {dev} 3 57 {self._tracking_id}",  # EV_ABS ABS_MT_TRACKING_ID
                f"sendevent {dev} 3 53 {touch_x}",            # EV_ABS ABS_MT_POSITION_X
                f"sendevent {dev} 3 54 {touch_y}",            # EV_ABS ABS_MT_POSITION_Y
                f"sendevent {dev} 1 330 1",                   # EV_KEY BTN_TOUCH
                f"sendevent {dev} 0 0 0",                     # EV_SYN SYN_REPORT
                # 触摸抬起
                f"sendevent {dev} 3 57 -1",                   # EV_ABS ABS_MT_TRACKING_ID (释放)
                f"sendevent {dev} 1 330 0",                   # EV_KEY BTN_TOUCH
                f"sendevent {dev} 0 0 0",                     # EV_SYN SYN_REPORT
            ]

            # 使用 su -c 执行所有事件（需要 root 权限）
            # 将所有命令用 ; 连接，通过参数列表传递避免 shell 注入
            shell_cmd = "; ".join(events)

            cmd = ["adb", "-s", self._device_serial, "shell", "su", "-c", shell_cmd]
            result = subprocess.run(
                cmd, capture_output=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )

            success = (result.returncode == 0)
            if success:
                logger.debug("sendevent tap 成功: (%d, %d) -> (%d, %d)", x, y, touch_x, touch_y)
            else:
                stderr_msg = result.stderr.decode(errors='replace')[:200]
                logger.warning("sendevent tap 失败: %s", stderr_msg)
                # 如果是权限问题，禁用 sendevent
                if "Permission denied" in stderr_msg or "su:" in stderr_msg:
                    logger.info("设备无 root 权限，禁用 sendevent，回退到 input tap")
                    self._use_sendevent = False

            return success

        except Exception as e:
            logger.warning("sendevent tap 异常: %s", e)
            return False

    def _detect_rotation_immediate(self):
        """立即同步检测一次旋转状态（仅在 start 时调用）。

        确保打开窗口时就拿到正确的旋转方向，避免前 2 秒坐标错误。
        """
        if not self._device_serial:
            return
        try:
            result = subprocess.run(
                [
                    "adb", "-s", self._device_serial, "shell",
                    "dumpsys", "input"
                ],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            match = re.search(
                r"SurfaceOrientation:\s*(\d)", result.stdout
            )
            if match:
                rotation = int(match.group(1))
                if rotation != self._device_rotation:
                    old = self._device_rotation
                    self._device_rotation = rotation
                    logger.info("初始旋转检测: %d -> %d", old, rotation)
                    # 直接调用同步版本（在 start 上下文中安全）
                    if (old in (0, 2)) != (rotation in (0, 2)):
                        self._device_width, self._device_height = (
                            self._device_height, self._device_width
                        )
        except Exception as e:
            logger.debug("初始旋转检测失败: %s", e)

    def _check_rotation(self):
        """检测设备旋转状态（异步：在后台线程执行 ADB 命令）。"""
        if self._closed or not self._device_serial or self._rotation_locked:
            return
        # 防止重复启动检测线程
        if self._rotation_thread is not None and self._rotation_thread.is_alive():
            return

        def _detect():
            try:
                result = subprocess.run(
                    [
                        "adb", "-s", self._device_serial, "shell",
                        "dumpsys", "input"
                    ],
                    capture_output=True, text=True, timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO
                )
                match = re.search(
                    r"SurfaceOrientation:\s*(\d)", result.stdout
                )
                if match:
                    new_rotation = int(match.group(1))
                    # 通过信号回主线程
                    if not self._closed:
                        self._rotation_detected.emit(new_rotation)
            except Exception as e:
                logger.debug("检测旋转失败: %s", e)

        self._rotation_thread = threading.Thread(
            target=_detect, daemon=True, name="rotation-check"
        )
        self._rotation_thread.start()

    def _on_rotation_changed(self, old_rotation: int, new_rotation: int):
        """设备旋转变化时更新 UI。"""
        # 旋转 0/2 = 竖屏, 1/3 = 横屏
        # 交换设备宽高以匹配实际方向
        if (old_rotation in (0, 2)) != (new_rotation in (0, 2)):
            old_res = (self._device_width, self._device_height)
            self._device_width, self._device_height = (
                self._device_height, self._device_width
            )

            logger.info(
                "旋转交换分辨率: %dx%d -> %dx%d (rotation %d->%d)",
                old_res[0], old_res[1],
                self._device_width, self._device_height,
                old_rotation, new_rotation
            )

            self._view.set_device_resolution(
                self._device_width, self._device_height
            )
        self._update_resolution_label()
        self._update_rotation_label()
        # 自动适配
        QTimer.singleShot(100, self._on_fit)

        # 旋转后延迟刷新分辨率（防止使用过期值或重复交换）
        if (old_rotation in (0, 2)) != (new_rotation in (0, 2)):
            QTimer.singleShot(500, self._fetch_device_resolution)

    def _on_rotation_detected_from_thread(self, new_rotation: int):
        """后台旋转检测线程的回调（在主线程执行）。"""
        if new_rotation != self._device_rotation:
            old = self._device_rotation
            self._device_rotation = new_rotation
            logger.info("设备旋转: %d -> %d", old, new_rotation)
            self._on_rotation_changed(old, new_rotation)

    def _update_resolution_label(self):
        self._resolution_label.setText(
            f"分辨率: {self._device_width}x{self._device_height}"
        )

    def _update_rotation_label(self):
        names = {0: "竖屏(0°)", 1: "横屏(90°)", 2: "竖屏(180°)", 3: "横屏(270°)"}
        self._rotation_label.setText(
            f"方向: {names.get(self._device_rotation, '未知')}"
        )

    # -----------------------------------------------------------------------
    #  工具栏操作
    # -----------------------------------------------------------------------

    def _on_fit(self):
        self._view.fit_to_view()
        self._sync_zoom_spin()

    def _on_1to1(self):
        self._view.zoom_to(1.0)
        self._sync_zoom_spin()

    def _on_reset(self):
        self._view.reset_view()
        self._sync_zoom_spin()

    def _on_zoom_spin_changed(self, value: int):
        self._view.zoom_to(value / 100.0)

    def _sync_zoom_spin(self):
        zoom = self._view.get_zoom()
        self._zoom_spin.blockSignals(True)
        self._zoom_spin.setValue(int(zoom * 100))
        self._zoom_spin.blockSignals(False)
        self._zoom_label.setText(f"{int(zoom * 100)}%")

    def _on_rotation_lock_toggled(self, checked: bool):
        self._rotation_locked = checked
        self._combo_rotation.setEnabled(checked)
        if checked:
            # 锁定时立即应用选择的方向
            self._on_rotation_target_changed(self._combo_rotation.currentIndex())
        else:
            # 解锁时恢复自动旋转
            self._restore_auto_rotation()

    def _on_rotation_target_changed(self, index: int):
        """旋转目标改变：通过 ADB 强制设备旋转到指定方向。"""
        if not self._rotation_locked:
            return
        if index == 0:
            # "跟随设备" — 只锁定检测，不强制旋转
            self._restore_auto_rotation()
            return
        # index 1-4 对应 rotation 0-3
        target_rotation = index - 1
        self._force_rotation(target_rotation)

    def _force_rotation(self, rotation: int):
        """通过 ADB 强制设备旋转到指定方向。

        Args:
            rotation: 0=0°, 1=90°, 2=180°, 3=270°
        """
        if not self._device_serial:
            return
        try:
            # 关闭自动旋转
            subprocess.run(
                ["adb", "-s", self._device_serial, "shell",
                 "settings", "put", "system", "accelerometer_rotation", "0"],
                capture_output=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            # 设置目标方向
            subprocess.run(
                ["adb", "-s", self._device_serial, "shell",
                 "settings", "put", "system", "user_rotation", str(rotation)],
                capture_output=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            logger.info("强制设备旋转: rotation=%d", rotation)

            # 更新内部状态和 UI
            old = self._device_rotation
            self._device_rotation = rotation
            if (old in (0, 2)) != (rotation in (0, 2)):
                self._device_width, self._device_height = (
                    self._device_height, self._device_width
                )
                self._view.set_device_resolution(
                    self._device_width, self._device_height
                )
            self._update_resolution_label()
            self._update_rotation_label()
            QTimer.singleShot(200, self._on_fit)

        except Exception as e:
            logger.warning("强制旋转失败: %s", e)

    def _restore_auto_rotation(self):
        """恢复设备自动旋转。"""
        if not self._device_serial:
            return
        try:
            subprocess.run(
                ["adb", "-s", self._device_serial, "shell",
                 "settings", "put", "system", "accelerometer_rotation", "1"],
                capture_output=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            logger.debug("已恢复自动旋转")
        except Exception as e:
            logger.debug("恢复自动旋转失败: %s", e)

    # -----------------------------------------------------------------------
    #  点击事件
    # -----------------------------------------------------------------------

    def _on_point_clicked(self, dev_x: int, dev_y: int):
        """用户点击画面 -> 异步发送 tap 到设备。"""
        self._coord_label.setText(f"坐标: ({dev_x}, {dev_y})")
        self.device_point_clicked.emit(dev_x, dev_y)
        self._send_tap_async(dev_x, dev_y)

    def _on_mouse_moved(self, dev_x: int, dev_y: int):
        """鼠标悬停 -> 更新坐标显示。"""
        self._coord_label.setText(f"坐标: ({dev_x}, {dev_y})")

    def _send_tap_async(self, x: int, y: int):
        """通过 adb 异步发送点击事件（后台线程执行，不阻塞 UI）。

        优先使用 sendevent（绕过应用过滤），失败则回退到多种 input 命令。
        """
        if not self._device_serial:
            return

        # 速率限制：防止快速连击堆积 ADB 命令
        now = time.monotonic()
        with self._tap_lock:
            if now - self._last_tap_time < self._TAP_MIN_INTERVAL:
                return
            self._last_tap_time = now

        def _do_tap():
            success = False
            method = "unknown"

            try:
                # 优先使用 sendevent（绕过应用过滤）
                if self._use_sendevent and self._touch_device_detected:
                    method = "sendevent"
                    success = self._sendevent_tap(x, y)

                # sendevent 失败或不可用时，尝试多种 input 命令
                if not success:
                    success, method = self._try_input_tap(x, y)

                if not self._closed:
                    self._tap_finished.emit(success, x, y, method)
                    if success:
                        logger.debug("tap 成功 (%s): (%d, %d)", method, x, y)
                    else:
                        logger.warning("tap 失败 (%s): (%d, %d)", method, x, y)

            except Exception as e:
                logger.warning("发送 tap 失败 (%s): %s", method, e)
                if not self._closed:
                    self._tap_finished.emit(False, x, y, method)

        threading.Thread(
            target=_do_tap, daemon=True, name="tap-sender"
        ).start()
        logger.debug("异步 tap 已提交: (%d, %d)", x, y)

    def _try_input_tap(self, x: int, y: int) -> Tuple[bool, str]:
        """尝试多种 input tap 命令。

        按优先级尝试：
        1. input touchscreen tap（某些设备支持）
        2. input tap（标准方式）
        3. input motionevent DOWN/UP（模拟完整触摸事件）

        Returns:
            (成功与否, 使用的方法名称)
        """
        serial = self._device_serial

        # 方法列表：(命令参数列表, 方法名称)
        methods = [
            # 方法1: input touchscreen tap（某些设备支持，可能绕过过滤）
            (["input", "touchscreen", "tap", str(x), str(y)], "input touchscreen tap"),
            # 方法2: 标准 input tap
            (["input", "tap", str(x), str(y)], "input tap"),
            # 方法3: input motionevent（模拟完整触摸事件序列）
            (["input", "motionevent", "DOWN", str(x), str(y), "&&",
              "input", "motionevent", "UP", str(x), str(y)], "input motionevent"),
        ]

        for args, method_name in methods:
            try:
                if self._adb_core is not None:
                    # 使用 adb_core 执行
                    result = self._adb_core.execute(
                        ["shell"] + args, device=serial, timeout=5
                    )
                    success = (result.returncode == 0)
                else:
                    # 直接执行
                    cmd = ["adb", "-s", serial, "shell"] + args
                    result = subprocess.run(
                        cmd, capture_output=True, timeout=5,
                        creationflags=_NO_WINDOW,
                        startupinfo=_STARTUPINFO
                    )
                    success = (result.returncode == 0)

                if success:
                    logger.debug("%s 成功: (%d, %d)", method_name, x, y)
                    return True, method_name
                else:
                    logger.debug("%s 失败，尝试下一种方法", method_name)

            except Exception as e:
                logger.debug("%s 异常: %s，尝试下一种方法", method_name, e)
                continue

        # 所有方法都失败
        return False, "input tap (all methods failed)"

    def _on_tap_finished(self, success: bool, x: int, y: int, method: str):
        """tap 完成回调（主线程）。更新状态栏反馈。"""
        if success:
            logger.debug("tap 成功: (%d, %d) [%s]", x, y, method)
            # 成功时显示注入方式（短暂显示）
            self._status_label.setText(f"✓ {method}: ({x}, {y})")
            self._status_label.setStyleSheet(
                "color: #3fb950; font-size: 11px;"
            )
            # 2 秒后恢复状态
            QTimer.singleShot(2000, self._restore_status)
        else:
            logger.warning("tap 失败: (%d, %d) [%s]", x, y, method)
            self._status_label.setText(f"✗ {method} 失败: ({x}, {y})")
            self._status_label.setStyleSheet(
                "color: #f85149; font-size: 11px;"
            )
            # 3 秒后恢复状态
            QTimer.singleShot(3000, self._restore_status)

    def _restore_status(self):
        """恢复状态栏为正常状态。"""
        if self._closed:
            return
        self._status_label.setText("已连接")
        self._status_label.setStyleSheet(
            "color: #3fb950; font-size: 11px;"
        )

    def _on_resolution_failed(self):
        """设备分辨率获取失败时的 UI 反馈。"""
        self._status_label.setText("⚠ 分辨率获取失败，点击功能不可用")
        self._status_label.setStyleSheet(
            "color: #d29922; font-size: 11px;"
        )

    # -----------------------------------------------------------------------
    #  窗口事件
    # -----------------------------------------------------------------------

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # 显示后自适应一次
        QTimer.singleShot(200, self._on_fit)
