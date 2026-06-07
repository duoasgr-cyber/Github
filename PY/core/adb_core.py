import subprocess
import logging
import re
import os
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class AdbError(Exception):
    pass


class AdbCore:
    def __init__(self):
        self._device: Optional[str] = None

    def set_device(self, serial: str) -> None:
        self._device = serial
        logger.debug("设备已设置: %s", serial)

    def get_device(self) -> Optional[str]:
        return self._device

    def execute(self, command: str, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
        serial = device or self._device
        if serial:
            full_cmd = f"adb -s {serial} {command}"
        else:
            full_cmd = f"adb {command}"

        logger.debug("执行命令: %s", full_cmd)

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=True
            )
            logger.debug("命令结果 - returncode=%d, stdout=%s, stderr=%s",
                         result.returncode, result.stdout.strip(), result.stderr.strip())

            if result.returncode != 0:
                raise AdbError(f"ADB命令失败: {full_cmd}\nstderr: {result.stderr.strip()}")

            return result
        except subprocess.TimeoutExpired as e:
            logger.error("命令超时: %s (%.1fs)", full_cmd, timeout)
            raise AdbError(f"ADB命令超时: {full_cmd}") from e
        except subprocess.CalledProcessError as e:
            logger.error("命令执行错误: %s - %s", full_cmd, e)
            raise AdbError(f"ADB命令执行错误: {full_cmd}") from e

    def tap(self, x: int, y: int, device: str = None) -> bool:
        try:
            self.execute(f"shell input tap {x} {y}", device=device)
            return True
        except AdbError:
            logger.error("点击失败: (%d, %d)", x, y)
            return False

    def long_press(self, x: int, y: int, duration: float = 1000, device: str = None) -> bool:
        try:
            self.execute(f"shell input swipe {x} {y} {x} {y} {int(duration)}", device=device)
            return True
        except AdbError:
            logger.error("长按失败: (%d, %d) duration=%.0f", x, y, duration)
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 300, device: str = None) -> bool:
        try:
            self.execute(f"shell input swipe {x1} {y1} {x2} {y2} {int(duration)}", device=device)
            return True
        except AdbError:
            logger.error("滑动失败: (%d,%d) -> (%d,%d)", x1, y1, x2, y2)
            return False

    def keyevent(self, key: str, device: str = None) -> bool:
        try:
            self.execute(f"shell input keyevent {key}", device=device)
            return True
        except AdbError:
            logger.error("按键事件失败: %s", key)
            return False

    def input_text(self, text: str, device: str = None) -> bool:
        try:
            self.execute(f"shell input text {text}", device=device)
            return True
        except AdbError:
            logger.error("文本输入失败: %s", text)
            return False

    def screenshot(self, remote_path: str, device: str = None) -> bool:
        try:
            self.execute(f"shell screencap -p {remote_path}", device=device)
            return True
        except AdbError:
            logger.error("截图失败: %s", remote_path)
            return False

    def pull_file(self, remote: str, local: str, device: str = None) -> bool:
        try:
            self.execute(f"pull {remote} {local}", device=device)
            return True
        except AdbError:
            logger.error("拉取文件失败: %s -> %s", remote, local)
            return False

    def push_file(self, local: str, remote: str, device: str = None) -> bool:
        try:
            self.execute(f"push {local} {remote}", device=device)
            return True
        except AdbError:
            logger.error("推送文件失败: %s -> %s", local, remote)
            return False

    def delete_file(self, path: str, device: str = None) -> bool:
        try:
            self.execute(f"shell rm {path}", device=device)
            return True
        except AdbError:
            logger.error("删除文件失败: %s", path)
            return False

    def shell(self, cmd: str, device: str = None, timeout: float = 30.0) -> str:
        try:
            result = self.execute(f"shell {cmd}", timeout=timeout, device=device)
            return result.stdout.strip()
        except AdbError:
            logger.error("Shell命令失败: %s", cmd)
            return ""

    def wifi_enable(self, device: str = None) -> bool:
        try:
            self.execute("shell svc wifi enable", device=device)
            return True
        except AdbError:
            logger.error("启用WiFi失败")
            return False

    def wifi_disable(self, device: str = None) -> bool:
        try:
            self.execute("shell svc wifi disable", device=device)
            return True
        except AdbError:
            logger.error("禁用WiFi失败")
            return False

    def force_stop(self, package: str, device: str = None) -> bool:
        try:
            self.execute(f"shell am force-stop {package}", device=device)
            return True
        except AdbError:
            logger.error("强制停止应用失败: %s", package)
            return False

    def launch(self, package: str, device: str = None) -> bool:
        try:
            self.execute(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1", device=device)
            return True
        except AdbError:
            logger.error("启动应用失败: %s", package)
            return False

    def get_device_list(self) -> List[str]:
        try:
            result = self.execute("devices", timeout=10.0)
            lines = result.stdout.strip().split('\n')
            devices = []
            for line in lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) == 2 and parts[1] == 'device':
                    devices.append(parts[0])
            return devices
        except AdbError:
            logger.error("获取设备列表失败")
            return []

    def get_device_resolution(self, device: str = None) -> Tuple[int, int]:
        try:
            result = self.execute("shell wm size", device=device)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
            logger.error("无法解析分辨率: %s", result.stdout)
            return (0, 0)
        except AdbError:
            logger.error("获取设备分辨率失败")
            return (0, 0)

    def push_and_start_scrcpy(self, server_path: str, device: str = None) -> subprocess.Popen:
        serial = device or self._device
        try:
            if serial:
                push_result = self.execute(f"push {server_path} /data/local/tmp/scrcpy-server.jar", device=serial)
            else:
                push_result = self.execute(f"push {server_path} /data/local/tmp/scrcpy-server.jar")

            cmd_parts = ["adb"]
            if serial:
                cmd_parts.extend(["-s", serial])
            cmd_parts.extend([
                "shell",
                "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
                "app_process",
                "/",
                "com.genymobile.scrcpy.Server",
                "1.25",
                "log_level=info",
                "max_size=1920",
                "max_fps=60",
                "tunnel_forward=true",
                "control=false",
                "cleanup=true"
            ])

            logger.debug("启动scrcpy服务: %s", " ".join(cmd_parts))
            proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return proc
        except AdbError:
            logger.error("推送并启动scrcpy失败")
            raise


