from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QPixmap, QImage, QBrush
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


class _ImageLabel(QLabel):
    point_clicked = pyqtSignal(int, int)
    mouse_position = pyqtSignal(int, int)

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
        dev_x = int(ix * bw / pw)
        dev_y = int(iy * bh / ph)
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
    point_selected = pyqtSignal(int, int)
    mouse_moved = pyqtSignal(int, int)

    def __init__(self, screen_capture=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._btn_capture = QPushButton("截屏")
        self._btn_capture.setFixedHeight(26)
        self._btn_capture.clicked.connect(self.capture_and_display)
        toolbar.addWidget(self._btn_capture)

        self._btn_clear = QPushButton("清除标注")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.clicked.connect(self.clear_markers)
        toolbar.addWidget(self._btn_clear)

        toolbar.addWidget(QLabel("缩放:"))
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(10, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        toolbar.addWidget(self._zoom_slider)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(45)
        toolbar.addWidget(self._zoom_label)

        self._btn_calibrate = QPushButton("校准模式")
        self._btn_calibrate.setFixedHeight(26)
        self._btn_calibrate.setCheckable(True)
        self._btn_calibrate.clicked.connect(self._on_calibrate_toggled)
        toolbar.addWidget(self._btn_calibrate)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        self._image_label = _ImageLabel()
        self._image_label.point_clicked.connect(self._on_point_clicked)
        self._image_label.mouse_position.connect(self.mouse_moved.emit)
        scroll.setWidget(self._image_label)
        layout.addWidget(scroll, stretch=1)

        info_bar = QHBoxLayout()
        self._coord_label = QLabel("设备坐标: (-, -)")
        self._coord_label.setFont(QFont("Consolas", 10))
        info_bar.addWidget(self._coord_label)
        info_bar.addStretch()
        layout.addLayout(info_bar)

    def _on_zoom_changed(self, value: int):
        zoom = value / 100.0
        self._zoom_label.setText(f"{value}%")
        self._image_label.set_zoom(zoom)

    def _on_calibrate_toggled(self, checked: bool):
        self._image_label.set_calibration_mode(checked)
        if checked:
            self._btn_calibrate.setStyleSheet("background-color: #1f6feb; color: white;")
        else:
            self._btn_calibrate.setStyleSheet("")

    def _on_point_clicked(self, x: int, y: int):
        self._coord_label.setText(f"设备坐标: ({x}, {y})")
        self.point_selected.emit(x, y)

    def set_screen_capture(self, screen_capture):
        self._screen_capture = screen_capture

    def capture_and_display(self):
        if self._screen_capture is None:
            return
        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return
        self._display_frame(frame)

    def _display_frame(self, frame: np.ndarray):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_img)
        self._image_label.set_pixmap(pixmap)

    def clear_markers(self):
        self._image_label.clear_markers()
        self._coord_label.setText("设备坐标: (-, -)")

    def get_selected_point(self) -> tuple[int, int] | None:
        return self._image_label.get_active_marker()

    def set_calibration_mode(self, enabled: bool):
        self._btn_calibrate.setChecked(enabled)
        self._on_calibrate_toggled(enabled)

    def set_base_resolution(self, width: int, height: int):
        self._image_label.set_base_resolution(width, height)
