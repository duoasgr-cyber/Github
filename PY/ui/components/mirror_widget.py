"""实时投屏镜像控件。

显示 ScrcpyCapture 的实时视频帧，捕获鼠标交互：
  - 始终把点击/滑动注入设备（control 协议实时跟随，或 adb 降级整体注入）
  - 发出 interaction_started/ended 信号供 StepRecorder 录制为工作流步骤

坐标体系（关键）：
  display 坐标 ──(÷zoom)──▶ img 坐标 ──┬──(=视频流坐标)──▶ 注入 ScrcpyCapture
                                         └──(×base_resolution÷pixmap_size)──▶ 设备坐标 ──▶ 录制步骤
img 坐标即视频流坐标系（pixmap 来自视频帧），设备坐标用于工作流步骤（跨设备回放）。
"""
import time
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QFont, QImage, QPainter, QPen, QColor, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import numpy as np


_FRAME_PULL_INTERVAL_MS = 33  # ~30fps 拉取最新帧
_RECORD_TICK_MS = 1000        # 录制计时刷新


class _MirrorLabel(QLabel):
    """实时帧显示 + 鼠标交互捕获。"""

    # 交互信号：x_dev, y_dev, timestamp
    interaction_started = pyqtSignal(int, int, float)
    interaction_ended = pyqtSignal(int, int, float)
    # 鼠标位置（设备坐标），用于状态栏显示
    mouse_moved = pyqtSignal(int, int)
    # 缩放变化（滚轮触发），同步工具栏 slider
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self._base_resolution: Tuple[int, int] = (2400, 1080)
        self._pressed: bool = False
        self._interaction_enabled: bool = True
        self._screen_capture = None  # 注入用
        self.setMinimumSize(200, 150)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    # ---- 配置 ----
    def set_base_resolution(self, width: int, height: int) -> None:
        self._base_resolution = (int(width), int(height))

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.1, min(zoom, 5.0))
        self._update_display()

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._interaction_enabled = enabled

    def set_screen_capture(self, screen_capture) -> None:
        self._screen_capture = screen_capture
        self._image_label.set_screen_capture(screen_capture)

    # ---- 帧渲染 ----
    def set_frame(self, frame: np.ndarray) -> None:
        """接收一帧（BGR ndarray）并渲染。"""
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self._pixmap = QPixmap.fromImage(q_img)
        self._update_display()

    def _update_display(self) -> None:
        if self._pixmap is None:
            return
        new_w = max(1, int(self._pixmap.width() * self._zoom))
        new_h = max(1, int(self._pixmap.height() * self._zoom))
        scaled = self._pixmap.scaled(new_w, new_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self.setMinimumSize(new_w, new_h)

    # ---- 坐标映射 ----
    def _display_to_img(self, dx: int, dy: int) -> Tuple[int, int]:
        return int(dx / self._zoom), int(dy / self._zoom)

    def _img_to_device(self, ix: int, iy: int) -> Tuple[int, int]:
        if self._pixmap is None:
            return ix, iy
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw == 0 or ph == 0:
            return ix, iy
        bw, bh = self._base_resolution
        return int(ix * bw / pw), int(iy * bh / ph)

    def _pos_to_coords(self, pos: QPoint) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """返回 ((img_x, img_y), (dev_x, dev_y))。img 即视频流坐标。"""
        ix, iy = self._display_to_img(pos.x(), pos.y())
        return (ix, iy), self._img_to_device(ix, iy)

    # ---- 鼠标事件 ----
    def mousePressEvent(self, event):
        if self._pixmap is None or not self._interaction_enabled:
            return
        if event.button() != Qt.LeftButton:
            return
        (ix, iy), (dx, dy) = self._pos_to_coords(event.pos())
        # 边界检查
        if not (0 <= ix < self._pixmap.width() and 0 <= iy < self._pixmap.height()):
            return
        self._pressed = True
        ts = time.time()
        # 注入 + 发信号
        if self._screen_capture is not None:
            self._screen_capture.begin_touch(ix, iy)
        self.interaction_started.emit(dx, dy, ts)

    def mouseMoveEvent(self, event):
        if self._pixmap is None:
            return
        (ix, iy), (dx, dy) = self._pos_to_coords(event.pos())
        if 0 <= ix < self._pixmap.width() and 0 <= iy < self._pixmap.height():
            self.mouse_moved.emit(dx, dy)
        if self._pressed and self._interaction_enabled:
            if self._screen_capture is not None:
                self._screen_capture.move_touch(ix, iy)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._pressed:
            return
        self._pressed = False
        if self._pixmap is None or not self._interaction_enabled:
            return
        (ix, iy), (dx, dy) = self._pos_to_coords(event.pos())
        ts = time.time()
        if self._screen_capture is not None:
            self._screen_capture.end_touch(ix, iy)
        self.interaction_ended.emit(dx, dy, ts)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            new_zoom = min(self._zoom * 1.1, 5.0)
        elif delta < 0:
            new_zoom = max(self._zoom / 1.1, 0.1)
        else:
            return
        self.set_zoom(new_zoom)
        self.zoom_changed.emit(new_zoom)


class MirrorWidget(QWidget):
    """实时投屏镜像面板：帧渲染 + 交互注入 + 录制开关。"""

    # 用户点击录制按钮（True=开始录制，False=停止）
    record_toggled = pyqtSignal(bool)
    # 转发交互信号（供 StepRecorder 连接）：x_dev, y_dev, timestamp
    interaction_started = pyqtSignal(int, int, float)
    interaction_ended = pyqtSignal(int, int, float)

    def __init__(self, screen_capture=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._recording: bool = False
        self._record_start_time: float = 0.0
        self._setup_ui()
        self._connect_signals()
        # 同步构造传入的 screen_capture 给显示标签
        if self._screen_capture is not None:
            self._image_label.set_screen_capture(self._screen_capture)

        # 帧拉取定时器
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._pull_frame)
        self._frame_timer.start(_FRAME_PULL_INTERVAL_MS)

        # 录制计时刷新
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_record_timer)

    # ---- UI ----
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._btn_record = QPushButton("开始录制")
        self._btn_record.setFixedHeight(28)
        self._btn_record.setCheckable(True)
        self._btn_record.setCursor(Qt.PointingHandCursor)
        self._btn_record.setStyleSheet(
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #d29922; font-size: 12px; padding: 2px 10px; }"
            "QPushButton:checked { background-color: #da3633; color: #ffffff; }"
            "QPushButton:hover { background-color: #30363d; }"
        )
        toolbar.addWidget(self._btn_record)

        self._record_status = QLabel("空闲")
        self._record_status.setFont(QFont("Microsoft YaHei", 9))
        self._record_status.setStyleSheet("color: #a0a0a0;")
        toolbar.addWidget(self._record_status)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("缩放:"))
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(10, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(110)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider)
        toolbar.addWidget(self._zoom_slider)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(45)
        toolbar.addWidget(self._zoom_label)

        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        self._image_label = _MirrorLabel()
        scroll.setWidget(self._image_label)
        layout.addWidget(scroll, stretch=1)

        info_bar = QHBoxLayout()
        self._coord_label = QLabel("设备坐标: (-, -)")
        self._coord_label.setFont(QFont("Consolas", 10))
        info_bar.addWidget(self._coord_label)
        info_bar.addStretch()
        self._inject_label = QLabel("注入: --")
        self._inject_label.setFont(QFont("Microsoft YaHei", 9))
        info_bar.addWidget(self._inject_label)
        layout.addLayout(info_bar)

    def _connect_signals(self):
        self._btn_record.toggled.connect(self._on_record_toggled)
        self._image_label.interaction_started.connect(self._on_interaction_started)
        self._image_label.interaction_ended.connect(self._on_interaction_ended)
        self._image_label.mouse_moved.connect(self._on_mouse_moved)
        self._image_label.zoom_changed.connect(self._sync_zoom_ui)
        # 转发交互信号给外部（StepRecorder）
        self._image_label.interaction_started.connect(self.interaction_started)
        self._image_label.interaction_ended.connect(self.interaction_ended)

    # ---- 外部接口 ----
    def set_screen_capture(self, screen_capture) -> None:
        self._screen_capture = screen_capture

    def set_base_resolution(self, width: int, height: int) -> None:
        self._image_label.set_base_resolution(width, height)
        if self._screen_capture is not None:
            self._screen_capture.set_base_resolution(width, height)

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._image_label.set_interaction_enabled(enabled)

    def is_recording(self) -> bool:
        return self._recording

    def set_recording(self, active: bool) -> None:
        """同步录制状态到 UI（由外部调用，配合 record_toggled 信号）。"""
        self._recording = active
        if active:
            self._record_start_time = time.time()
            self._btn_record.setText("停止录制")
            self._record_status.setText("● 录制中 0s")
            self._record_status.setStyleSheet("color: #da3633; font-weight: bold;")
            self._tick_timer.start(_RECORD_TICK_MS)
        else:
            self._btn_record.setText("开始录制")
            self._record_status.setText("空闲")
            self._record_status.setStyleSheet("color: #a0a0a0;")
            self._tick_timer.stop()

    # ---- 内部槽 ----
    def _on_record_toggled(self, checked: bool):
        # 仅发信号，实际录制启停由 main_window 处理后回调 set_recording
        self.record_toggled.emit(checked)

    def _on_zoom_slider(self, value: int):
        zoom = value / 100.0
        self._zoom_label.setText(f"{value}%")
        self._image_label.set_zoom(zoom)

    def _sync_zoom_ui(self, zoom: float):
        v = int(zoom * 100)
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(v)
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{v}%")

    def _on_mouse_moved(self, x: int, y: int):
        self._coord_label.setText(f"设备坐标: ({x}, {y})")

    def _on_interaction_started(self, x: int, y: int, ts: float):
        # 注入方式提示
        if self._screen_capture is not None and self._screen_capture.is_control_available():
            self._inject_label.setText("注入: scrcpy(control)")
            self._inject_label.setStyleSheet("color: #3fb950;")
        else:
            self._inject_label.setText("注入: adb input(降级)")
            self._inject_label.setStyleSheet("color: #d29922;")

    def _on_interaction_ended(self, x: int, y: int, ts: float):
        pass

    def _pull_frame(self):
        if self._screen_capture is None:
            return
        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return
        self._image_label.set_frame(frame)

    def _update_record_timer(self):
        elapsed = int(time.time() - self._record_start_time)
        self._record_status.setText(f"● 录制中 {elapsed}s")

    def cleanup(self):
        self._frame_timer.stop()
        self._tick_timer.stop()
