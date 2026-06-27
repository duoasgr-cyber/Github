import subprocess
import threading
import socket
import struct
import logging
import re
import time
import os
import sys
from typing import Optional, Tuple

import numpy as np
import cv2
from PyQt5.QtCore import QObject, pyqtSignal

from core.scrcpy_control import ScrcpyControl, ACTION_DOWN, ACTION_MOVE, ACTION_UP


logger = logging.getLogger(__name__)

if sys.platform == "win32":
    _SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    _SUBPROCESS_FLAGS = 0

_SCRCPY_SOCKET_NAME = "scrcpy"
_DEFAULT_FORWARD_PORT = 27183
_FRAME_EMIT_INTERVAL = 0.033
_JPEG_BUFFER_MAX = 5 * 1024 * 1024
_MAX_PACKET_SIZE = 10 * 1024 * 1024
_SERVER_STARTUP_WAIT = 1.5
_RECONNECT_DELAY = 2.0
_FALLBACK_INTERVAL = 0.1
_SOCKET_CONNECT_RETRIES = 5
_SOCKET_CONNECT_INTERVAL = 0.5

# 延迟优化参数（不降画质）
# bit_rate 提到 6Mbps（1080p 高画质）；关键帧间隔 10，加快重连首帧
_SCRCPY_BIT_RATE = 6000000
_SCRCPY_MAX_SIZE = 1080
_SCRCPY_I_FRAME_INTERVAL = 10
# rawvideo 显示通道：省掉 mjpeg 编码+JPEG 解码两步，延迟 -10~25ms
_USE_RAWVIDEO = True
# stderr 解析视频分辨率的超时（秒）
_VIDEO_SIZE_DETECT_TIMEOUT = 8.0
# ffmpeg stderr 中分辨率正则（匹配形如 1080x486 / 1920x1080）
_RESOLUTION_RE = re.compile(rb"(\d{2,5})x(\d{2,5})")

# 触摸 tap 判定阈值（视频流坐标系像素，press≈release 视为 tap）
_TOUCH_TAP_THRESHOLD = 10


