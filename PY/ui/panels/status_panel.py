from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


class StatusPanel(QWidget):
    start_monitoring = pyqtSignal()
    stop_monitoring = pyqtSignal()
    pause_monitoring = pyqtSignal()
    resume_monitoring = pyqtSignal()
    refresh_price = pyqtSignal()
    reset_mail_count = pyqtSignal()
    start_clicker = pyqtSignal(int, int, int)
    stop_clicker = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._create_status_group())
        layout.addWidget(self._create_control_group())
        layout.addStretch()

    def _create_status_group(self):
        group = QGroupBox("运行状态")
        glayout = QVBoxLayout(group)

        self._status_label = QLabel("空闲")
        self._status_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self._status_label.setStyleSheet("color: gray;")
        self._status_label.setAlignment(Qt.AlignCenter)
        glayout.addWidget(self._status_label)

        self._workflow_label = QLabel("当前工作流: --")
        glayout.addWidget(self._workflow_label)

        self._step_label = QLabel("当前步骤: --")
        glayout.addWidget(self._step_label)

        self._price_label = QLabel("¥0")
        self._price_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        self._price_label.setStyleSheet("color: #00ff88;")
        self._price_label.setAlignment(Qt.AlignCenter)
        glayout.addWidget(self._price_label)

        self._mail_count_label = QLabel("已发送: 0")
        self._mail_count_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
        glayout.addWidget(self._mail_count_label)

        return group

    def _create_control_group(self):
        group = QGroupBox("控制区")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        # Row 0: 20发模式 / 子弹数量 / 单发价格
        self._btn_20mode = QPushButton("20发模式: 关")
        self._btn_20mode.setCheckable(True)
        self._btn_20mode.toggled.connect(self._on_20mode_toggled)
        grid.addWidget(self._btn_20mode, 0, 0)

        lbl_bullet = QLabel("子弹数量:")
        grid.addWidget(lbl_bullet, 0, 1)
        self._spin_bullet = QSpinBox()
        self._spin_bullet.setRange(1, 99999)
        self._spin_bullet.setValue(1500)
        grid.addWidget(self._spin_bullet, 0, 2)

        lbl_price = QLabel("单发价格:")
        grid.addWidget(lbl_price, 0, 3)
        self._spin_price = QDoubleSpinBox()
        self._spin_price.setRange(0.0, 999999.0)
        self._spin_price.setDecimals(2)
        self._spin_price.setValue(0.5)
        grid.addWidget(self._spin_price, 0, 4)

        # Row 1: 启动控制
        self._btn_start = QPushButton("从第一行启动")
        self._btn_start.setProperty("class", "primary")
        self._btn_start.clicked.connect(self.start_monitoring.emit)
        grid.addWidget(self._btn_start, 1, 0)

        self._btn_start_from = QPushButton("从选中步骤启动")
        self._btn_start_from.clicked.connect(self.start_monitoring.emit)
        grid.addWidget(self._btn_start_from, 1, 1)

        self._btn_stop = QPushButton("停止/继续")
        self._btn_stop.setProperty("class", "danger")
        self._btn_stop.clicked.connect(self.stop_monitoring.emit)
        grid.addWidget(self._btn_stop, 1, 2)

        # Row 2: 预留按钮（禁用）
        for col in range(3):
            btn = QPushButton("预留")
            btn.setEnabled(False)
            grid.addWidget(btn, 2, col)

        # Row 3: 更多预留按钮（禁用）
        for col in range(3):
            btn = QPushButton("预留")
            btn.setEnabled(False)
            grid.addWidget(btn, 3, col)

        return group

    def _on_20mode_toggled(self, checked: bool):
        self._btn_20mode.setText(f"20发模式: {'开' if checked else '关'}")

    # ---------- 公开接口 ----------

    def update_price(self, price: int):
        self._price_label.setText(f"¥{price}")

    def update_mail_count(self, count: int):
        self._mail_count_label.setText(f"已发送: {count}")

    def update_status(self, status: str, color: str):
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")

    def update_current_workflow(self, name: str):
        self._workflow_label.setText(f"当前工作流: {name}")

    def update_current_step(self, step_info: str):
        self._step_label.setText(f"当前步骤: {step_info}")