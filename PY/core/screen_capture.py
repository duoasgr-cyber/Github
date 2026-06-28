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

try:
    import av as _av
    _HAS_PYAV = True
except ImportError:
    _av = None
    _HAS_PYAV = False


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

_SUPPORTED_CODECS = ("h264", "h265", "av1")


class CastOptions:
    """投屏启动参数（与 config.json 的 device.cast 对应）。

    保持向后兼容：所有字段均有默认值，与 P1 之前的行为一致。
    """

    def __init__(
        self,
        server_version: str = "2.0",
        video_codec: str = "h264",
        bit_rate: int = 2000000,
        max_size: int = 1080,
        max_fps: int = 30,
        startup_wait: float = _SERVER_STARTUP_WAIT,
        skip_push_if_exists: bool = True,
    ):
        self.server_version = server_version
        self.video_codec = video_codec if video_codec in _SUPPORTED_CODECS else "h264"
        self.bit_rate = int(bit_rate)
        self.max_size = int(max_size)
        self.max_fps = int(max_fps)
        self.startup_wait = float(startup_wait)
        self.skip_push_if_exists = bool(skip_push_if_exists)


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
        self._device_serial: Optional[str] = None
        self._server_jar_path: Optional[str] = None
        self._connected: bool = False
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._cleanup_lock = threading.Lock()
        self._server_process: Optional[subprocess.Popen] = None
        self._socket: Optional[socket.socket] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._decoder_thread: Optional[threading.Thread] = None
        self._fallback_thread: Optional[threading.Thread] = None
        self._forward_port: int = _DEFAULT_FORWARD_PORT
        self._stopping: bool = False
        self._reconnect_count: int = 0
        self._max_reconnect: int = 3
        self._last_emit_time: float = 0.0
        self._generation: int = 0
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._cast_options: CastOptions = CastOptions()
        self._use_pyav: bool = _HAS_PYAV
        self._av_codec = None

    def start(
        self,
        device_serial: str,
        server_jar_path: str,
        max_retries: int = 3,
        cast_options: Optional[CastOptions] = None,
    ) -> bool:
        if self._connected:
            self.stop()

        self._device_serial = device_serial
        self._server_jar_path = server_jar_path
        self._stopping = False
        self._max_reconnect = max_retries
        self._cast_options = cast_options or CastOptions()
        if self._cast_options.video_codec != "h264":
            if not self._probe_codec_supported(self._cast_options.video_codec):
                logger.warning(
                    "设备不支持 video_codec=%s，回退到 h264",
                    self._cast_options.video_codec,
                )
                self._cast_options.video_codec = "h264"

        for attempt in range(1, max_retries + 1):
            logger.info("尝试启动scrcpy连接 (%d/%d): %s", attempt, max_retries, device_serial)
            try:
                if self._start_scrcpy():
                    self._connected = True
                    if self._reconnect_count > 0:
                        self.connection_restored.emit()
                    logger.info("scrcpy连接成功: %s", device_serial)
                    return True
            except Exception as e:
                logger.error("scrcpy连接失败 (%d/%d): %s", attempt, max_retries, e)
                self.error_occurred.emit(f"连接失败 (尝试 {attempt}/{max_retries}): {e}")
                self._cleanup_resources()

            if attempt < max_retries:
                time.sleep(_RECONNECT_DELAY)

        logger.warning("scrcpy连接失败，切换到screencap回退模式: %s", device_serial)
        self._connected = True
        self._start_fallback_reader()
        return True

    def stop(self):
        logger.info("停止屏幕捕获: %s", self._device_serial)
        self._stopping = True
        self._connected = False
        self._cleanup_resources()

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

    def _start_scrcpy(self) -> bool:
        push_cmd = [
            "adb", "-s", self._device_serial, "push",
            self._server_jar_path, "/data/local/tmp/scrcpy-server.jar"
        ]
        result = subprocess.run(
            push_cmd, capture_output=True, timeout=30,
            creationflags=_SUBPROCESS_FLAGS
        )
        if result.returncode != 0:
            raise RuntimeError(f"推送scrcpy-server失败: {result.stderr.decode(errors='replace')}")

    def _start_server_process(self, server_version: str = None):
        """启动 scrcpy server 子进程（支持 2.x / 3.x / 4.x 版本自适应）。

        forward_cmd = [
            "adb", "-s", self._device_serial, "forward",
            f"tcp:{self._forward_port}", f"localabstract:{_SCRCPY_SOCKET_NAME}"
        ]
        result = subprocess.run(
            forward_cmd, capture_output=True, timeout=10,
            creationflags=_SUBPROCESS_FLAGS
        )
        if result.returncode != 0:
            raise RuntimeError(f"adb forward失败: {result.stderr.decode(errors='replace')}")

        server_cmd = [
            "adb", "-s", self._device_serial, "shell",
            "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
            "app_process", "/", "com.genymobile.scrcpy.Server",
            opts.server_version, "log_level=info",
            f"video_codec={opts.video_codec}",
            f"video_bit_rate={opts.bit_rate}",
            f"max_size={opts.max_size}",
            f"max_fps={opts.max_fps}",
            "tunnel_forward=true", "control=false", "cleanup=true", "audio=false"
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

        time.sleep(opts.startup_wait)

        if self._server_process.poll() is not None:
            stderr_output = self._server_process.stderr.read().decode(errors="replace")
            raise RuntimeError(f"scrcpy服务启动失败: {stderr_output}")

        connected = False
        for socket_attempt in range(_SOCKET_CONNECT_RETRIES):
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
                self._socket.settimeout(5)
                self._socket.connect(("127.0.0.1", self._forward_port))
                self._socket.settimeout(2)
                connected = True
                break
            except (ConnectionRefusedError, OSError) as e:
                if socket_attempt == _SOCKET_CONNECT_RETRIES - 1:
                    raise RuntimeError(f"无法连接到scrcpy socket: {e}")
                time.sleep(_SOCKET_CONNECT_INTERVAL)

        if not connected:
            raise RuntimeError("无法连接到scrcpy socket")

        name_len_byte = self._recv_exact(1)
        if not name_len_byte:
            raise RuntimeError("无法读取设备名称长度")
        name_len = struct.unpack("B", name_len_byte)[0]
        if name_len > 0:
            device_name = self._recv_exact(name_len)
            if device_name:
                logger.info("设备名称: %s", device_name.decode(errors="replace"))

        codec_info = self._recv_exact(4)
        if not codec_info:
            raise RuntimeError("无法读取编码信息")

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

        self._start_decoder_pipeline()
        return True

    def _start_decoder_pipeline(self):
        """解码管线分发：优先 PyAV 进程内解码，失败回退 ffmpeg rawvideo。"""
        if self._use_pyav:
            try:
                self._start_pyav_decoder()
                return
            except Exception as e:
                logger.warning("PyAV 解码初始化失败，回退到 ffmpeg: %s", e)
                self._use_pyav = False
                self._av_codec = None
        self._start_ffmpeg_and_threads()

    def _start_pyav_decoder(self):
        self._generation += 1
        gen = self._generation
        codec_name = self._cast_options.video_codec
        try:
            self._av_codec = _av.CodecContext.create(codec_name, "r")
        except Exception as e:
            raise RuntimeError(f"PyAV 创建 {codec_name} 解码器失败: {e}")
        self._frame_w = 0
        self._frame_h = 0
        self._writer_thread = threading.Thread(
            target=self._pyav_decode_loop, args=(gen,), daemon=True
        )
        self._writer_thread.start()

    def _pyav_decode_loop(self, gen: int):
        logger.debug("PyAV 解码线程启动 [gen=%d]", gen)
        codec = self._av_codec
        try:
            while not self._stopping and self._generation == gen:
                pts_data = self._recv_exact(8)
                if not pts_data:
                    break
                size_data = self._recv_exact(4)
                if not size_data:
                    break
                packet_size = struct.unpack(">I", size_data)[0]
                if packet_size == 0:
                    continue
                if packet_size > _MAX_PACKET_SIZE:
                    logger.warning("异常包大小: %d, 跳过", packet_size)
                    continue
                h264_data = self._recv_exact(packet_size)
                if not h264_data:
                    break
                try:
                    for packet in codec.parse(h264_data):
                        for frame in codec.decode(packet):
                            self._handle_decoded_frame(frame, gen)
                except Exception as e:
                    logger.debug("PyAV 解码单包异常 [gen=%d]: %s", gen, e)
        except Exception as e:
            if not self._stopping:
                logger.error("PyAV 解码线程异常 [gen=%d]: %s", gen, e)
        finally:
            logger.debug("PyAV 解码线程结束 [gen=%d]", gen)
            if not self._stopping and self._generation == gen:
                self._handle_connection_lost()

    def _handle_decoded_frame(self, frame, gen: int):
        """处理 PyAV 解码出的 VideoFrame，转 ndarray 后缓存/emit。

        节流位置上移：未到 emit 间隔则跳过昂贵的 to_ndarray 转换，
        仅首帧用于解析宽高。被跳过的帧仍正常参与 H.264 参考解码，
        _current_frame 最多 ~_FRAME_EMIT_INTERVAL 陈旧，可接受。
        """
        if self._frame_w == 0 and frame.width > 0:
            self._frame_w = frame.width
            self._frame_h = frame.height
            logger.debug("PyAV 解析分辨率: %dx%d", self._frame_w, self._frame_h)
        now = time.monotonic()
        if now - self._last_emit_time < _FRAME_EMIT_INTERVAL:
            return
        self._last_emit_time = now
        arr = frame.to_ndarray(format="bgr24")
        with self._frame_lock:
            self._current_frame = arr
        self.frame_captured.emit(arr)

    def _remote_jar_matches_local(self) -> bool:
        """校验远端 scrcpy-server.jar 大小与本地一致，用于跳过重复 push。"""
        try:
            local_size = os.path.getsize(self._server_jar_path)
        except OSError:
            return False
        try:
            result = subprocess.run(
                ["adb", "-s", self._device_serial, "shell",
                 "ls", "-s", "/data/local/tmp/scrcpy-server.jar"],
                capture_output=True, timeout=5,
                creationflags=_SUBPROCESS_FLAGS
            )
        except (subprocess.TimeoutExpired, OSError):
            return False
        if result.returncode != 0:
            return False
        out = result.stdout.decode(errors="replace").strip()
        parts = out.split()
        if not parts:
            return False
        try:
            remote_size = int(parts[0])
        except ValueError:
            return False
        return remote_size == local_size and local_size > 0

    def _probe_codec_supported(self, codec: str) -> bool:
        """探测设备是否支持指定 video codec 的硬件编码。

        通过 scrcpy server 的 list_encoders 能力（server >= 2.0）查询；
        不可用时降级为基于 Android API level 的保守判断。
        """
        if codec == "h264":
            return True
        try:
            result = subprocess.run(
                ["adb", "-s", self._device_serial, "shell",
                 "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
                 "app_process", "/", "com.genymobile.scrcpy.Server",
                 self._cast_options.server_version, "log_level=warn",
                 "list_encoders=true"],
                capture_output=True, timeout=8,
                creationflags=_SUBPROCESS_FLAGS
            )
            text = (result.stdout + result.stderr).decode(errors="replace")
            return codec in text
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _start_ffmpeg_and_threads(self):
        self._generation += 1
        gen = self._generation

        ffmpeg_cmd = [
            "ffmpeg",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-f", "h264",
            "-i", "pipe:0",
            "-f", "rawvideo",
            "-pix_fmt", "bgr0",
            "pipe:1"
        ]

        try:
            self._ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=_SUBPROCESS_FLAGS
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg未找到，请确认ffmpeg已安装并添加到PATH")

        self._writer_thread = threading.Thread(
            target=self._socket_to_ffmpeg, args=(gen,), daemon=True
        )
        self._writer_thread.start()

        self._frame_w, self._frame_h = self._probe_frame_size(gen, timeout=6.0)
        if self._frame_w == 0 or self._frame_h == 0:
            raise RuntimeError("无法解析视频宽高")

        self._decoder_thread = threading.Thread(
            target=self._decode_ffmpeg_output, args=(gen,), daemon=True
        )
        self._decoder_thread.start()

    def _recv_exact(self, length: int) -> Optional[bytes]:
        if self._socket is None:
            return None
        data = b""
        while len(data) < length:
            try:
                chunk = self._socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                if self._stopping:
                    return None
                continue
            except (ConnectionError, OSError):
                return None
        return data

    def _probe_frame_size(self, gen: int, timeout: float = 4.0) -> tuple:
        import re
        import select
        pattern = re.compile(rb',\s*(\d+)x(\d+)[\s,]')
        deadline = time.monotonic() + timeout
        stderr = self._ffmpeg_process.stderr if self._ffmpeg_process else None
        if stderr is None:
            return 0, 0
        fd = stderr.fileno()
        collected = b""
        while time.monotonic() < deadline:
            if self._stopping or self._generation != gen:
                break
            if self._ffmpeg_process.poll() is not None:
                break
            ready, _, _ = select.select([fd], [], [], 0.05)
            if not ready:
                continue
            try:
                chunk = stderr.read(4096)
            except (BlockingIOError, OSError):
                time.sleep(0.02)
                continue
            if chunk:
                collected += chunk
                m = pattern.search(collected)
                if m:
                    return int(m.group(1)), int(m.group(2))
            else:
                time.sleep(0.02)
        logger.warning("ffmpeg 未能解析分辨率，stderr 片段: %r", collected[-512:])
        return 0, 0

    def _socket_to_ffmpeg(self, gen: int):
        logger.debug("socket读取线程启动 [gen=%d]", gen)
        try:
            while not self._stopping and self._generation == gen:
                pts_data = self._recv_exact(8)
                if not pts_data:
                    break

                size_data = self._recv_exact(4)
                if not size_data:
                    break

                packet_size = struct.unpack(">I", size_data)[0]
                if packet_size == 0:
                    continue

                if packet_size > _MAX_PACKET_SIZE:
                    logger.warning("寮傚父鍖呭ぇ灏? %d, 跳过", packet_size)
                    continue

                h264_data = self._recv_exact(packet_size)
                if not h264_data:
                    break

                if self._ffmpeg_process and self._ffmpeg_process.stdin:
                    try:
                        self._ffmpeg_process.stdin.write(h264_data)
                        self._ffmpeg_process.stdin.flush()
                    except (BrokenPipeError, OSError):
                        break
        except Exception as e:
            if not self._stopping:
                logger.error("socket读取线程异常 [gen=%d]: %s", gen, e)
        finally:
            logger.debug("socket读取线程结束 [gen=%d]", gen)
            if self._ffmpeg_process and self._ffmpeg_process.stdin:
                try:
                    self._ffmpeg_process.stdin.close()
                except Exception:
                    pass
            if not self._stopping and self._generation == gen:
                self._handle_connection_lost()

    def _decode_ffmpeg_output(self, gen: int):
        logger.debug("帧解码线程启动[gen=%d]", gen)
        buf = b""

        try:
            while not self._stopping and self._generation == gen and self._ffmpeg_process:
                try:
                    data = self._ffmpeg_process.stdout.read(1 << 20)
                    if not data:
                        break
                    buf += data
                except Exception:
                    break

                while len(buf) >= frame_size:
                    now = time.monotonic()
                    if now - self._last_emit_time < _FRAME_EMIT_INTERVAL:
                        # 命中节流：只消费缓冲（避免堆积），跳过拷贝与 numpy 构造
                        del buf[:frame_size]
                        continue
                    self._last_emit_time = now
                    raw = bytes(buf[:frame_size])
                    del buf[:frame_size]
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)
                    frame = frame[:, :, :3]
                    with self._frame_lock:
                        self._current_frame = frame
                    self.frame_captured.emit(frame)
        except Exception as e:
            if not self._stopping:
                logger.error("帧解码线程异常[gen=%d]: %s", gen, e)
        finally:
            logger.debug("帧解码线程结束[gen=%d]", gen)

    def _start_fallback_reader(self):
        self._fallback_thread = threading.Thread(target=self._fallback_loop, daemon=True)
        self._fallback_thread.start()

    def _fallback_loop(self):
        logger.info("screencap回退模式启动")
        while not self._stopping:
            try:
                frame = self._screencap_single()
                if frame is not None:
                    with self._frame_lock:
                        self._current_frame = frame
                    now = time.monotonic()
                    if now - self._last_emit_time >= _FRAME_EMIT_INTERVAL:
                        self._last_emit_time = now
                        self.frame_captured.emit(frame)
                time.sleep(_FALLBACK_INTERVAL)
            except Exception as e:
                logger.error("screencap回退模式出错: %s", e)
                if not self._stopping:
                    self._connected = False
                    self.connection_lost.emit()
                    time.sleep(1)
                    self._connected = True
        logger.info("screencap回退模式结束")

    def _screencap_single(self) -> Optional[np.ndarray]:
        try:
            proc = subprocess.Popen(
                ["adb", "-s", self._device_serial, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE,
                creationflags=_SUBPROCESS_FLAGS
            )
            data, _ = proc.communicate(timeout=10)
            if proc.returncode != 0 or not data:
                return None
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            return frame
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return None
        except Exception as e:
            logger.error("screencap失败: %s", e)
            return None

    def _handle_connection_lost(self):
        if self._stopping:
            return
        try:
            # 如果 server 已退出，直接读取全部 stderr
            if self._server_process.poll() is not None:
                stderr_data = self._server_process.stderr.read()
                if stderr_data:
                    stderr_text = stderr_data.decode(errors="replace")[:1000]
                    logger.error("scrcpy server stderr: %s", stderr_text)
                return

            logger.info("自动重连 (%d/%d)", attempt, self._max_reconnect)
            time.sleep(_RECONNECT_DELAY)

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
                if self._start_scrcpy():
                    self._connected = True
                    self._reconnect_count = 0
                    self.connection_restored.emit()
                    logger.info("自动重连成功")
                    return
            except Exception as e:
                logger.error("自动重连失败 (%d/%d): %s", attempt, self._max_reconnect, e)

        logger.warning("自动重连失败，切换到screencap回退模式")
        self.error_occurred.emit("scrcpy连接丢失，已切换到screencap回退模式")
        self._connected = True
        self._start_fallback_reader()

    def _cleanup_resources(self):
        with self._cleanup_lock:
            if self._socket:
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

            self._writer_thread = None
            self._decoder_thread = None
            self._fallback_thread = None
            self._av_codec = None

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
