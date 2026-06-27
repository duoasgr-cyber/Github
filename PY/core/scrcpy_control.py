"""scrcpy 2.0 控制协议注入。

通过独立的 control socket 向设备注入触摸事件（tap/swipe），
延迟约 5~15ms，远低于 `adb shell input` 的 80~150ms。

协议参考 scrcpy 2.0（server 启动参数 version=2.0, control=true）：
    INJECT_TOUCH_EVENT (type=2) 报文体（紧跟 type 字节之后）：
        action        : uint8   (0=DOWN, 1=UP, 2=MOVE)
        pointer_id    : int64   (大端)
        x             : int32   (大端，视频流坐标系)
        y             : int32   (大端，视频流坐标系)
        video_width   : uint16  (大端，当前视频帧宽，server 会校验)
        video_height  : uint16  (大端，当前视频帧高，server 会校验)
        pressure      : uint16  (大端，0xFFFF 表示最大压力)
        action_button : int32   (大端，PRIMARY=1)
        buttons       : int32   (大端，按钮状态)
    总长度 = 1(type) + 1+8+4+4+2+2+2+4+4 = 32 字节

forward 模式下，scrcpy server 在 video socket 之后再 accept 一个连接
作为 control socket；客户端发起第二个 TCP 连接到同一 forward 端口即可。

注意：x/y/video_width/video_height 都是 **视频流分辨率** 坐标系
（受 scrcpy max_size 缩放后的帧尺寸），不是设备物理分辨率。
调用方需先通过 set_video_size() 告知当前视频帧尺寸。
"""
import logging
import socket
import struct
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# scrcpy 控制消息类型
TYPE_INJECT_TOUCH_EVENT = 2

# Android MotionEvent action
ACTION_DOWN = 0
ACTION_UP = 1
ACTION_MOVE = 2

# 报文体格式（不含 type 字节、不含字节序前缀，拼接时统一加 ">")
# B:action q:pointer_id i:x i:y H:video_w H:video_h H:pressure i:action_button i:buttons
_TOUCH_BODY_FMT = "BqiiHHHii"
_TOUCH_BODY_SIZE = struct.calcsize(">" + _TOUCH_BODY_FMT)  # 31（大端无填充）
_TOUCH_MSG_SIZE = 1 + _TOUCH_BODY_SIZE               # 32

# 单指 pointer_id（任意正数即可，同一手势全程保持一致）
_DEFAULT_POINTER_ID = 0x1234567887654321

# 默认压力（满量程）
_PRESSURE_MAX = 0xFFFF

# ACTION_BUTTON / buttons：PRIMARY
_BUTTON_PRIMARY = 1

# swipe 插值步长（视频坐标系像素）与每步间隔
_SWIPE_STEP_PX = 8
_SWIPE_STEP_INTERVAL = 0.008

# control socket 建立重试
_CONTROL_CONNECT_RETRIES = 8
_CONTROL_CONNECT_INTERVAL = 0.25

# 单次 send 超时
_SEND_TIMEOUT = 3.0


