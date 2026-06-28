from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from core.device_manager import DeviceManager


class DeviceBindWidget(QWidget):
    """任务级设备绑定组件：显示设备信息，允许选择/重选设备，显示在线状态。"""

    device_selected = pyqtSignal(str, str)   # serial, label
    rename_requested = pyqtSignal(str, str)  # serial, new_label
    open_mirror_requested = pyqtSignal(str)  # serial  -- 新增：打开高清投屏

    _MIRROR_STYLE_ACTIVE = (
        "QPushButton { background-color: #da3633; border: 1px solid #f85149; "
        "border-radius: 4px; color: #ffffff; font-size: 12px; padding: 2px 10px; }"
        "QPushButton:hover { background-color: #f85149; }"
        "QPushButton:disabled { background-color: #21262d; color: #484f58; border-color: #30363d; }"
    )
    _MIRROR_STYLE_INACTIVE = (
        "QPushButton { background-color: #1f6feb; border: 1px solid #388bfd; "
        "border-radius: 4px; color: #ffffff; font-size: 12px; padding: 2px 10px; }"
        "QPushButton:hover { background-color: #388bfd; }"
        "QPushButton:disabled { background-color: #21262d; color: #484f58; border-color: #30363d; }"
    )

    def __init__(self, device_manager: DeviceManager, adb_core, parent=None):
        super().__init__(parent)
        self._device_manager = device_manager
        self._adb_core = adb_core
        self._bound_serial = ""
        self._bound_label = ""
        self._mirror_active = False
        self._online = False  # 缓存的设备在线状态，由 _refresh_display 定时更新
        self._init_ui()
        self._start_poll()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("设备信息")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        layout.addWidget(title)

        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(16)
        self._status_dot.setStyleSheet("color: #8b949e; font-size: 14px;")

        self._info_label = QLabel("未选择设备")
        self._info_label.setFont(QFont("Microsoft YaHei", 10))
        self._info_label.setWordWrap(True)

        info_row = QHBoxLayout()
        info_row.addWidget(self._status_dot)
        info_row.addWidget(self._info_label, stretch=1)
        layout.addLayout(info_row)

        btn_row = QHBoxLayout()
        self._btn_select = QPushButton("选择")
        self._btn_select.setFixedHeight(28)
        self._btn_select.clicked.connect(self._on_select)
        btn_row.addWidget(self._btn_select)

        self._btn_rename = QPushButton("重命名")
        self._btn_rename.setFixedHeight(28)
        self._btn_rename.setVisible(False)
        self._btn_rename.clicked.connect(self._on_rename)
        btn_row.addWidget(self._btn_rename)

        self._btn_mirror = QPushButton("高清投屏")
        self._btn_mirror.setFixedHeight(28)
        self._btn_mirror.setStyleSheet(self._MIRROR_STYLE_INACTIVE)
        self._btn_mirror.setEnabled(False)
        self._btn_mirror.clicked.connect(self._on_open_mirror)
        btn_row.addWidget(self._btn_mirror)

        layout.addLayout(btn_row)

    def set_bound_device(self, serial: str, label: str = "") -> None:
        self._bound_serial = serial or ""
        self._bound_label = label or serial or ""
        self._refresh_display()

    def _refresh_display(self):
        if not self._bound_serial:
            self._online = False
            self._info_label.setText("未选择设备")
            self._status_dot.setStyleSheet("color: #8b949e; font-size: 14px;")
            self._btn_select.setText("选择")
            self._btn_rename.setVisible(False)
            self._btn_mirror.setEnabled(False)
            return

        online = self._is_device_online()
        self._online = online  # 缓存在线状态，供 update_mini_info 等读取，避免同步调用 adb
        display = self._bound_label if self._bound_label else self._bound_serial
        self._info_label.setText(display)
        if online:
            self._status_dot.setStyleSheet("color: #3fb950; font-size: 14px;")
        else:
            self._status_dot.setStyleSheet("color: #d29922; font-size: 14px;")
            # 设备离线时重置投屏按钮状态
            if self._mirror_active:
                self.set_mirror_active(False)
        self._btn_select.setText("重选")
        self._btn_rename.setVisible(True)
        self._btn_mirror.setEnabled(online)

    def _is_device_online(self) -> bool:
        if not self._bound_serial:
            return False
        try:
            serials = self._device_manager.refresh_device_list()
            return self._bound_serial in serials
        except Exception:
            return False

    @property
    def online(self) -> bool:
        """返回缓存的设备在线状态（由定时器刷新，不触发 adb 调用）。"""
        return self._online

    def _start_poll(self):
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh_display)
        self._timer.start()

    def _on_select(self):
        try:
            devices = self._device_manager.refresh_device_list()
        except Exception:
            devices = []
        if not devices:
            QMessageBox.information(self, "设备选择", "未检测到已连接设备，请确认 ADB 连接。")
            return
        item, ok = QInputDialog.getItem(self, "选择设备", "设备列表:", devices, 0, False)
        if ok and item:
            try:
                self._device_manager.select_device(item)
            except Exception:
                pass
            self._bound_serial = item
            self._bound_label = item
            self._refresh_display()
            self.device_selected.emit(self._bound_serial, self._bound_label)

    def _on_rename(self):
        if not self._bound_serial:
            return
        name, ok = QInputDialog.getText(self, "重命名设备", "自定义名称:", text=self._bound_label)
        if ok and name.strip():
            self._bound_label = name.strip()
            self._refresh_display()
            self.rename_requested.emit(self._bound_serial, self._bound_label)

    def _on_open_mirror(self):
        """发出打开高清投屏的信号。"""
        if self._bound_serial:
            self.open_mirror_requested.emit(self._bound_serial)

    def set_mirror_active(self, active: bool):
        """更新投屏按钮的状态（文字和样式）。"""
        self._mirror_active = active
        if active:
            self._btn_mirror.setText("取消投屏")
            self._btn_mirror.setStyleSheet(self._MIRROR_STYLE_ACTIVE)
        else:
            self._btn_mirror.setText("高清投屏")
            self._btn_mirror.setStyleSheet(self._MIRROR_STYLE_INACTIVE)