_adb = AdbCore()


def execute(command: str, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
    return _adb.execute(command, timeout=timeout, device=device)


def tap(x: int, y: int, device: str = None) -> bool:
    return _adb.tap(x, y, device=device)


def long_press(x: int, y: int, duration: float = 1000, device: str = None) -> bool:
    return _adb.long_press(x, y, duration=duration, device=device)


def swipe(x1: int, y1: int, x2: int, y2: int, duration: float = 300, device: str = None) -> bool:
    return _adb.swipe(x1, y1, x2, y2, duration=duration, device=device)


def keyevent(key: str, device: str = None) -> bool:
    return _adb.keyevent(key, device=device)


def input_text(text: str, device: str = None) -> bool:
    return _adb.input_text(text, device=device)


def screenshot(remote_path: str, device: str = None) -> bool:
    return _adb.screenshot(remote_path, device=device)


def pull_file(remote: str, local: str, device: str = None) -> bool:
    return _adb.pull_file(remote, local, device=device)


def push_file(local: str, remote: str, device: str = None) -> bool:
    return _adb.push_file(local, remote, device=device)


def delete_file(path: str, device: str = None) -> bool:
    return _adb.delete_file(path, device=device)


def shell(cmd: str, device: str = None, timeout: float = 30.0) -> str:
    return _adb.shell(cmd, device=device, timeout=timeout)


def wifi_enable(device: str = None) -> bool:
    return _adb.wifi_enable(device=device)


def wifi_disable(device: str = None) -> bool:
    return _adb.wifi_disable(device=device)


def force_stop(package: str, device: str = None) -> bool:
    return _adb.force_stop(package, device=device)


def launch(package: str, device: str = None) -> bool:
    return _adb.launch(package, device=device)


def get_device_list() -> List[str]:
    return _adb.get_device_list()


def get_device_resolution(device: str = None) -> Tuple[int, int]:
    return _adb.get_device_resolution(device=device)


def push_and_start_scrcpy(server_path: str, device: str = None) -> subprocess.Popen:
    return _adb.push_and_start_scrcpy(server_path, device=device)


def set_device(serial: str) -> None:
    _adb.set_device(serial)


def get_device() -> Optional[str]:
    return _adb.get_device()
