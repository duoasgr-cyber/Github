import logging
from typing import Optional, List, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from core.adb_core import AdbCore, _adb

logger = logging.getLogger(__name__)


class DeviceManager(QObject):
    device_connected = pyqtSignal(str)
    device_disconnected = pyqtSignal(str)
    device_changed = pyqtSignal(str)
    connection_status_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_device: Optional[str] = None
        self._adb: AdbCore = _adb
        self._monitor_timer: QTimer = QTimer(self)
        self._monitor_timer.timeout.connect(self._on_monitor_timeout)
        self._connected: bool = False

    def refresh_device_list(self) -> List[str]:
        devices = self._adb.get_device_list()
        logger.debug("刷新设备列表: %s", devices)
        return devices

    def select_device(self, serial: str) -> bool:
        devices = self.refresh_device_list()
        if serial not in devices:
            logger.warning("选择设备失败，设备不在列表中: %s", serial)
            return False

        self._current_device = serial
        self._adb.set_device(serial)
        self._connected = True
        self.device_changed.emit(serial)
        self.connection_status_changed.emit(True)
        logger.info("已选择设备: %s", serial)
        return True

    def get_current_device(self) -> Optional[str]:
        return self._current_device

    def get_device_resolution(self) -> Optional[Tuple[int, int]]:
        if not self._current_device:
            logger.warning("未选择设备，无法获取分辨率")
            return None
        resolution = self._adb.get_device_resolution()
        if resolution == (0, 0):
            logger.warning("获取设备分辨率失败: %s", self._current_device)
            return None
        return resolution

    def check_connection(self) -> bool:
        if not self._current_device:
            return False
        devices = self.refresh_device_list()
        connected = self._current_device in devices
        if connected != self._connected:
            self._connected = connected
            if connected:
                self.device_connected.emit(self._current_device)
                self.connection_status_changed.emit(True)
                logger.info("设备已重新连接: %s", self._current_device)
            else:
                self.device_disconnected.emit(self._current_device)
                self.connection_status_changed.emit(False)
                logger.warning("设备已断开: %s", self._current_device)
        return connected

    def start_monitoring(self, interval: float = 5.0) -> None:
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
        self._monitor_timer.start(int(interval * 1000))
        logger.info("开始监控设备连接，间隔: %.1f秒", interval)

    def stop_monitoring(self) -> None:
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
            logger.info("停止监控设备连接")

    def _on_monitor_timeout(self) -> None:
        self.check_connection()
