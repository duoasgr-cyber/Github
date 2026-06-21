import subprocess
import logging
import re
import shlex
import os
import sys
from typing import Optional, List, Tuple

# Windows 下隐藏子进程控制台窗口
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# STARTUPINFO: 双重保障，防止 Windows 上子进程闪现控制台窗口
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    _STARTUPINFO = None

logger = logging.getLogger(__name__)


class AdbError(Exception):
    pass


# --- 安全：输入验证 ---
_PACKAGE_PATTERN = re.compile(r'^[a-zA-Z0-9._]+$')
_KEYEVENT_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
_SHELL_META_PATTERN = re.compile(r'[;&|$(){}!#`]')


def _validate_package(package: str) -> bool:
    """验证 Android 包名是否安全。"""
    if not package or not _PACKAGE_PATTERN.match(package):
        logger.error("非法包名: %s", package)
        return False
    return True


def _validate_keyevent(key: str) -> bool:
    """验证 keyevent 名称是否安全。"""
    if not key or not _KEYEVENT_PATTERN.match(str(key)):
        logger.error("非法 keyevent: %s", key)
        return False
    return True


def _validate_path(path: str) -> bool:
    """验证路径中不包含 shell 元字符。"""
    if not path or _SHELL_META_PATTERN.search(path):
        logger.error("非法路径 (含 shell 元字符): %s", path)
        return False
    return True


