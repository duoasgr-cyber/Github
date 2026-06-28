"""双模式屏幕采集：scrcpy 高速采集 + screencap 回退。

主链路：scrcpy-server.jar → H.264 流 → PyAV 进程内解码 → RGB numpy 帧
回退：adb exec-out screencap -p → PNG 解码 → numpy 帧

验收标准见 docs/cast-acceptance.md。
"""

import logging
import os
import re
import select
import socket
import struct
import subprocess
import sys
import threading
import time
import zipfile
from typing import Optional

import av
import cv2
import numpy as np
from av.codec import CodecContext
from av.error import InvalidDataError
from PyQt5.QtCore import QObject, pyqtSignal

if sys.platform == "win32":
    import ctypes
    import msvcrt

logger = logging.getLogger(__name__)

# Windows 下隐藏子进程控制台窗口
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# STARTUPINFO: 双重保障，防止 Windows 上子进程闪现控制台窗口
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    _STARTUPINFO = None

# 项目根目录（core/ 的上一级）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 默认 scrcpy-server.jar 路径
_DEFAULT_SERVER_JAR = os.path.join(_PROJECT_ROOT, "lib", "scrcpy-server.jar")

# scrcpy 连接参数
_SCRCPY_DEFAULT_PORT = 27183
_SCRCPY_SOCKET_TIMEOUT = 5.0
_SCRCPY_CONNECT_TIMEOUT = 3.0
_SCRCPY_CONNECT_RETRY_INTERVAL = 0.2


def _detect_scrcpy_version() -> str:
    """动态检测 scrcpy 版本号。

    优先级：
    1. 项目自带的 scrcpy 客户端（lib/scrcpy-win64/scrcpy.exe）
    2. 系统 PATH 中的 scrcpy
    3. 兜底返回 "4.0"（适配 scrcpy 4.0）

    Returns:
        版本号字符串，如 "4.0"、"4.0.0"；检测失败返回 "4.0" 作为兜底。
    """
    # 按优先级尝试多个 scrcpy 客户端路径
    candidates = [
        os.path.join(_PROJECT_ROOT, "lib", "scrcpy-win64", "scrcpy.exe"),  # 项目自带（首选）
        "scrcpy",  # 系统 PATH
    ]
    for exe_path in candidates:
        try:
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO,
            )
            # 输出格式: "scrcpy 4.0 <https://...>"
            if result.returncode == 0 and result.stdout:
                version_match = result.stdout.split()[1]
                if version_match[0].isdigit():
                    logger.debug("检测到 scrcpy 客户端版本 (%s): %s", exe_path, version_match)
                    return version_match
        except Exception as e:
            logger.debug("检测 %s 失败: %s", exe_path, e)
            continue
    logger.debug("未检测到 scrcpy 客户端，使用兜底版本 4.0")
    return "4.0"


def _detect_server_jar_version(jar_path: str) -> Optional[str]:
    """从 scrcpy-server.jar 内部提取版本号。

    scrcpy server JAR 的 classes.dex 中嵌入了版本字符串，
    但无法直接从 ZIP 层面读取。此处依次尝试从 MANIFEST.MF、
    资源文件和 .dex 文件中提取，若均失败则返回 None。

    Args:
        jar_path: scrcpy-server.jar 文件路径

    Returns:
        版本号字符串（如 "3.3.4"），或 None
    """
    if not os.path.isfile(jar_path):
        return None
    try:
        with zipfile.ZipFile(jar_path, "r") as zf:
            namelist = zf.namelist()
            # 尝试读取 MANIFEST.MF
            for name in namelist:
                if name.endswith("MANIFEST.MF"):
                    content = zf.read(name).decode("utf-8", errors="replace")
                    for line in content.splitlines():
                        if "Implementation-Version" in line or "Bundle-Version" in line:
                            version = line.split(":")[-1].strip()
                            if version and version[0].isdigit():
                                logger.debug("从 MANIFEST.MF 检测到版本: %s", version)
                                return version
            # 尝试读取包含 version 的资源文件
            for name in namelist:
                if "version" in name.lower() and not name.endswith("/"):
                    content = zf.read(name).decode("utf-8", errors="replace").strip()
                    # 匹配语义化版本号 (如 3.3.4)
                    match = re.search(r"\d+\.\d+", content)
                    if match:
                        version = match.group(0)
                        logger.debug("从资源文件 %s 检测到版本: %s", name, version)
                        return version
            # 尝试从 .dex 文件中搜索版本号
            # 注意：.dex 中包含大量第三方库版本（如 AndroidX 1.9.0、Gradle 8.x 等），
            # 必须过滤掉这些干扰项，只匹配 scrcpy 自身版本格式
            for name in namelist:
                if name.endswith(".dex"):
                    content = zf.read(name).decode("utf-8", errors="replace")
                    matches = re.findall(r"\b(\d\.\d+(?:\.\d+)?)\b", content)
                    for version in matches:
                        major = int(version.split(".")[0])
                        # scrcpy 版本特征：主版本在 2~5 范围内（当前为 4.0）
                        # 排除库版本：1.x (AndroidX)、8.x/9.x (AGP/Gradle)、27+/28+ (SDK)
                        if 2 <= major <= 5:
                            logger.debug("从 dex 文件 %s 检测到版本: %s", name, version)
                            return version
    except Exception as e:
        logger.debug("从 JAR 检测版本失败: %s", e)
    return None