class ScrcpyControl:
    """通过 scrcpy 控制协议向设备注入触摸事件。

    线程安全：内部用锁串行化 socket 写入。
    降级：若 control socket 未建立或发送失败，is_available() 返回 False，
    调用方应回退到 `adb shell input`。
    """

    def __init__(self, forward_port: int):
        self._forward_port = forward_port
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._video_size: Tuple[int, int] = (0, 0)  # (width, height)
        self._available = False
        self._closed = False

    # ---- 状态 ----
    def is_available(self) -> bool:
        """control 通道是否可用（已连接且视频尺寸已知）。"""
        return self._available and self._socket is not None and self._video_size != (0, 0)

    def set_video_size(self, width: int, height: int) -> None:
        """设置当前视频帧尺寸（视频流坐标系，非设备物理分辨率）。

        scrcpy server 会校验报文里的 video_width/height，不匹配会丢弃事件，
        因此每次视频帧尺寸变化（如旋转）都必须更新。
        """
        with self._lock:
            self._video_size = (int(width), int(height))
            if self._video_size != (0, 0) and self._socket is not None:
                self._available = True

    def get_video_size(self) -> Tuple[int, int]:
        return self._video_size

    # ---- 连接管理 ----
    def connect(self) -> bool:
        """发起第二个 TCP 连接作为 control socket。

        必须在 video socket 建立之后调用。
        forward 模式下 server 在 video accept 后再 accept control，
        故此处需重试若干次。
        """
        last_err = None
        for attempt in range(1, _CONTROL_CONNECT_RETRIES + 1):
            if self._closed:
                return False
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(_SEND_TIMEOUT)
                sock.connect(("127.0.0.1", self._forward_port))
                sock.settimeout(_SEND_TIMEOUT)
                self._socket = sock
                if self._video_size != (0, 0):
                    self._available = True
                logger.info(
                    "scrcpy control socket 已连接 (port=%d, 尝试 %d/%d)",
                    self._forward_port, attempt, _CONTROL_CONNECT_RETRIES,
                )
                return True
            except (ConnectionRefusedError, OSError) as e:
                last_err = e
                time.sleep(_CONTROL_CONNECT_INTERVAL)

        logger.warning("scrcpy control socket 连接失败，将降级 adb input: %s", last_err)
        self._available = False
        return False

    def close(self) -> None:
        self._closed = True
        self._available = False
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

    # ---- 报文构造 ----
    @staticmethod
    def build_touch_message(
        action: int,
        x: int,
        y: int,
        video_width: int,
        video_height: int,
        pointer_id: int = _DEFAULT_POINTER_ID,
        pressure: int = _PRESSURE_MAX,
        action_button: int = _BUTTON_PRIMARY,
        buttons: int = _BUTTON_PRIMARY,
    ) -> bytes:
        """构造一条 INJECT_TOUCH_EVENT 报文（32 字节）。

        供单测直接调用验证字节布局。
        """
        return struct.pack(
            ">B" + _TOUCH_BODY_FMT,
            TYPE_INJECT_TOUCH_EVENT,
            action,
            pointer_id,
            int(x),
            int(y),
            int(video_width),
            int(video_height),
            int(pressure),
            int(action_button),
            int(buttons),
        )

    def _send(self, message: bytes) -> bool:
        if self._socket is None:
            return False
        try:
            self._socket.sendall(message)
            return True
        except (BrokenPipeError, ConnectionError, OSError) as e:
            logger.warning("scrcpy control 发送失败，标记为不可用: %s", e)
            self._available = False
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            return False

    def _send_touch(
        self, action: int, x: int, y: int,
        pressure: int = _PRESSURE_MAX,
        buttons: int = _BUTTON_PRIMARY,
    ) -> bool:
        vw, vh = self._video_size
        if vw == 0 or vh == 0:
            logger.debug("control 注入跳过：视频尺寸未知")
            return False
        # UP 时 buttons 置 0（语义上无按钮按下）
        if action == ACTION_UP:
            buttons = 0
        msg = self.build_touch_message(
            action, x, y, vw, vh,
            pressure=pressure, buttons=buttons,
        )
        with self._lock:
            return self._send(msg)

    # ---- 高层注入 API ----
    def inject_touch_event(self, action: int, x: int, y: int) -> bool:
        """注入原始触摸事件（ACTION_DOWN/MOVE/UP），用于实时跟随手指。

        坐标为视频流坐标系。control 模式下逐事件注入，延迟最低。
        """
        if not self.is_available():
            return False
        pressure = 0 if action == ACTION_UP else _PRESSURE_MAX
        return self._send_touch(action, x, y, pressure=pressure)

    def inject_tap(self, x: int, y: int) -> bool:
        """注入一次点击：DOWN + 短暂 + UP。坐标为视频流坐标系。"""
        if not self.is_available():
            return False
        ok1 = self._send_touch(ACTION_DOWN, x, y)
        # 短暂保持，模拟真实点击时长
        time.sleep(0.01)
        ok2 = self._send_touch(ACTION_UP, x, y, pressure=0)
        return ok1 and ok2

    def inject_swipe(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        duration: float = 0.3,
    ) -> bool:
        """注入一次滑动：DOWN + 插值 MOVE + UP。坐标为视频流坐标系。

        duration 单位秒；按固定步长插值，步间 sleep，总时长尽量贴近 duration。
        """
        if not self.is_available():
            return False

        if not self._send_touch(ACTION_DOWN, x1, y1):
            return False

        dx = x2 - x1
        dy = y2 - y1
        distance = (dx * dx + dy * dy) ** 0.5
        if distance == 0:
            time.sleep(max(duration, 0.01))
            return self._send_touch(ACTION_UP, x2, y2, pressure=0)

        steps = max(1, int(distance / _SWIPE_STEP_PX))
        # 步间间隔：取 (duration/steps) 与默认间隔的较小者，保证总时长不超 duration 太多
        step_interval = min(_SWIPE_STEP_INTERVAL, duration / steps) if duration > 0 else _SWIPE_STEP_INTERVAL

        for i in range(1, steps + 1):
            t = i / steps
            xi = int(round(x1 + dx * t))
            yi = int(round(y1 + dy * t))
            if not self._send_touch(ACTION_MOVE, xi, yi):
                return False
            if i < steps:
                time.sleep(step_interval)

        return self._send_touch(ACTION_UP, x2, y2, pressure=0)