class AdbCore:
    def __init__(self):
        self._device: Optional[str] = None

    def set_device(self, serial: str) -> None:
        self._device = serial
        logger.debug("设备已设置: %s", serial)

    def get_device(self) -> Optional[str]:
        return self._device

    def execute(self, args: list, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
        """执行 ADB 命令（参数列表形式，shell=False）。

        Args:
            args: ADB 子命令参数列表，如 ["shell", "input", "tap", "100", "200"]
            timeout: 超时秒数
            device: 设备序列号（覆盖默认值）
        """
        serial = device or self._device
        cmd = ["adb"]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)

        cmd_str = " ".join(cmd)
        logger.debug("执行命令: %s", cmd_str)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            logger.debug("命令结果 - returncode=%d, stdout=%s, stderr=%s",
                         result.returncode, result.stdout.strip(), result.stderr.strip())

            if result.returncode != 0:
                raise AdbError(f"ADB命令失败: {cmd_str}\nstderr: {result.stderr.strip()}")

            return result
        except subprocess.TimeoutExpired as e:
            logger.error("命令超时: %s (%.1fs)", cmd_str, timeout)
            raise AdbError(f"ADB命令超时: {cmd_str}") from e
        except subprocess.CalledProcessError as e:
            logger.error("命令执行错误: %s - %s", cmd_str, e)
            raise AdbError(f"ADB命令执行错误: {cmd_str}") from e

    def execute_legacy(self, command: str, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
        """旧接口兼容层：接受字符串命令，内部拆分为列表调用 execute()。"""
        logger.warning("execute_legacy() 已废弃，请迁移到 execute(list) 接口")
        args = shlex.split(command)
        return self.execute(args, timeout=timeout, device=device)

    def tap(self, x: int, y: int, device: str = None) -> bool:
        try:
            self.execute(["shell", "input", "tap", str(x), str(y)], device=device)
            return True
        except AdbError:
            logger.error("点击失败: (%d, %d)", x, y)
            return False

    def long_press(self, x: int, y: int, duration: float = 1000, device: str = None) -> bool:
        try:
            self.execute(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(int(duration))], device=device)
            return True
        except AdbError:
            logger.error("长按失败: (%d, %d) duration=%.0f", x, y, duration)
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 300, device: str = None) -> bool:
        try:
            self.execute(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(int(duration))], device=device)
            return True
        except AdbError:
            logger.error("滑动失败: (%d,%d) -> (%d,%d)", x1, y1, x2, y2)
            return False

    def keyevent(self, key: str, device: str = None) -> bool:
        if not _validate_keyevent(key):
            return False
        try:
            self.execute(["shell", "input", "keyevent", str(key)], device=device)
            return True
        except AdbError:
            logger.error("按键事件失败: %s", key)
            return False

    # ADB input text 需要转义的字符
    _INPUT_TEXT_SPECIAL = re.compile(r'[&;|`$(){}<>\\!#*?~"\']')

    def input_text(self, text: str, device: str = None) -> bool:
        if not text:
            return False
        # 检查是否包含危险 shell 元字符
        if self._INPUT_TEXT_SPECIAL.search(text):
            logger.error("输入文本包含危险字符，已拒绝: %s", text[:50])
            return False
        # ADB input text 用 %s 表示空格
        safe_text = text.replace(' ', '%s')
        try:
            self.execute(["shell", "input", "text", safe_text], device=device)
            return True
        except AdbError:
            logger.error("文本输入失败: %s", text[:50])
            return False

    def screenshot(self, remote_path: str, device: str = None) -> bool:
        if not _validate_path(remote_path):
            return False
        try:
            self.execute(["shell", "screencap", "-p", str(remote_path)], device=device)
            return True
        except AdbError:
            logger.error("截图失败: %s", remote_path)
            return False

    def pull_file(self, remote: str, local: str, device: str = None) -> bool:
        if not _validate_path(remote) or not _validate_path(local):
            return False
        try:
            self.execute(["pull", str(remote), str(local)], device=device)
            return True
        except AdbError:
            logger.error("拉取文件失败: %s -> %s", remote, local)
            return False

    def push_file(self, local: str, remote: str, device: str = None) -> bool:
        if not _validate_path(local) or not _validate_path(remote):
            return False
        try:
            self.execute(["push", str(local), str(remote)], device=device)
            return True
        except AdbError:
            logger.error("推送文件失败: %s -> %s", local, remote)
            return False

    def delete_file(self, path: str, device: str = None) -> bool:
        if not _validate_path(path):
            return False
        try:
            self.execute(["shell", "rm", str(path)], device=device)
            return True
        except AdbError:
            logger.error("删除文件失败: %s", path)
            return False

    def shell(self, cmd: str, device: str = None, timeout: float = 30.0) -> str:
        """执行 shell 命令。cmd 会被 shlex.split() 拆分为参数列表。"""
        try:
            args = ["shell"] + shlex.split(cmd)
            result = self.execute(args, timeout=timeout, device=device)
            return result.stdout.strip()
        except ValueError as e:
            logger.error("Shell命令解析失败: %s - %s", cmd, e)
            return ""
        except AdbError:
            logger.error("Shell命令失败: %s", cmd)
            return ""

    def wifi_enable(self, device: str = None) -> bool:
        try:
            self.execute(["shell", "svc", "wifi", "enable"], device=device)
            return True
        except AdbError:
            logger.error("启用WiFi失败")
            return False

    def wifi_disable(self, device: str = None) -> bool:
        try:
            self.execute(["shell", "svc", "wifi", "disable"], device=device)
            return True
        except AdbError:
            logger.error("禁用WiFi失败")
            return False

    def force_stop(self, package: str, device: str = None) -> bool:
        if not _validate_package(package):
            return False
        try:
            self.execute(["shell", "am", "force-stop", str(package)], device=device)
            return True
        except AdbError:
            logger.error("强制停止应用失败: %s", package)
            return False

    def launch(self, package: str, device: str = None) -> bool:
        if not _validate_package(package):
            return False
        try:
            self.execute(["shell", "monkey", "-p", str(package),
                          "-c", "android.intent.category.LAUNCHER", "1"], device=device)
            return True
        except AdbError:
            logger.error("启动应用失败: %s", package)
            return False

    def get_device_list(self) -> List[str]:
        try:
            result = self.execute(["devices"], timeout=10.0)
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
            result = self.execute(["shell", "wm", "size"], device=device)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
            logger.error("无法解析分辨率: %s", result.stdout)
            return (0, 0)
        except AdbError:
            logger.error("获取设备分辨率失败")
            return (0, 0)

    def push_and_start_scrcpy(self, server_path: str, device: str = None) -> subprocess.Popen:
        """推送并启动 scrcpy server（已废弃，推荐使用 ScrcpyCapture.start()）。"""
        import warnings
        warnings.warn("push_and_start_scrcpy() 已废弃，请使用 ScrcpyCapture.start()", DeprecationWarning, stacklevel=2)
        serial = device or self._device
        try:
            self.execute(["push", server_path, "/data/local/tmp/scrcpy-server.jar"], device=serial)
        except AdbError:
            logger.error("推送scrcpy-server失败")
            raise

        cmd_parts = ["adb"]
        if serial:
            cmd_parts.extend(["-s", serial])
        cmd_parts.extend([
            "shell",
            "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            "2.0",
            "log_level=info",
            "max_size=1920",
            "max_fps=60",
            "tunnel_forward=true",
            "control=false",
            "cleanup=true"
        ])

        logger.debug("启动scrcpy服务: %s", " ".join(cmd_parts))
        try:
            proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )
            return proc
        except Exception as e:
            logger.error("启动scrcpy进程失败: %s", e)
            raise


_adb = AdbCore()


def execute(command, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
    """模块级便捷 execute：接受 list 或 str（str 时自动拆分）。"""
    if isinstance(command, list):
        return _adb.execute(command, timeout=timeout, device=device)
    else:
        return _adb.execute_legacy(command, timeout=timeout, device=device)


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