def _parse_major_version(version: str) -> int:
    """从版本字符串提取主版本号。

    Args:
        version: 版本字符串，如 "4.0.0"、"3.3.4" 或 "2.0"

    Returns:
        主版本号整数，如 4、3 或 2。解析失败返回 4（默认假设 4.0）。
    """
    try:
        major = int(version.split(".")[0])
        if major < 2:
            return 2  # 最小支持 2.x
        return major
    except (ValueError, IndexError):
        return 4  # 默认假设 4.0


_SCRCPY_VERSION = None


def _get_scrcpy_version() -> str:
    """延迟获取 scrcpy 版本号，避免模块导入时执行子进程。"""
    global _SCRCPY_VERSION
    if _SCRCPY_VERSION is None:
        _SCRCPY_VERSION = _detect_scrcpy_version()
    return _SCRCPY_VERSION


# screencap 回退采集间隔（秒）
_SCREENCAP_INTERVAL = 0.2


class ScrcpyCapture(QObject):
    """双模式屏幕采集：scrcpy 高速 + screencap 回退。

    Signals:
        frame_captured(np.ndarray): 每帧画面（RGB 格式）
        connection_lost(): 连接断开
        connection_restored(): 连接恢复
        error_occurred(str): 错误信息
    """

    frame_captured = pyqtSignal(object)  # np.ndarray (RGB)
    frame_ready = pyqtSignal()  # 新帧就绪通知（无参数，UI 通过版本号拉取，替代轮询）
    connection_lost = pyqtSignal()
    connection_restored = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._connected = False
        self._lock = threading.Lock()

        # 当前帧缓存
        self._current_frame: Optional[np.ndarray] = None

        # 帧版本号（每次 set_current_frame 递增，UI 用此判断是否有新帧）
        self._frame_version: int = 0

        # 设备分辨率（从 scrcpy 头部解析，用于 rawvideo 帧计算）
        self._frame_width: int = 0
        self._frame_height: int = 0

        # 设备信息
        self._serial: str = ""
        self._server_jar: str = ""
        self._max_retries: int = 3

        # 子进程 / 连接
        self._server_process: Optional[subprocess.Popen] = None
        self._video_socket: Optional[socket.socket] = None
        self._local_port: int = 0

        # 采集线程
        self._capture_thread: Optional[threading.Thread] = None

        # 连接状态跟踪
        self._was_connected: bool = False

    # ===================================================================
    #  公开接口
    # ===================================================================

    def start(self, serial: str = "", server_jar_path: str = None, max_retries: int = 3):
        """启动屏幕采集。

        Args:
            serial: 设备序列号（空则使用 adb 默认设备）
            server_jar_path: scrcpy-server.jar 路径（None 用默认值）
            max_retries: scrcpy 失败后的最大重试次数
        """
        if self._running:
            logger.warning("屏幕采集已在运行，先停止再重启")
            self.stop()

        self._serial = serial
        self._server_jar = server_jar_path or _DEFAULT_SERVER_JAR
        self._max_retries = max_retries
        self._running = True

        # 在后台线程中启动采集，避免阻塞 UI
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="screen-capture")
        self._capture_thread.start()

        logger.info("屏幕采集启动: serial=%s, jar=%s", serial or "(default)", self._server_jar)

    def stop(self):
        """停止屏幕采集，清理所有资源。"""
        self._running = False

        # 等待采集线程退出（最多 3 秒）
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)
            self._capture_thread = None

        self._cleanup_scrcpy()
        self._cleanup_screencap()

        with self._lock:
            self._connected = False
            self._current_frame = None

        logger.info("屏幕采集已停止")

    def is_running(self) -> bool:
        return self._running

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def get_current_frame(self) -> Optional[np.ndarray]:
        """返回最新帧的拷贝；未连接时返回 None。"""
        with self._lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None

    def get_frame_version(self) -> int:
        """返回当前帧版本号。每次 set_current_frame 递增。"""
        with self._lock:
            return self._frame_version

    def get_current_frame_if_new(self, last_version: int) -> Optional[tuple]:
        """如果帧版本号大于 last_version，返回 (帧引用, 新版本号)；否则返回 None。

        UI 用此方法避免重复渲染同一帧。

        性能优化：返回内部缓存的引用而非拷贝。
        采集线程每次 to_ndarray() 生成新数组，永不修改旧数组；
        UI 线程只读不写（QImage 仅读取 data 指针），因此直接返回引用是安全的。
        消除 1080×2400 RGB 帧 ~7.4MB/帧 的内存拷贝。
        """
        with self._lock:
            if self._frame_version > last_version and self._current_frame is not None:
                return (self._current_frame, self._frame_version)
            return None

    def capture_screenshot(self) -> Optional[np.ndarray]:
        """兼容接口：返回当前帧。"""
        if not self.is_connected():
            return None
        return self.get_current_frame()

    def set_current_frame(self, frame: np.ndarray):
        """由采集后端调用，缓存最新帧。

        缓存帧后 emit frame_ready 信号，UI 通过信号 + 版本号获取新帧，
        替代固定间隔轮询，将显示唤醒延迟从 0~8ms 降到 ~0ms。
        信号队列不会堆积：UI slot 用版本号跳过已渲染帧。
        """
        with self._lock:
            self._current_frame = frame
            self._frame_version += 1
        # 通知 UI 有新帧（信号驱动，零延迟通知）
        try:
            self.frame_ready.emit()
        except RuntimeError:
            pass  # 信号已断开（UI 关闭等）

    def set_device(self, serial: str):
        """切换到不同设备。"""
        was_running = self._running
        if was_running:
            self.stop()
        if was_running:
            self.start(serial)

    # ===================================================================
    #  采集主循环（后台线程）
    # ===================================================================

    def _capture_loop(self):
        """采集主循环：先尝试 scrcpy，失败则回退到 screencap。"""
        retry_count = 0

        while self._running:
            # 1. 尝试 scrcpy 模式
            if self._try_start_scrcpy():
                logger.info("scrcpy 模式启动成功")
                self._set_connected(True)
                self._scrcpy_read_loop()
                # 从 scrcpy 循环退出说明连接断开
                self._cleanup_scrcpy()
                if not self._running:
                    break
                # 断连处理
                self._set_connected(False)
                retry_count += 1
                if retry_count <= self._max_retries:
                    wait_time = min(retry_count * 1.0, 5.0)
                    logger.warning("scrcpy 连接断开，%0.1fs 后重试 (%d/%d)", wait_time, retry_count, self._max_retries)
                    if not self._interruptible_sleep(wait_time):
                        break
                    continue
                else:
                    logger.warning(
                        "scrcpy 重试次数耗尽 (%d)，回退到 screencap 模式（低帧率截图模式，约 5fps，投屏可能卡顿）",
                        self._max_retries,
                    )
            else:
                logger.warning("scrcpy 启动失败，回退到 screencap 模式（低帧率截图模式，约 5fps，投屏可能卡顿）")

            # 2. screencap 回退模式
            self._cleanup_scrcpy()
            self._set_connected(True)
            self._screencap_loop()
            self._set_connected(False)

            # screencap 退出后不再自动重试（除非外部再次调用 start）
            break

    # ===================================================================
    #  Scrcpy 模式
    # ===================================================================

    def _try_start_scrcpy(self) -> bool:
        """尝试启动 scrcpy server 并建立连接。返回是否成功。"""
        # 检查 JAR 文件
        if not os.path.isfile(self._server_jar):
            logger.warning("scrcpy-server.jar 不存在: %s", self._server_jar)
            return False

        try:
            # 0. 确定传给 server 的版本参数
            # 策略：始终以客户端版本为准（因为 client 和 server 来自同一发布包，版本必须一致）
            # JAR 内部版本检测仅作参考日志（4.0 的 JAR 中版本号嵌入方式不可靠）
            client_version = _get_scrcpy_version()
            jar_detected_version = _detect_server_jar_version(self._server_jar)

            if jar_detected_version:
                jar_major = _parse_major_version(jar_detected_version)
                client_major = _parse_major_version(client_version)
                # 如果 JAR 检测到的版本与客户端不一致，记录警告但不影响运行
                if jar_major != client_major or jar_major > 5:
                    logger.warning(
                        "JAR 版本检测 (%s, major=%d) 与客户端 (%s, major=%d) 不一致或异常，"
                        "将以客户端版本 %s 作为 server 参数",
                        jar_detected_version, jar_major,
                        client_version, client_major,
                        client_version,
                    )
                else:
                    logger.info("从 JAR 检测到 scrcpy server 版本: %s", jar_detected_version)

            server_version = client_version
            logger.info("使用客户端版本作为 server 版本参数: %s", server_version)

            # 0.1 版本兼容性检查
            self._validate_version_compatibility(client_version, server_version)

            # 1. 杀死设备上残留的 scrcpy server 进程
            self._kill_existing_server()

            # 2. 推送 server JAR 到设备
            push_cmd = ["adb"]
            if self._serial:
                push_cmd += ["-s", self._serial]
            push_cmd += ["push", self._server_jar, "/data/local/tmp/scrcpy-server.jar"]
            result = subprocess.run(
                push_cmd, capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
            )
            if result.returncode != 0:
                logger.error("推送 scrcpy-server 失败: %s", result.stderr.strip())
                return False
            logger.info("scrcpy-server.jar 推送成功")

            # 3. 启动 scrcpy server 子进程（先启动 server，再设置转发）
            self._start_server_process(server_version)
            if self._server_process is None:
                return False

            # 4. 设置端口转发（server 启动后设置，确保 localabstract socket 已就绪）
            self._local_port = _SCRCPY_DEFAULT_PORT
            self._setup_adb_forward()

            # 5. 连接 socket（等待 server 就绪）
            self._video_socket = self._connect_socket()
            if self._video_socket is None:
                logger.error("无法连接 scrcpy socket")
                self._log_server_stderr()
                self._cleanup_scrcpy()
                return False

            # 6. 自适应读取协议头部（兼容 2.x / 3.x / 4.x）
            if not self._read_scrcpy_header(server_version):
                self._log_server_stderr()
                self._cleanup_scrcpy()
                return False

            return True

        except Exception as e:
            logger.error("scrcpy 启动异常: %s", e)
            self._cleanup_scrcpy()
            return False

    def _kill_existing_server(self):
        """杀死设备上残留的 scrcpy server 进程，避免 socket 冲突。"""
        try:
            # 先尝试优雅停止
            kill_cmd = ["adb"]
            if self._serial:
                kill_cmd += ["-s", self._serial]
            kill_cmd += ["shell", "pkill", "-f", "scrcpy-server.jar"]
            subprocess.run(kill_cmd, capture_output=True, timeout=3, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO)
            # 等待进程完全退出（避免竞态）
            time.sleep(0.5)

            # 验证是否已退出，如果还在则强制杀死
            check_cmd = ["adb"]
            if self._serial:
                check_cmd += ["-s", self._serial]
            check_cmd += ["shell", "pidof", "com.genymobile.scrcpy.Server"]
            result = subprocess.run(
                check_cmd, capture_output=True, text=True, timeout=3, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
            )
            if result.stdout.strip():
                # 进程仍在运行，强制杀死
                force_cmd = ["adb"]
                if self._serial:
                    force_cmd += ["-s", self._serial]
                force_cmd += ["shell", "pkill", "-9", "-f", "scrcpy-server.jar"]
                subprocess.run(
                    force_cmd, capture_output=True, timeout=3, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
                )
                time.sleep(0.3)
                logger.debug("已强制清理设备上残留的 scrcpy server 进程")
            else:
                logger.debug("已清理设备上残留的 scrcpy server 进程")
        except Exception as e:
            logger.debug("清理残留 server 进程失败（可能不存在）: %s", e)

    def _setup_adb_forward(self):
        """设置 adb 端口转发。"""
        # 清理旧的端口转发，避免残留转发导致连接异常
        remove_cmd = ["adb"]
        if self._serial:
            remove_cmd += ["-s", self._serial]
        remove_cmd += ["forward", "--remove", f"tcp:{self._local_port}"]
        try:
            subprocess.run(
                remove_cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO,
            )
        except Exception:
            logger.debug("清理旧端口转发失败（可能不存在）")

        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += ["forward", f"tcp:{self._local_port}", f"localabstract:scrcpy"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
        )
        if result.returncode == 0:
            logger.info("端口转发设置成功: tcp:%d -> localabstract:scrcpy", self._local_port)
        else:
            logger.warning("端口转发 tcp:%d 失败: %s，尝试随机端口", self._local_port, result.stderr.strip())
            # 尝试不同的端口
            cmd_retry = ["adb"]
            if self._serial:
                cmd_retry += ["-s", self._serial]
            cmd_retry += ["forward", "tcp:0", "localabstract:scrcpy"]
            result = subprocess.run(
                cmd_retry, capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
            )
            if result.returncode == 0 and result.stdout.strip().isdigit():
                self._local_port = int(result.stdout.strip())
                logger.info("端口转发设置成功（随机端口）: tcp:%d", self._local_port)
            else:
                logger.error("所有端口转发尝试均失败")

    def _start_server_process(self, server_version: str = None):
        """启动 scrcpy server 子进程（支持 2.x / 3.x / 4.x 版本自适应）。

        Args:
            server_version: 传给 server 的版本字符串，None 则使用模块级检测值
        """
        version = server_version or _get_scrcpy_version()
        major = _parse_major_version(version)
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += [
            "shell",
            "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            version,
            "log_level=warn",
            # max_size=0 表示不缩放，frame 尺寸 == 设备真实分辨率。
            # 此前 max_size=1280 会把 1080x2400 缩成 576x1280，导致投屏点击
            # 坐标与设备响应位置不一致（wm size Override 与 scrcpy 采集的物理
            # 分辨率比例不一致时，比例补偿会失准）。取消限制后 frame 与设备
            # 1:1 对齐，坐标映射无需依赖比例补偿。
            "max_size=0",
            "max_fps=60",
            "video_bit_rate=4000000",
            "video_codec_options=latency=1,priority=0",
            "tunnel_forward=true",
            "control=false",
            "audio=false",
            "cleanup=false",
            "send_frame_meta=False",
        ]
        logger.info("启动 scrcpy server (version=%s, major=%d)", version, major)
        try:
            self._server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
            )
            # 给 server 启动时间（dex2oat 编译可能需要数秒）
            time.sleep(1.0)
            # 检查是否已退出
            if self._server_process.poll() is not None:
                stderr = b""
                try:
                    stderr = self._server_process.stderr.read()
                except Exception:
                    pass
                logger.error(
                    "scrcpy server 已退出 (code=%d): %s",
                    self._server_process.returncode,
                    stderr.decode(errors="replace")[:500],
                )
                self._server_process = None
                return
            logger.info("scrcpy server 进程已启动 (pid=%d)", self._server_process.pid)
        except Exception as e:
            logger.error("启动 scrcpy server 失败: %s", e)
            self._server_process = None

    def _connect_socket(self) -> Optional[socket.socket]:
        """连接到 scrcpy socket（带超时重试）。"""
        deadline = time.monotonic() + _SCRCPY_CONNECT_TIMEOUT
        attempt = 0
        while time.monotonic() < deadline:
            if not self._running:
                return None
            attempt += 1
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # 增大接收缓冲区，减少丢包和拷贝次数
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 0x400000)
                # 禁用 Nagle 算法，小包立即发送
                # scrcpy 帧头可能被 Nagle 缓存 ~20ms，禁用后降低传输延迟
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(_SCRCPY_SOCKET_TIMEOUT)
                sock.connect(("127.0.0.1", self._local_port))
                # 握手阶段保持超时保护，防止 server 不响应时无限阻塞
                sock.settimeout(_SCRCPY_SOCKET_TIMEOUT)
                logger.info("scrcpy socket 连接成功 (第 %d 次尝试): 127.0.0.1:%d",
                            attempt, self._local_port)
                return sock
            except (ConnectionRefusedError, OSError):
                try:
                    sock.close()
                except Exception:
                    pass
                time.sleep(_SCRCPY_CONNECT_RETRY_INTERVAL)
        logger.error("scrcpy socket 连接超时 (%d 次尝试)", attempt)
        return None

    def _read_exact(self, sock: socket.socket, n: int) -> Optional[bytes]:
        """从 socket 精确读取 n 字节。

        返回 None 时可通过日志区分原因：采集停止 / 连接关闭 / 超时 / socket 错误。
        """
        buf = bytearray()
        while len(buf) < n:
            if not self._running:
                logger.debug("_read_exact: 采集已停止 (已读 %d/%d 字节)", len(buf), n)
                return None
            try:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    logger.debug("_read_exact: 连接已关闭 (已读 %d/%d 字节)", len(buf), n)
                    return None
                buf.extend(chunk)
            except socket.timeout:
                logger.debug("_read_exact: 读取超时 (已读 %d/%d 字节)", len(buf), n)
                return None
            except OSError as e:
                logger.debug("_read_exact: socket 错误 %s (已读 %d/%d 字节)", e, len(buf), n)
                return None
        return bytes(buf)

    def _read_scrcpy_header(self, server_version: str) -> bool:
        """自适应读取 scrcpy 协议头部，兼容 2.x / 3.x / 4.x。

        scrcpy 协议头部格式：
        - 2.x: [1 byte dummy] [64 bytes device name] [4 bytes width] [4 bytes height]
        - 3.x: [1 byte dummy] [64 bytes device name] [4 bytes codec] [4 bytes width] [4 bytes height]
        - 4.x: 与 3.x 格式向后兼容（可能扩展额外字段）

        自适应策略：读取设备名后，先读 4 字节，根据数据特征判断协议版本：
        - codec id (FourCC) 通常 > 0x10000000（如 "h264" = 0x68323634）
        - width 通常 < 10000（移动设备分辨率）
        因此若前 4 字节 > 0x10000000 则为 3.x/4.x，否则为 2.x。

        Args:
            server_version: 检测到的 server 版本字符串（仅作日志参考）

        Returns:
            是否成功解析协议头部
        """
        sock = self._video_socket
        if sock is None:
            return False

        # 1. 读取 dummy byte（forward 模式下用于检测连接）
        dummy = self._read_exact(sock, 1)
        if dummy is None:
            # 诊断：检查 server 进程是否仍在运行
            if self._server_process and self._server_process.poll() is not None:
                logger.error("读取 scrcpy dummy byte 失败: server 已退出 (code=%d)", self._server_process.returncode)
            else:
                logger.error("读取 scrcpy dummy byte 失败: server 未发送数据" "（可能版本不匹配或设备端异常）")
            return False

        # 2. 读取 64 字节设备名
        device_name_bytes = self._read_exact(sock, 64)
        if device_name_bytes is None:
            logger.error("读取 scrcpy 设备名失败")
            return False

        device_name = device_name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")

        # 3. 读取前 4 字节，用于判断协议版本
        first_4_bytes = self._read_exact(sock, 4)
        if first_4_bytes is None:
            logger.error("读取 scrcpy 协议字段失败")
            return False

        first_val = struct.unpack(">I", first_4_bytes)[0]
        major_version = _parse_major_version(server_version)
        logger.debug("scrcpy 协议判断: first_4_bytes=0x%08x, major_version=%d, server_version=%s",
                     first_val, major_version, server_version)

        # 4. 根据数据特征和版本号判断协议格式
        if first_val > 0x10000000:
            # 3.x 或 4.x 协议: first_4_bytes = codec_id
            codec_id = first_val
            size_bytes = self._read_exact(sock, 8)
            if size_bytes is None:
                logger.error("读取 scrcpy 分辨率失败 (3.x/4.x 协议)")
                return False

            self._frame_width = struct.unpack(">I", size_bytes[0:4])[0]
            self._frame_height = struct.unpack(">I", size_bytes[4:8])[0]

            if self._frame_width == 0 or self._frame_height == 0:
                logger.error("scrcpy 分辨率无效 (3.x/4.x): %dx%d", self._frame_width, self._frame_height)
                return False

            version_label = "4.x" if major_version >= 4 else "3.x"
            logger.info(
                "scrcpy %s 协议: 设备=%s, codec=0x%08x, 分辨率=%dx%d",
                version_label, device_name, codec_id, self._frame_width, self._frame_height,
            )
        else:
            # 2.x 协议: first_4_bytes = width
            self._frame_width = first_val
            height_bytes = self._read_exact(sock, 4)
            if height_bytes is None:
                logger.error("读取 scrcpy 高度失败 (2.x 协议)")
                return False

            self._frame_height = struct.unpack(">I", height_bytes)[0]

            if self._frame_width == 0 or self._frame_height == 0:
                logger.error("scrcpy 分辨率无效 (2.x): %dx%d", self._frame_width, self._frame_height)
                return False

            logger.info("scrcpy 2.x 协议: 设备=%s, 分辨率=%dx%d", device_name, self._frame_width, self._frame_height)

        return True

    def _validate_version_compatibility(self, client_ver: str, server_ver: str) -> bool:
        """检测客户端与服务端版本兼容性。

        Args:
            client_ver: 客户端版本字符串
            server_ver: 服务端版本字符串

        Returns:
            是否兼容（True=兼容，False=可能存在兼容性问题）
        """
        client_major = _parse_major_version(client_ver)
        server_major = _parse_major_version(server_ver)

        if abs(client_major - server_major) > 1:
            logger.warning(
                "scrcpy 版本差距过大: client=%s (major=%d), server=%s (major=%d)，可能出现兼容性问题",
                client_ver, client_major, server_ver, server_major,
            )
            return False
        return True

    def _log_server_stderr(self):
        """读取并记录 scrcpy server 进程的 stderr 输出，用于诊断。"""
        if self._server_process is None:
            return
        try:
            # 如果 server 已退出，直接读取全部 stderr
            if self._server_process.poll() is not None:
                stderr_data = self._server_process.stderr.read()
                if stderr_data:
                    stderr_text = stderr_data.decode(errors="replace")[:1000]
                    logger.error("scrcpy server stderr: %s", stderr_text)
                return

            # server 仍在运行，用线程读取（避免阻塞）
            stderr_chunks = []

            def _read_stderr():
                try:
                    while True:
                        chunk = self._server_process.stderr.read(4096)
                        if not chunk:
                            break
                        stderr_chunks.append(chunk)
                except Exception:
                    pass

            reader = threading.Thread(target=_read_stderr, daemon=True)
            reader.start()
            reader.join(timeout=1.0)  # 最多等 1 秒

            if stderr_chunks:
                stderr_text = b"".join(stderr_chunks).decode(errors="replace")[:1000]
                logger.error("scrcpy server stderr: %s", stderr_text)
            else:
                logger.debug("scrcpy server stderr 为空（server 可能仍在运行）")
        except Exception as e:
            logger.debug("读取 server stderr 失败: %s", e)

    def _scrcpy_read_loop(self):
        """从 scrcpy socket 读取 H.264 数据 → PyAV 进程内解码 → RGB numpy 帧。

        使用 PyAV CodecContext 直接在 Python 进程内解码 H.264，
        跳过 ffmpeg 子进程和 pipe 开销，大幅降低延迟和 CPU 占用。

        帧跳过策略：当解码速度超过 UI 消费速度时，只保留最新帧，
        丢弃旧帧避免延迟累积。

        scrcpy 协议帧头格式（当 send_frame_meta=true 时）：
          byte7  byte6  byte5  byte4  byte3  byte2  byte1  byte0
          CK...... ........ ........ ........ ........ ........ ........
          ||<--------------------------------------------------->
          || PTS (62 bits)
          | `- key frame flag
           `-- config packet flag
          后跟 packet size (u32)，再跟原始 H.264 数据

        当 send_frame_meta=false 时，socket 中只包含裸 H.264 流。
        """
        if self._video_socket is None:
            return

        sock = self._video_socket

        # 增大 socket 接收缓冲区，减少丢包和内核态拷贝次数
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 0x400000)  # 4MB
        except OSError:
            pass
        sock.setblocking(False)

        # 创建 PyAV 解码器（支持 H.264 / H.265 / AV1 动态选择）
        # scrcpy 4.0 可能使用 H.265 或 AV1 编码，根据 codec_id 自动选择解码器
        try:
            codec = CodecContext.create("h264", "r")
        except Exception as e:
            logger.error("PyAV H.264 解码器创建失败: %s", e)
            return

        # 编解码器映射表（FourCC → 解码器名称），用于动态切换
        _CODEC_MAP = {
            0x68323634: "h264",  # "h264"
            0x68323635: "h265",  # "h265"
            0x61766331: "av1",   # "av1"
        }

        def _create_decoder_for_codec(codec_id: int) -> Optional[CodecContext]:
            """根据 codec FourCC 创建对应解码器（scrcpy 4.0+ 可能使用新编码格式）。

            Args:
                codec_id: 四字符编码标识符

            Returns:
                解码器实例，失败返回 None
            """
            codec_name = _CODEC_MAP.get(codec_id, "h264")
            if codec_name != "h264":
                logger.info("检测到非 H.264 编码 (codec_id=0x%08x)，尝试使用 %s 解码器", codec_id, codec_name)
            try:
                decoder = CodecContext.create(codec_name, "r")
                logger.info("PyAV %s 解码器创建成功 (codec_id=0x%08x)", codec_name, codec_id)
                return decoder
            except Exception as e:
                logger.warning("创建 %s 解码器失败: %s，回退到 H.264", codec_name, e)
                try:
                    return CodecContext.create("h264", "r")
                except Exception as e2:
                    logger.error("回退到 H.264 解码器也失败: %s", e2)
                    return None
        # 尝试启用硬件解码（DXVA2/D3D11VA），失败则回退到软件解码
        # 硬件解码将 H.264 解码工作卸载到 GPU，延迟从 ~10ms 降到 ~2ms
        # 解码结果完全相同，零画质损失
        hw_ctx = None
        try:
            hw_ctx = av.HWDeviceContext.create('dxva2')
            codec.hwaccel = hw_ctx
            logger.info("启用 DXVA2 硬件解码（GPU 加速）")
        except (AttributeError, Exception) as e:
            logger.debug("DXVA2 硬件解码不可用: %s，使用软件解码", e)
            hw_ctx = None

        # 单线程解码：消除帧重排序延迟
        # H.264 多线程帧级并行（FRAME threading）需要缓冲 2~4 帧才能并行，
        # 引入 33~66ms 重排序延迟（@60fps）。单线程解码无此延迟。
        # 1080p@60 软解单线程通常足够（~15ms/帧余量）。
        # 零画质损失，仅影响并行策略。
        codec.thread_count = 1

        # 启用低延迟解码，减少 FFmpeg 内部帧重排序缓冲
        try:
            codec.flags |= av.codec.Flags.LOW_DELAY
        except Exception as e:
            logger.warning("设置 LOW_DELAY 标志失败: %s", e)
        # 可选：进一步降低解码 CPU 占用
        try:
            codec.flags2 |= av.codec.Flags2.FAST
            codec.skip_loop_filter = "ALL"
        except Exception as e:
            logger.warning("设置 FAST/skip_loop_filter 失败: %s", e)

        hw_label = "DXVA2 硬解" if hw_ctx is not None else "软解"
        logger.info("PyAV 解码器已启动 (%s, 单线程, 低延迟, 支持 H.264/H.265/AV1)", hw_label)

        # 诊断变量
        loop_start_time = time.monotonic()
        first_frame_received = False
        recv_count = 0
        decode_count = 0

        try:
            while self._running:
                # 使用 select 等待数据可读，避免 busy-wait 空转
                # 超时 2ms（原 10ms），降低空闲时发现新数据的延迟
                try:
                    readable, _, _ = select.select([sock], [], [], 0.002)
                    if not readable:
                        continue
                except (OSError, ValueError):
                    break

                # 首帧超时告警
                if not first_frame_received and time.monotonic() - loop_start_time > 5.0:
                    logger.warning(
                        "scrcpy 已连接超过 5 秒但未收到任何视频帧 (已接收 %d 次数据, 已解码 %d 帧)",
                        recv_count, decode_count,
                    )
                    first_frame_received = True  # 只告警一次

                try:
                    raw_h264 = sock.recv(0x100000)  # 1MB 缓冲区（原 256KB），减少 syscall 次数
                    recv_count += 1
                    if recv_count <= 3 or recv_count % 100 == 0:
                        logger.debug("scrcpy 接收数据: %d 字节 (第 %d 次)", len(raw_h264), recv_count)
                    if not raw_h264:
                        logger.debug("scrcpy socket 关闭")
                        break
                except (BlockingIOError, OSError):
                    continue

                try:
                    # 解析 H.264 NAL 单元
                    packets = list(codec.parse(raw_h264))
                    if packets and decode_count == 0:
                        logger.info("scrcpy 首次解析到 %d 个 NAL packet", len(packets))
                    for packet in packets:
                        # 解码为视频帧
                        frames = list(codec.decode(packet))
                        if frames:
                            decode_count += 1
                            if decode_count <= 3 or decode_count % 100 == 0:
                                logger.debug("scrcpy 解码: %d 帧 (第 %d 次解码)", len(frames), decode_count)
                        # 帧跳过：只保留最后一个解码帧，丢弃中间帧
                        latest_frame = None
                        for frame in frames:
                            if frame is not None:
                                latest_frame = frame
                        if latest_frame is not None:
                            try:
                                # 硬件解码帧需要先从 GPU 转移到 CPU 内存
                                if hw_ctx is not None:
                                    try:
                                        latest_frame = latest_frame.transfer_to(0)
                                    except Exception:
                                        pass  # 可能已经是软件帧，直接使用
                                rgb_frame = latest_frame.reformat(format="rgb24").to_ndarray()
                                if not first_frame_received or decode_count == 1:
                                    logger.info(
                                        "scrcpy 首帧解码成功: shape=%s, dtype=%s",
                                        rgb_frame.shape, rgb_frame.dtype,
                                    )
                                    first_frame_received = True
                                self.set_current_frame(rgb_frame)
                            except Exception as e:
                                logger.error(
                                    "scrcpy 帧格式转换失败: %s (原始帧 format=%s, pts=%s)",
                                    e, latest_frame.format, latest_frame.pts,
                                )
                except InvalidDataError:
                    # 解码器尚未收到完整帧，正常现象
                    pass
                except Exception as e:
                    logger.warning(
                        "PyAV 解码异常: %s (已接收 %d 次, 已解码 %d 帧, 运行 %.1fs)",
                        e, recv_count, decode_count, time.monotonic() - loop_start_time,
                    )

        except (ConnectionError, OSError) as e:
            logger.debug("scrcpy 读取退出: %s", e)
        except Exception as e:
            logger.warning("scrcpy 读取异常: %s", e)

    def _cleanup_scrcpy(self):
        """清理 scrcpy 相关资源。"""
        # 关闭 socket
        if self._video_socket is not None:
            try:
                self._video_socket.close()
            except Exception:
                pass
            self._video_socket = None

        # 终止 server 进程
        if self._server_process is not None:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=3)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
            self._server_process = None

        # 清理端口转发
        if self._local_port > 0:
            try:
                cmd = ["adb"]
                if self._serial:
                    cmd += ["-s", self._serial]
                cmd += ["forward", "--remove", f"tcp:{self._local_port}"]
                subprocess.run(cmd, capture_output=True, timeout=5, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO)
            except Exception:
                pass
            self._local_port = 0

        logger.debug("scrcpy 资源已清理")

    # ===================================================================
    #  Screencap 回退模式
    # ===================================================================

    def _screencap_loop(self):
        """screencap 回退：周期性截屏获取帧。"""
        logger.info("screencap 回退模式启动 (间隔 %.1fs)", _SCREENCAP_INTERVAL)

        while self._running:
            frame = self._capture_screencap()
            if frame is not None:
                self.set_current_frame(frame)
            else:
                # 连续失败则断开
                logger.debug("screencap 获取帧失败")
                if not self._running:
                    break

            if not self._interruptible_sleep(_SCREENCAP_INTERVAL):
                break

        logger.info("screencap 回退模式结束")

    def _capture_screencap(self) -> Optional[np.ndarray]:
        """执行一次 screencap 截屏，返回 BGR numpy 数组。"""
        try:
            cmd = ["adb"]
            if self._serial:
                cmd += ["-s", self._serial]
            cmd += ["exec-out", "screencap", "-p"]

            result = subprocess.run(
                cmd, capture_output=True, timeout=10, creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO
            )
            if result.returncode != 0 or not result.stdout:
                return None

            # 解码 PNG
            img_array = np.frombuffer(result.stdout, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return frame

        except subprocess.TimeoutExpired:
            logger.debug("screencap 超时")
            return None
        except Exception as e:
            logger.debug("screencap 异常: %s", e)
            return None

    def _cleanup_screencap(self):
        """清理 screencap 相关资源（当前无需特殊清理）。"""
        pass

    # ===================================================================
    #  连接状态管理
    # ===================================================================

    def _set_connected(self, connected: bool):
        """更新连接状态并 emit 相应信号。"""
        with self._lock:
            old = self._connected
            self._connected = connected

        if connected and not old:
            logger.info("屏幕采集连接已建立")
            try:
                self.connection_restored.emit()
            except RuntimeError:
                pass
        elif not connected and old:
            logger.info("屏幕采集连接已断开")
            try:
                self.connection_lost.emit()
            except RuntimeError:
                pass

    # ===================================================================
    #  工具方法
    # ===================================================================

    def _interruptible_sleep(self, seconds: float) -> bool:
        """可中断的 sleep。返回 True 表示正常结束，False 表示被停止信号中断。"""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(min(0.1, end - time.monotonic()))
        return self._running