class ScrcpyCapture(QObject):
    frame_captured = pyqtSignal(np.ndarray)
    connection_lost = pyqtSignal()
    connection_restored = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_serial: Optional[str] = None
        self._server_jar_path: Optional[str] = None
        self._connected: bool = False
        self._use_scrcpy: bool = False
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

        # 控制协议注入（低延迟）与降级路径
        self._adb_core = None  # 降级 adb input 注入用
        self._control: Optional[ScrcpyControl] = None
        self._video_size: Tuple[int, int] = (0, 0)  # 当前视频帧尺寸（视频流坐标系）
        self._base_resolution: Tuple[int, int] = (2400, 1080)  # 设备物理分辨率（降级坐标转换用）

        # 触摸手势状态（adb 降级模式下记录按下起点，release 时整体注入）
        self._touch_start: Tuple[int, int] = (-1, -1)
        self._touch_start_time: float = 0.0

        # rawvideo 解析分辨率相关
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._size_event = threading.Event()
        self._stderr_thread: Optional[threading.Thread] = None

    def start(self, device_serial: str, server_jar_path: str, max_retries: int = 3, adb_core=None) -> bool:
        if self._connected:
            self.stop()

        self._device_serial = device_serial
        self._server_jar_path = server_jar_path
        self._stopping = False
        self._max_reconnect = max_retries
        self._adb_core = adb_core  # 降级注入路径用

        for attempt in range(1, max_retries + 1):
            logger.info("灏濊瘯鍚姩scrcpy杩炴帴 (%d/%d): %s", attempt, max_retries, device_serial)
            try:
                if self._start_scrcpy():
                    self._connected = True
                    self._use_scrcpy = True
                    if self._reconnect_count > 0:
                        self.connection_restored.emit()
                    logger.info("scrcpy杩炴帴鎴愬姛: %s", device_serial)
                    # 异步建立 control socket（失败仅降级注入，不影响投屏）
                    self._start_control_channel()
                    return True
            except Exception as e:
                logger.error("scrcpy杩炴帴澶辫触 (%d/%d): %s", attempt, max_retries, e)
                self.error_occurred.emit(f"杩炴帴澶辫触 (灏濊瘯 {attempt}/{max_retries}): {e}")
                self._cleanup_resources()

            if attempt < max_retries:
                time.sleep(_RECONNECT_DELAY)

        logger.warning("scrcpy杩炴帴澶辫触锛屽垏鎹㈠埌screencap鍥為€€妯″紡: %s", device_serial)
        self._use_scrcpy = False
        self._connected = True
        self._start_fallback_reader()
        return True

    def stop(self):
        logger.info("鍋滄灞忓箷鎹曡幏: %s", self._device_serial)
        self._stopping = True
        self._connected = False
        self._cleanup_resources()

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None

    def is_connected(self) -> bool:
        return self._connected

    def set_base_resolution(self, width: int, height: int) -> None:
        """设置设备物理分辨率，用于降级 adb input 时的坐标转换。"""
        self._base_resolution = (int(width), int(height))

    def get_video_size(self) -> Tuple[int, int]:
        """返回当前视频帧尺寸（视频流坐标系，受 max_size 缩放）。"""
        return self._video_size

    def is_control_available(self) -> bool:
        """scrcpy 控制通道是否可用（低延迟注入）。"""
        return self._control is not None and self._control.is_available()

    def inject_tap(self, x: int, y: int) -> bool:
        """注入一次点击。x,y 为 **视频流坐标系** 坐标。

        优先 scrcpy 控制协议（~10ms）；不可用则降级 adb input（~100ms），
        降级时自动把视频流坐标转换为设备物理坐标。
        """
        if self._control is not None and self._control.is_available():
            return self._control.inject_tap(x, y)
        return self._inject_tap_via_adb(x, y)

    def inject_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> bool:
        """注入一次滑动。坐标为 **视频流坐标系**，duration 单位秒。

        优先 scrcpy 控制协议；不可用则降级 adb input（duration 转毫秒）。
        """
        if self._control is not None and self._control.is_available():
            return self._control.inject_swipe(x1, y1, x2, y2, duration)
        return self._inject_swipe_via_adb(x1, y1, x2, y2, duration)

    def begin_touch(self, vx: int, vy: int) -> bool:
        """开始触摸（按下）。视频流坐标。

        control 模式：立即注入 DOWN，手指实时跟随。
        adb 降级模式：仅记录起点，待 end_touch 时整体注入。
        """
        self._touch_start = (vx, vy)
        self._touch_start_time = time.monotonic()
        if self.is_control_available():
            return self._control.inject_touch_event(ACTION_DOWN, vx, vy)
        return True

    def move_touch(self, vx: int, vy: int) -> bool:
        """触摸移动。视频流坐标。

        control 模式：立即注入 MOVE（实时跟随）；adb 降级模式忽略中间移动。
        """
        if self.is_control_available():
            return self._control.inject_touch_event(ACTION_MOVE, vx, vy)
        return True

    def end_touch(self, vx: int, vy: int) -> bool:
        """结束触摸（抬起）。视频流坐标。

        control 模式：立即注入 UP。
        adb 降级模式：根据起点/终点位移判定 tap 或 swipe，整体注入。
        """
        sx, sy = self._touch_start
        duration = max(time.monotonic() - self._touch_start_time, 0.0)
        self._touch_start = (-1, -1)

        if self.is_control_available():
            return self._control.inject_touch_event(ACTION_UP, vx, vy)

        # adb 降级：整体注入
        if self._adb_core is None:
            return False
        dist = ((vx - sx) ** 2 + (vy - sy) ** 2) ** 0.5
        if dist < _TOUCH_TAP_THRESHOLD:
            dx, dy = self._video_to_device(vx, vy)
            return self._adb_core.tap(dx, dy)
        return self._inject_swipe_via_adb(sx, sy, vx, vy, max(duration, 0.05))

    def _inject_tap_via_adb(self, vx: int, vy: int) -> bool:
        if self._adb_core is None:
            logger.debug("adb 注入跳过：adb_core 未设置")
            return False
        dx, dy = self._video_to_device(vx, vy)
        return self._adb_core.tap(dx, dy)

    def _inject_swipe_via_adb(self, vx1: int, vy1: int, vx2: int, vy2: int, duration: float) -> bool:
        if self._adb_core is None:
            logger.debug("adb 注入跳过：adb_core 未设置")
            return False
        dx1, dy1 = self._video_to_device(vx1, vy1)
        dx2, dy2 = self._video_to_device(vx2, vy2)
        # adb swipe duration 单位毫秒
        return self._adb_core.swipe(dx1, dy1, dx2, dy2, duration * 1000)

    def _video_to_device(self, vx: int, vy: int) -> Tuple[int, int]:
        """视频流坐标 → 设备物理坐标（基于当前视频尺寸与 base_resolution）。"""
        vw, vh = self._video_size
        bw, bh = self._base_resolution
        if vw == 0 or vh == 0:
            return int(vx), int(vy)
        dx = int(vx * bw / vw)
        dy = int(vy * bh / vh)
        # 限制到设备屏幕范围
        dx = max(0, min(dx, bw - 1))
        dy = max(0, min(dy, bh - 1))
        return dx, dy

    def _start_control_channel(self) -> None:
        """异步建立 scrcpy control socket（失败仅降级注入，不影响投屏）。"""
        if self._control is not None:
            self._control.close()
        self._control = ScrcpyControl(self._forward_port)
        # 若已解析到视频尺寸，先同步给 control
        if self._video_size != (0, 0):
            self._control.set_video_size(*self._video_size)

        def _worker():
            try:
                self._control.connect()
            except Exception as e:
                logger.warning("control 通道建立异常: %s", e)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

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
            raise RuntimeError(f"鎺ㄩ€乻crcpy-server澶辫触: {result.stderr.decode(errors='replace')}")

        subprocess.run(
            ["adb", "-s", self._device_serial, "forward", "--remove", f"tcp:{self._forward_port}"],
            capture_output=True, timeout=5,
            creationflags=_SUBPROCESS_FLAGS
        )

        forward_cmd = [
            "adb", "-s", self._device_serial, "forward",
            f"tcp:{self._forward_port}", f"localabstract:{_SCRCPY_SOCKET_NAME}"
        ]
        result = subprocess.run(
            forward_cmd, capture_output=True, timeout=10,
            creationflags=_SUBPROCESS_FLAGS
        )
        if result.returncode != 0:
            raise RuntimeError(f"adb forward澶辫触: {result.stderr.decode(errors='replace')}")

        server_cmd = [
            "adb", "-s", self._device_serial, "shell",
            "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
            "app_process", "/", "com.genymobile.scrcpy.Server",
            "2.0", "log_level=info",
            f"bit_rate={_SCRCPY_BIT_RATE}", f"max_size={_SCRCPY_MAX_SIZE}",
            f"i_frame_interval={_SCRCPY_I_FRAME_INTERVAL}",
            "tunnel_forward=true", "control=true", "cleanup=true", "audio=false"
        ]
        self._server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_SUBPROCESS_FLAGS
        )

        time.sleep(_SERVER_STARTUP_WAIT)

        if self._server_process.poll() is not None:
            stderr_output = self._server_process.stderr.read().decode(errors="replace")
            raise RuntimeError(f"scrcpy鏈嶅姟鍚姩澶辫触: {stderr_output}")

        connected = False
        for socket_attempt in range(_SOCKET_CONNECT_RETRIES):
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(5)
                self._socket.connect(("127.0.0.1", self._forward_port))
                self._socket.settimeout(2)
                connected = True
                break
            except (ConnectionRefusedError, OSError) as e:
                if socket_attempt == _SOCKET_CONNECT_RETRIES - 1:
                    raise RuntimeError(f"鏃犳硶杩炴帴鍒皊crcpy socket: {e}")
                time.sleep(_SOCKET_CONNECT_INTERVAL)

        if not connected:
            raise RuntimeError("鏃犳硶杩炴帴鍒皊crcpy socket")

        name_len_byte = self._recv_exact(1)
        if not name_len_byte:
            raise RuntimeError("鏃犳硶璇诲彇璁惧鍚嶇О闀垮害")
        name_len = struct.unpack("B", name_len_byte)[0]
        if name_len > 0:
            device_name = self._recv_exact(name_len)
            if device_name:
                logger.info("璁惧鍚嶇О: %s", device_name.decode(errors="replace"))

        codec_info = self._recv_exact(4)
        if not codec_info:
            raise RuntimeError("鏃犳硶璇诲彇缂栫爜淇℃伅")

        self._start_ffmpeg_and_threads()
        return True

    def _start_ffmpeg_and_threads(self):
        self._generation += 1
        gen = self._generation

        # 重置 rawvideo 分辨率探测状态
        self._frame_w = 0
        self._frame_h = 0
        self._size_event.clear()

        ffmpeg_cmd = [
            "ffmpeg",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-f", "h264",
            "-i", "pipe:0",
        ]
        if _USE_RAWVIDEO:
            # rawvideo bgr24：省掉 mjpeg 编码 + JPEG 解码两步，直接 np.frombuffer 成帧
            ffmpeg_cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
        else:
            ffmpeg_cmd += ["-f", "mjpeg", "-q:v", "5", "pipe:1"]

        try:
            self._ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=(subprocess.PIPE if _USE_RAWVIDEO else subprocess.DEVNULL),
                bufsize=0,
                creationflags=_SUBPROCESS_FLAGS
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg鏈壘鍒帮紝璇风‘淇漟fmpeg宸插畨瑁呭苟娣诲姞鍒癙ATH")

        if _USE_RAWVIDEO:
            self._stderr_thread = threading.Thread(
                target=self._read_ffmpeg_stderr, args=(gen,), daemon=True
            )
            self._stderr_thread.start()

        self._writer_thread = threading.Thread(
            target=self._socket_to_ffmpeg, args=(gen,), daemon=True
        )
        self._writer_thread.start()

        self._decoder_thread = threading.Thread(
            target=self._decode_ffmpeg_output, args=(gen,), daemon=True
        )
        self._decoder_thread.start()

    def _read_ffmpeg_stderr(self, gen: int):
        """读取 ffmpeg stderr，解析视频流分辨率。

        rawvideo 输出无元数据，必须从 stderr 获取帧尺寸才能定长读取。
        ffmpeg 启动时会输出形如 `Stream #0:0: Video: h264 ..., 1080x486`。
        解析到后通过 _size_event 通知解码线程，并同步给 ScrcpyControl。
        """
        if not self._ffmpeg_process or not self._ffmpeg_process.stderr:
            return
        try:
            for line in iter(self._ffmpeg_process.stderr.readline, b""):
                if self._stopping or self._generation != gen:
                    return
                # 取最后一个匹配（避免与输入流信息混淆，输出行通常在后）
                matches = _RESOLUTION_RE.findall(line)
                if matches:
                    w, h = int(matches[-1][0]), int(matches[-1][1])
                    # 过滤明显异常值
                    if 16 <= w <= 7680 and 16 <= h <= 7680 and (w, h) != (self._frame_w, self._frame_h):
                        self._frame_w = w
                        self._frame_h = h
                        self._size_event.set()
                        logger.info("解析到视频分辨率: %dx%d", w, h)
                        # 同步给 control（注入需校验视频尺寸）
                        if self._control is not None:
                            self._control.set_video_size(w, h)
        except Exception as e:
            if not self._stopping:
                logger.debug("ffmpeg stderr 读取结束: %s", e)

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

    def _socket_to_ffmpeg(self, gen: int):
        logger.debug("socket璇诲彇绾跨▼鍚姩 [gen=%d]", gen)
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
                    logger.warning("寮傚父鍖呭ぇ灏? %d, 璺宠繃", packet_size)
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
                logger.error("socket璇诲彇绾跨▼寮傚父 [gen=%d]: %s", gen, e)
        finally:
            logger.debug("socket璇诲彇绾跨▼缁撴潫 [gen=%d]", gen)
            if self._ffmpeg_process and self._ffmpeg_process.stdin:
                try:
                    self._ffmpeg_process.stdin.close()
                except Exception:
                    pass
            if not self._stopping and self._generation == gen:
                self._handle_connection_lost()

    def _decode_ffmpeg_output(self, gen: int):
        logger.debug("甯цВ鐮佺嚎绋嬪惎鍔?[gen=%d]", gen)
        try:
            if _USE_RAWVIDEO:
                self._decode_rawvideo(gen)
            else:
                self._decode_mjpeg(gen)
        except Exception as e:
            if not self._stopping:
                logger.error("甯цВ鐮佺嚎绋嬪紓甯?[gen=%d]: %s", gen, e)
        finally:
            logger.debug("甯цВ鐮佺嚎绋嬬粨鏉?[gen=%d]", gen)

    def _decode_rawvideo(self, gen: int):
        """rawvideo 定长读取：每帧 w*h*3 字节，np.frombuffer + reshape 成帧。

        需先从 stderr 解析出分辨率（_size_event），否则无法切帧。
        """
        if not self._size_event.wait(timeout=_VIDEO_SIZE_DETECT_TIMEOUT):
            if not self._stopping:
                logger.error("rawvideo 分辨率解析超时，无法解码")
            return

        buf = b""
        while not self._stopping and self._generation == gen and self._ffmpeg_process:
            w, h = self._frame_w, self._frame_h
            if w == 0 or h == 0:
                time.sleep(0.05)
                continue
            frame_size = w * h * 3

            # 凑够一帧
            while len(buf) < frame_size:
                if self._stopping or self._generation != gen:
                    return
                try:
                    chunk = self._ffmpeg_process.stdout.read(4096)
                except Exception:
                    return
                if not chunk:
                    return
                buf += chunk
                # 尺寸可能在读取过程中变化（旋转），重新计算并丢弃错位数据
                if (self._frame_w, self._frame_h) != (w, h):
                    w, h = self._frame_w, self._frame_h
                    frame_size = w * h * 3
                    buf = b""
                    break

            if len(buf) < frame_size:
                continue

            raw = buf[:frame_size]
            buf = buf[frame_size:]
            try:
                frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
            except ValueError:
                continue

            self._publish_frame(frame, w, h)

    def _decode_mjpeg(self, gen: int):
        """mjpeg JPEG 边界扫描解码（回退路径）。"""
        buf = b""
        while not self._stopping and self._generation == gen and self._ffmpeg_process:
            try:
                data = self._ffmpeg_process.stdout.read(4096)
                if not data:
                    break
                buf += data
            except Exception:
                break

            while True:
                start = buf.find(b'\xff\xd8')
                if start == -1:
                    if len(buf) > _JPEG_BUFFER_MAX:
                        buf = buf[-1024:]
                    break
                end = buf.find(b'\xff\xd9', start + 2)
                if end == -1:
                    if len(buf) > _JPEG_BUFFER_MAX:
                        buf = buf[start:]
                    break
                jpeg_data = buf[start:end + 2]
                buf = buf[end + 2:]
                frame = cv2.imdecode(np.frombuffer(jpeg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    h, w = frame.shape[:2]
                    self._publish_frame(frame, w, h)

    def _publish_frame(self, frame: np.ndarray, w: int, h: int):
        """覆盖式写最新帧 + 节流 emit + 同步视频尺寸到 control。

        覆盖式缓冲：只保留最新帧，丢弃中间积压帧，消除延迟累积。
        """
        with self._frame_lock:
            # frombuffer 视图自带 base 引用，赋值安全；get_current_frame 取出时会 copy
            self._current_frame = frame

        # 视频尺寸变化时同步给 control（注入报文需校验视频尺寸）
        if (w, h) != self._video_size:
            self._video_size = (w, h)
            if self._control is not None:
                self._control.set_video_size(w, h)

        now = time.monotonic()
        if now - self._last_emit_time >= _FRAME_EMIT_INTERVAL:
            self._last_emit_time = now
            self.frame_captured.emit(frame.copy())

    def _start_fallback_reader(self):
        self._fallback_thread = threading.Thread(target=self._fallback_loop, daemon=True)
        self._fallback_thread.start()

    def _fallback_loop(self):
        logger.info("screencap鍥為€€妯″紡鍚姩")
        while not self._stopping:
            try:
                frame = self._screencap_single()
                if frame is not None:
                    with self._frame_lock:
                        self._current_frame = frame
                    now = time.monotonic()
                    if now - self._last_emit_time >= _FRAME_EMIT_INTERVAL:
                        self._last_emit_time = now
                        self.frame_captured.emit(frame.copy())
                time.sleep(_FALLBACK_INTERVAL)
            except Exception as e:
                logger.error("screencap鍥為€€妯″紡鍑洪敊: %s", e)
                if not self._stopping:
                    self._connected = False
                    self.connection_lost.emit()
                    time.sleep(1)
                    self._connected = True
        logger.info("screencap鍥為€€妯″紡缁撴潫")

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
            logger.error("screencap澶辫触: %s", e)
            return None

    def _handle_connection_lost(self):
        if self._stopping:
            return

        self._connected = False
        self.connection_lost.emit()

        self._reconnect_count += 1
        reconnect_thread = threading.Thread(target=self._auto_reconnect, daemon=True)
        reconnect_thread.start()

    def _auto_reconnect(self):
        for attempt in range(1, self._max_reconnect + 1):
            if self._stopping:
                return

            logger.info("鑷姩閲嶈繛 (%d/%d)", attempt, self._max_reconnect)
            time.sleep(_RECONNECT_DELAY)

            self._cleanup_resources()

            try:
                if self._start_scrcpy():
                    self._connected = True
                    self._use_scrcpy = True
                    self._reconnect_count = 0
                    self.connection_restored.emit()
                    logger.info("鑷姩閲嶈繛鎴愬姛")
                    return
            except Exception as e:
                logger.error("鑷姩閲嶈繛澶辫触 (%d/%d): %s", attempt, self._max_reconnect, e)

        logger.warning("鑷姩閲嶈繛澶辫触锛屽垏鎹㈠埌screencap鍥為€€妯″紡")
        self.error_occurred.emit("scrcpy杩炴帴涓㈠け锛屽凡鍒囨崲鍒皊creencap鍥為€€妯″紡")
        self._use_scrcpy = False
        self._connected = True
        self._start_fallback_reader()

    def _cleanup_resources(self):
        with self._cleanup_lock:
            # 关闭控制通道
            if self._control is not None:
                try:
                    self._control.close()
                except Exception:
                    pass
                self._control = None
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

            if self._ffmpeg_process:
                try:
                    if self._ffmpeg_process.stdin:
                        self._ffmpeg_process.stdin.close()
                except Exception:
                    pass
                try:
                    self._ffmpeg_process.terminate()
                    self._ffmpeg_process.wait(timeout=3)
                except Exception:
                    try:
                        self._ffmpeg_process.kill()
                    except Exception:
                        pass
                self._ffmpeg_process = None

            if self._server_process:
                try:
                    self._server_process.terminate()
                    self._server_process.wait(timeout=3)
                except Exception:
                    try:
                        self._server_process.kill()
                    except Exception:
                        pass
                self._server_process = None

            for thread in [self._writer_thread, self._decoder_thread, self._fallback_thread, self._stderr_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=5)

            self._writer_thread = None
            self._decoder_thread = None
            self._fallback_thread = None
            self._stderr_thread = None

            if self._device_serial:
                subprocess.run(
                    ["adb", "-s", self._device_serial, "forward", "--remove", f"tcp:{self._forward_port}"],
                    capture_output=True, timeout=5,
                    creationflags=_SUBPROCESS_FLAGS
                )


