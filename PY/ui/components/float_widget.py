from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class FloatingWidget(QWidget):
    """悬浮窗：信息分层显示 + 呼吸灯动画 + QSS 统一样式。"""

    _update_price_signal = pyqtSignal(str)
    _update_mail_signal = pyqtSignal(int)
    _update_status_signal = pyqtSignal(str, str)

    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_position = QPoint()
        self._paused = False
        self._status_color = "#a0a0a0"
        self._breathing_phase = 0
        self._is_running = False
        self._compact_mode = True

        self._init_window()
        self._init_ui()
        self._connect_signals()
        self._init_breathing_animation()

    def _init_window(self):
        self.setObjectName("floatingWidget")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 160)
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.topRight().x() - 220, geo.topRight().y() + 20)
        else:
            self.move(1600, 20)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # ---- 主状态行（大字 + 呼吸灯） ----
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setStyleSheet("color: #a0a0a0; font-size: 14px;")
        status_row.addWidget(self._status_dot)

        self._status_label = QLabel("空闲")
        self._status_label.setObjectName("floatStatus")
        self._status_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._status_label.setStyleSheet("color: #a0a0a0;")
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # ---- 分隔线 ----
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #30363d;")
        layout.addWidget(separator)

        # ---- 关键数据区 ----
        self._price_label = QLabel("价格: --")
        self._price_label.setObjectName("floatPrice")
        self._price_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self._price_label.setStyleSheet("color: #3fb950;")

        self._mail_label = QLabel("邮件: 0封")
        self._mail_label.setObjectName("floatMail")
        self._mail_label.setFont(QFont("Microsoft YaHei", 9))
        self._mail_label.setStyleSheet("color: #d29922;")

        layout.addWidget(self._price_label)
        layout.addWidget(self._mail_label)

        layout.addStretch()

        # ---- 控制按钮区 ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_pause = QPushButton("暂停")
        self._btn_pause.setObjectName("floatBtnPause")
        self._btn_pause.setFixedHeight(26)
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.clicked.connect(self._on_pause_clicked)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setObjectName("floatBtnStop")
        self._btn_stop.setFixedHeight(26)
        self._btn_stop.setCursor(Qt.PointingHandCursor)
        self._btn_stop.clicked.connect(self.stop_requested.emit)

        btn_row.addWidget(self._btn_pause)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

    def _connect_signals(self):
        self._update_price_signal.connect(self._on_price_updated)
        self._update_mail_signal.connect(self._on_mail_updated)
        self._update_status_signal.connect(self._on_status_updated)

    def _init_breathing_animation(self):
        """呼吸灯动画定时器。"""
        self._breathing_timer = QTimer(self)
        self._breathing_timer.timeout.connect(self._on_breathing_tick)

    def _on_breathing_tick(self):
        """呼吸灯动画 tick。"""
        self._breathing_phase = (self._breathing_phase + 1) % 40
        # 计算透明度（0.4 ~ 1.0 之间脉动）
        import math
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self._breathing_phase / 40.0 * 2 * math.pi))
        color = QColor(self._status_color)
        color.setAlphaF(alpha)
        self._status_dot.setStyleSheet(
            f"color: {color.name()}; font-size: 14px;"
        )

    def _on_pause_clicked(self):
        self._paused = not self._paused
        if self._paused:
            self._btn_pause.setText("继续")
        else:
            self._btn_pause.setText("暂停")
        self.pause_requested.emit()

    def update_price(self, price):
        self._update_price_signal.emit(str(price))

    def update_mail_count(self, count):
        self._update_mail_signal.emit(int(count))

    def update_status(self, status, color="#a0a0a0"):
        self._update_status_signal.emit(str(status), str(color))

    def _on_price_updated(self, price):
        self._price_label.setText(f"价格: {price}")

    def _on_mail_updated(self, count):
        self._mail_label.setText(f"邮件: {count}封")

    def _on_status_updated(self, status, color):
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_color = color
        # 运行中状态启动呼吸灯
        if status in ("运行中", "监控中"):
            self._is_running = True
            if not self._breathing_timer.isActive():
                self._breathing_timer.start(50)
        else:
            self._is_running = False
            if self._breathing_timer.isActive():
                self._breathing_timer.stop()
            self._status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.9)
        # 使用 GitHub Dark 配色
        bg_color = QColor("#161b22")
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor("#30363d"), 1))
        painter.drawRoundedRect(self.rect(), 10, 10)
        # 顶部强调线
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._status_color if self._is_running else "#30363d"))
        painter.drawRoundedRect(0, 0, self.width(), 2, 10, 10)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_position.isNull():
            self.move(event.globalPos() - self._drag_position)
            event.accept()

    def enterEvent(self, event):
        """鼠标悬停时展开详情。"""
        self._compact_mode = False
        self.setFixedSize(220, 180)
        event.accept()

    def leaveEvent(self, event):
        """鼠标离开时恢复紧凑模式。"""
        self._compact_mode = True
        self.setFixedSize(200, 160)
        event.accept()

    def closeEvent(self, event):
        if self._breathing_timer.isActive():
            self._breathing_timer.stop()
        super().closeEvent(event)
