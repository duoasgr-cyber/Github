import subprocess
import threading
import socket
import struct
import logging
import time
import os
import sys
from typing import Optional

import numpy as np
import cv2
from PyQt5.QtCore import QObject, pyqtSignal

try:
    import av as _av
    _HAS_PYAV = True
except ImportError:
    _av = None
    _HAS_PYAV = False


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
            logger.info("灏濊瘯鍚姩scrcpy杩炴帴 (%d/%d): %s", attempt, max_retries, device_serial)
            try:
                if self._start_scrcpy():
                    self._connected = True
                    self._use_scrcpy = True
                    if self._reconnect_count > 0:
                        self.connection_restored.emit()
                    logger.info("scrcpy杩炴帴鎴愬姛: %s", device_serial)
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

    def _start_scrcpy(self) -> bool:
        opts = self._cast_options
        if opts.skip_push_if_exists and self._remote_jar_matches_local():
            logger.debug("远端 scrcpy-server.jar 大小一致，跳过 push")
        else:
            push_cmd = [
                "adb", "-s", self._device_serial, "push",
                self._server_jar_path, "/data/local/tmp/scrcpy-server.jar"
            ]
            result = subprocess.run(
                push_cmd, capture_output=True, timeout=30,
                creationflags=_SUBPROCESS_FLAGS
            )
            if result.returncode != 0:
                raise RuntimeError(f"推送 scrcpy-server 失败: {result.stderr.decode(errors='replace')}")

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
            raise RuntimeError(f"adb forward 失败: {result.stderr.decode(errors='replace')}")

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
        self._server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_SUBPROCESS_FLAGS
        )

        time.sleep(opts.startup_wait)

        if self._server_process.poll() is not None:
            stderr_output = self._server_process.stderr.read().decode(errors="replace")
            raise RuntimeError(f"scrcpy 服务启动失败: {stderr_output}")

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
            raise RuntimeError("ffmpeg鏈壘鍒帮紝璇风‘淇漟fmpeg宸插畨瑁呭苟娣诲姞鍒癙ATH")

        self._frame_w, self._frame_h = 0, 0

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
        logger.debug("帧解码线程启动 [gen=%d]", gen)
        w = self._frame_w
        h = self._frame_h
        frame_size = w * h * 4
        buf = bytearray()

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
                logger.error("帧解码线程异常 [gen=%d]: %s", gen, e)
        finally:
            logger.debug("帧解码线程结束 [gen=%d]", gen)

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
                        self.frame_captured.emit(frame)
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

            for thread in [self._writer_thread, self._decoder_thread, self._fallback_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=5)

            self._writer_thread = None
            self._decoder_thread = None
            self._fallback_thread = None
            self._av_codec = None

            if self._device_serial:
                subprocess.run(
                    ["adb", "-s", self._device_serial, "forward", "--remove", f"tcp:{self._forward_port}"],
                    capture_output=True, timeout=5,
                    creationflags=_SUBPROCESS_FLAGS
                )


