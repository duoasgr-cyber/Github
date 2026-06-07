from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QTextEdit, QHeaderView, QAbstractItemView, QMessageBox
)
from PyQt5.QtCore import Qt

from core.adb_core import AdbCore


class DevicePanel(QWidget):

    def __init__(self, device_manager, adb_core, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.adb_core = adb_core
        self.current_serial = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        toolbar_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新设备列表")
        self.btn_connect = QPushButton("连接")
        toolbar_layout.addWidget(self.btn_refresh)
        toolbar_layout.addWidget(self.btn_connect)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        self.device_table = QTableWidget(0, 3)
        self.device_table.setHorizontalHeaderLabels(["序号", "设备序列号", "状态"])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.device_table)

        self.lbl_current_device = QLabel("当前设备: 无")
        layout.addWidget(self.lbl_current_device)

        cmd_layout = QHBoxLayout()
        self.txt_command = QLineEdit()
        self.txt_command.setPlaceholderText("输入自定义ADB shell命令（不带adb前缀）")
        self.btn_execute = QPushButton("执行")
        cmd_layout.addWidget(self.txt_command)
        cmd_layout.addWidget(self.btn_execute)
        layout.addLayout(cmd_layout)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        layout.addWidget(self.txt_output)

        self.btn_refresh.clicked.connect(self.refresh_devices)
        self.btn_connect.clicked.connect(self.connect_device)
        self.btn_execute.clicked.connect(self.execute_custom_command)
        self.device_table.cellClicked.connect(self._on_device_selected)

    def _connect_signals(self):
        self.device_manager.device_connected.connect(self._on_device_connected)
        self.device_manager.device_disconnected.connect(self._on_device_disconnected)
        self.device_manager.device_changed.connect(self._on_device_changed)

    def refresh_devices(self):
        devices = self.device_manager.refresh_device_list()
        self._update_device_table(devices)

    def connect_device(self):
        row = self.device_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在列表中选择一个设备")
            return
        serial_item = self.device_table.item(row, 1)
        if serial_item is None:
            return
        serial = serial_item.text()
        success = self.device_manager.select_device(serial)
        if success:
            self.current_serial = serial
            self._on_device_changed(serial)
            resolution = self.device_manager.get_device_resolution()
            if resolution:
                self.txt_output.setText("已连接: {} (分辨率: {}x{})".format(
                    serial, resolution[0], resolution[1]))
            else:
                self.txt_output.setText("已连接: {}".format(serial))
        else:
            self.txt_output.setText("连接失败: 设备 {} 不可用".format(serial))

    def execute_custom_command(self):
        command = self.txt_command.text().strip()
        if not command:
            return
        if not self.current_serial:
            self.txt_output.setText("未连接设备，请先连接设备")
            return
        try:
            output = self.adb_core.shell(command, device=self.current_serial)
            self.txt_output.setText(output if output else "(命令执行成功，无输出)")
        except Exception as e:
            self.txt_output.setText("执行失败: {}".format(str(e)))

    def _update_device_table(self, devices):
        self.device_table.setRowCount(0)
        for index, serial in enumerate(devices):
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)
            self.device_table.setItem(row, 0, QTableWidgetItem(str(index + 1)))
            self.device_table.setItem(row, 1, QTableWidgetItem(serial))
            self.device_table.setItem(row, 2, QTableWidgetItem("在线"))

    def _on_device_selected(self, row, col):
        serial_item = self.device_table.item(row, 1)
        if serial_item is None:
            return
        self.device_table.selectRow(row)

    def _on_device_changed(self, serial):
        self.current_serial = serial
        self.lbl_current_device.setText("当前设备: {}".format(serial))

    def _on_device_connected(self, serial):
        self.refresh_devices()

    def _on_device_disconnected(self, serial):
        if self.current_serial == serial:
            self.current_serial = None
            self.lbl_current_device.setText("当前设备: 无")
        self.refresh_devices()
