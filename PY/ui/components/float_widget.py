from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class FloatingWidget(QWidget):
    _update_price_signal = pyqtSignal(str)
    _update_mail_signal = pyqtSignal(int)
    _update_status_signal = pyqtSignal(str, str)

    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_position = QPoint()
        self._paused = False
        self._init_window()
        self._init_ui()
        self._connect_signals()

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 140)
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.topRight().x() - 220, geo.topRight().y() + 20)
        else:
            self.move(1600, 20)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._price_label = QLabel("价格: --")
        self._price_label.setStyleSheet(
            "color: #00ff88; font-size: 16px; font-weight: bold;"
        )
        self._price_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))

        self._mail_label = QLabel("邮件: 0封")
        self._mail_label.setStyleSheet("color: #ffaa00; font-size: 14px;")
        self._mail_label.setFont(QFont("Microsoft YaHei", 9))

        self._status_label = QLabel("状态: 空闲")
        self._status_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        self._status_label.setFont(QFont("Microsoft YaHei", 8))

        layout.addWidget(self._price_label)
        layout.addWidget(self._mail_label)
        layout.addWidget(self._status_label)

        # control buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_pause = QPushButton("暂停")
        self._btn_pause.setFixedHeight(24)
        self._btn_pause.setStyleSheet(
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #d29922; font-size: 11px; padding: 2px 8px; }"
            "QPushButton:hover { background-color: #30363d; }"
        )
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.clicked.connect(self._on_pause_clicked)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setFixedHeight(24)
        self._btn_stop.setStyleSheet(
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #da3633; font-size: 11px; padding: 2px 8px; }"
            "QPushButton:hover { background-color: #30363d; }"
        )
        self._btn_stop.setCursor(Qt.PointingHandCursor)
        self._btn_stop.clicked.connect(self.stop_requested.emit)

        btn_row.addWidget(self._btn_pause)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

    def _connect_signals(self):
        self._update_price_signal.connect(self._on_price_updated)
        self._update_mail_signal.connect(self._on_mail_updated)
        self._update_status_signal.connect(self._on_status_updated)

    def _on_pause_clicked(self):
        self._paused = not self._paused
        if self._paused:
            self._btn_pause.setText("继续")
            self._btn_pause.setStyleSheet(
                "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
                "border-radius: 4px; color: #3fb950; font-size: 11px; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #30363d; }"
            )
        else:
            self._btn_pause.setText("暂停")
            self._btn_pause.setStyleSheet(
                "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
                "border-radius: 4px; color: #d29922; font-size: 11px; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #30363d; }"
            )
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
        self._status_label.setText(f"状态: {status}")
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 12px;"
        )

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.85)
        bg_color = QColor("#1a1a2e")
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor("#2a2a4e"), 1))
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_position.isNull():
            self.move(event.globalPos() - self._drag_position)
            event.accept()
