"""截图选择器组件 - 基于嵌入式投屏的坐标选择器。

使用 EmbeddedMirrorView 实现高清投屏和坐标选择功能。
"""

import logging
import re
import subprocess
import sys
import threading
import time

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import numpy as np

from ui.components.embedded_mirror_widget import EmbeddedMirrorView

logger = logging.getLogger(__name__)

# Windows 下隐藏子进程控制台窗口
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    _STARTUPINFO = None


class ScreenshotPicker(QWidget):
    """截图选择器 - 嵌入式投屏坐标选择器。"""

    point_selected = pyqtSignal(int, int)
    mouse_moved = pyqtSignal(int, int)
    pickup_completed = pyqtSignal(int, int)  # 选点模式完成（设备坐标）

    # tap 最小间隔（秒），防止快速连击堆积 ADB 命令
    _TAP_MIN_INTERVAL = 0.05

    def __init__(self, screen_capture=None, adb_core=None, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._adb_core = adb_core
        self._connected = False

        # 设备信息
        self._device_serial: str = ""
        self._device_width: int = 0
        self._device_height: int = 0
        self._device_rotation: int = 0

        # 触摸注入（sendevent）
        self._touch_device_path: str = ""  # /dev/input/eventX
        self._touch_device_detected: bool = False
        self._use_sendevent: bool = True   # 优先使用 sendevent
        self._touch_max_x: int = 0         # 触摸设备最大 X 坐标
        self._touch_max_y: int = 0         # 触摸设备最大 Y 坐标
        self._tracking_id: int = 0         # 触摸跟踪 ID

        # 旋转检测定时器
        self._rotation_timer = None
        self._rotation_thread = None

        # 帧轮询定时器（替代信号槽，避免事件队列堆积）
        self._frame_timer: QTimer = None

        # tap 速率限制
        self._last_tap_time: float = 0.0
        self._tap_lock = threading.Lock()

        # tap worker（单线程顺序执行，防止并发 ADB 命令堆积）
        self._tap_pending: bool = False
        self._tap_pending_x: int = 0
        self._tap_pending_y: int = 0
        self._tap_in_flight: bool = False

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 工具栏容器（使用 QWidget 包装以确保正确的层级和高度）
        toolbar_container = QWidget()
        toolbar_container.setFixedHeight(34)
        toolbar_container.setStyleSheet("background-color: #161b22;")
        
        toolbar = QHBoxLayout(toolbar_container)
        toolbar.setContentsMargins(4, 4, 4, 4)
        toolbar.setSpacing(4)

        btn_style = (
            "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; font-size: 12px; "
            "padding: 4px 8px; min-width: 50px; }"
            "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
            "QPushButton:pressed { background-color: #161b22; }"
        )

        self._btn_clear = QPushButton("清除标注")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.setStyleSheet(btn_style)
        self._btn_clear.clicked.connect(self.clear_markers)
        toolbar.addWidget(self._btn_clear)

        self._btn_fit = QPushButton("适配窗口")
        self._btn_fit.setFixedHeight(26)
        self._btn_fit.setStyleSheet(btn_style)
        self._btn_fit.clicked.connect(self._on_fit)
        toolbar.addWidget(self._btn_fit)

        self._btn_1to1 = QPushButton("1:1")
        self._btn_1to1.setFixedHeight(26)
        self._btn_1to1.setStyleSheet(btn_style)
        self._btn_1to1.clicked.connect(self._on_1to1)
        toolbar.addWidget(self._btn_1to1)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setFixedHeight(26)
        self._btn_reset.setStyleSheet(btn_style)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        # 缩放百分比 - 已隐藏
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._zoom_label.setMinimumWidth(40)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        # toolbar.addWidget(self._zoom_label)

        toolbar.addStretch()

        # 校准模式按钮
        self._btn_calibrate = QPushButton("校准模式")
        self._btn_calibrate.setFixedHeight(26)
        self._btn_calibrate.setStyleSheet(btn_style)
        self._btn_calibrate.setCheckable(True)
        self._btn_calibrate.clicked.connect(self._on_calibrate_toggled)
        toolbar.addWidget(self._btn_calibrate)

        # 状态指示 - 已隐藏
        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._status_label.setMinimumWidth(60)
        # toolbar.addWidget(self._status_label)

        layout.addWidget(toolbar_container)

        # 投屏视图
        self._view = EmbeddedMirrorView()
        self._view.point_clicked.connect(self._on_point_clicked)
        self._view.mouse_moved.connect(self._on_mouse_moved)
        self._view.pickup_completed.connect(self._on_pickup_completed)
        layout.addWidget(self._view, stretch=1)

        # 底部信息栏 - 已隐藏
        self._coord_label = QLabel("设备坐标: (-, -)")
        self._coord_label.setFont(QFont("Consolas", 10))
        
        self._resolution_label = QLabel("分辨率: -")
        self._resolution_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        
        self._markers_label = QLabel("标记: 0")
        self._markers_label.setStyleSheet("color: #8b949e; font-size: 11px;")

    def _connect_signals(self):
        """连接信号。"""
        if self._screen_capture:
            # 不连接 frame_captured 信号，改用定时器轮询避免事件队列堆积
            self._screen_capture.connection_lost.connect(self._on_connection_lost)
            self._screen_capture.connection_restored.connect(self._on_connection_restored)

    def _on_frame_captured(self, frame: np.ndarray):
        """接收到新帧（已弃用，改用定时器轮询）。"""
        pass

    def _poll_latest_frame(self):
        """定时轮询最新帧（替代信号槽，避免事件队列堆积）。"""
        if not self._connected or not self._screen_capture:
            return
        frame = self._screen_capture.get_current_frame()
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)
            # 同步分辨率信息（确保与 view 一致）
            h, w = frame.shape[:2]
            if self._device_width == 0 and w > 0:
                self._device_width = w
                self._device_height = h
                # 关键修复：同步设置 view 的设备分辨率，否则 EmbeddedMirrorView._device_width
                # 始终为 0，导致所有点击被忽略（"点击被忽略: _device_width=0"）
                self._view.set_device_resolution(w, h)
            # 如果 view 已通过帧尺寸回退获得分辨率，也同步到自身，
            # 保证后续 tap 发送和坐标显示使用一致的分辨率。
            view_w, view_h = self._view.get_device_resolution()
            if self._device_width == 0 and view_w > 0:
                self._device_width = view_w
                self._device_height = view_h

    def _on_connection_lost(self):
        """连接断开。"""
        self._connected = False
        # self._status_label.setText("断开")
        # self._status_label.setStyleSheet("color: #f85149; font-size: 12px;")

    def _on_connection_restored(self):
        """连接恢复。"""
        self._connected = True
        # self._status_label.setText("已连接")
        # self._status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

    def _on_point_clicked(self, dev_x: int, dev_y: int):
        """普通模式下坐标点击 — 手机响应点击，但不同步坐标到编辑器。"""
        self._coord_label.setText(f"设备坐标: ({dev_x}, {dev_y})")
        # 发送 tap 到手机（普通模式下手机应响应点击）
        self._send_tap_async(dev_x, dev_y)

    def _on_mouse_moved(self, dev_x: int, dev_y: int):
        """鼠标移动。"""
        # self._coord_label.setText(f"设备坐标: ({dev_x}, {dev_y})")
        self.mouse_moved.emit(dev_x, dev_y)

    def _on_pickup_completed(self, dev_x: int, dev_y: int):
        """选点模式下点击完成。"""
        self.pickup_completed.emit(dev_x, dev_y)

    def _update_markers_label(self):
        """更新标记数量显示。"""
        markers = self._view.get_markers()
        # self._markers_label.setText(f"标记: {len(markers)}")

    # -- 工具栏操作 --

    def _on_fit(self):
        """适配窗口。"""
        self._view.fit_to_view()
        self._sync_zoom_label()

    def _on_1to1(self):
        """1:1 显示。"""
        self._view.zoom_to(1.0)
        self._sync_zoom_label()

    def _on_reset(self):
        """重置视图。"""
        self._view.reset_view()
        self._sync_zoom_label()

    def _sync_zoom_label(self):
        """同步缩放标签。"""
        zoom = self._view.get_zoom()
        # self._zoom_label.setText(f"{int(zoom * 100)}%")

    def _on_calibrate_toggled(self, checked: bool):
        """校准模式切换。"""
        self._view.set_calibration_mode(checked)
        if checked:
            self._btn_calibrate.setStyleSheet(
                "QPushButton { background-color: #1f6feb; color: white; "
                "border: 1px solid #30363d; border-radius: 4px; font-size: 12px; "
                "padding: 4px 8px; min-width: 50px; }"
            )
        else:
            self._btn_calibrate.setStyleSheet(
                "QPushButton { background-color: #21262d; border: 1px solid #30363d; "
                "border-radius: 4px; color: #c9d1d9; font-size: 12px; "
                "padding: 4px 8px; min-width: 50px; }"
                "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
                "QPushButton:pressed { background-color: #161b22; }"
            )

    # -- 设备信息 --

    def _detect_device_resolution(self):
        """异步获取设备分辨率。"""
        if not self._device_serial:
            return

        def _detect():
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "wm", "size"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO
                )
                if result.returncode != 0:
                    logger.warning("wm size 命令失败: %s", result.stderr.strip())
                    return

                lines = result.stdout.strip().splitlines()
                override_w, override_h = 0, 0
                physical_w, physical_h = 0, 0
                for line in lines:
                    match = re.search(r"(\d+)x(\d+)", line)
                    if match:
                        w, h = int(match.group(1)), int(match.group(2))
                        if "Override" in line:
                            override_w, override_h = w, h
                        elif "Physical" in line:
                            physical_w, physical_h = w, h

                # 优先使用 Override size（存在时代表当前实际显示分辨率）
                if override_w > 0 and override_h > 0:
                    width, height = override_w, override_h
                elif physical_w > 0 and physical_h > 0:
                    width, height = physical_w, physical_h
                else:
                    logger.warning("wm size 输出无法解析: %s", result.stdout.strip())
                    return

                QTimer.singleShot(0, lambda: self._apply_resolution(width, height))

            except Exception as e:
                logger.debug("获取分辨率失败: %s", e)

        threading.Thread(target=_detect, daemon=True, name="resolution-detect").start()

    def _apply_resolution(self, width: int, height: int):
        """在主线程中应用设备分辨率。"""
        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        logger.info("设备分辨率: %dx%d", width, height)

    # -- 旋转检测 --

    def _start_rotation_detection(self):
        """启动旋转检测定时器。"""
        if self._rotation_timer:
            return
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._check_rotation)
        self._rotation_timer.start(2000)  # 每 2 秒检测一次

    def _stop_rotation_detection(self):
        """停止旋转检测定时器。"""
        if self._rotation_timer:
            self._rotation_timer.stop()
            self._rotation_timer = None

    def _check_rotation(self):
        """检测设备旋转状态（异步：在后台线程执行 ADB 命令）。"""
        if not self._connected or not self._device_serial:
            return
        if self._rotation_thread is not None and self._rotation_thread.is_alive():
            return

        def _detect():
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device_serial, "shell", "dumpsys", "input"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=_NO_WINDOW,
                    startupinfo=_STARTUPINFO
                )
                match = re.search(r"SurfaceOrientation:\s*(\d)", result.stdout)
                if match:
                    new_rotation = int(match.group(1))
                    QTimer.singleShot(0, lambda: self._on_rotation_detected(new_rotation))
            except Exception as e:
                logger.debug("检测旋转失败: %s", e)

        self._rotation_thread = threading.Thread(
            target=_detect, daemon=True, name="rotation-check"
        )
        self._rotation_thread.start()

    def _on_rotation_detected(self, new_rotation: int):
        """旋转检测回调（主线程）。"""
        if new_rotation != self._device_rotation:
            old = self._device_rotation
            self._device_rotation = new_rotation
            logger.info("设备旋转: %d -> %d", old, new_rotation)

            # 旋转 0/2 = 竖屏, 1/3 = 横屏；方向类别变化时交换宽高
            if (old in (0, 2)) != (new_rotation in (0, 2)):
                self._device_width, self._device_height = (
                    self._device_height, self._device_width
                )
                self._view.set_device_resolution(
                    self._device_width, self._device_height
                )

            # 自动适配
            QTimer.singleShot(100, self._on_fit)

    # -- 触摸设备检测 --

    def _detect_touch_device(self):
        """检测设备的触摸输入设备路径（用于 sendevent 注入）。

        通过 getevent -pl 获取触摸设备信息，找到支持 ABS_MT_POSITION_X/Y 的设备。
        需要 root 权限才能使用 sendevent 写入。
        """
        if not self._device_serial or self._touch_device_detected:
            return

        try:
            result = subprocess.run(
                ["adb", "-s", self._device_serial, "shell", "getevent", "-pl"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )

            if result.returncode != 0:
                logger.debug("getevent -pl 失败: %s", result.stderr.strip())
                self._use_sendevent = False
                return

            # 解析输出，找到触摸设备
            current_device = None
            has_mt_x = False
            has_mt_y = False
            max_x = 0
            max_y = 0

            for line in result.stdout.splitlines():
                device_match = re.match(r"add device \d+: (/dev/input/event\d+)", line)
                if device_match:
                    if current_device and has_mt_x and has_mt_y:
                        self._touch_device_path = current_device
                        self._touch_max_x = max_x
                        self._touch_max_y = max_y
                        self._touch_device_detected = True
                        logger.info(
                            "检测到触摸设备: %s (max: %dx%d)",
                            current_device, max_x, max_y
                        )
                        return

                    current_device = device_match.group(1)
                    has_mt_x = False
                    has_mt_y = False
                    max_x = 0
                    max_y = 0
                    continue

                if "ABS_MT_POSITION_X" in line:
                    has_mt_x = True
                    max_match = re.search(r"max (\d+)", line)
                    if max_match:
                        max_x = int(max_match.group(1))

                if "ABS_MT_POSITION_Y" in line:
                    has_mt_y = True
                    max_match = re.search(r"max (\d+)", line)
                    if max_match:
                        max_y = int(max_match.group(1))

            # 检查最后一个设备
            if current_device and has_mt_x and has_mt_y:
                self._touch_device_path = current_device
                self._touch_max_x = max_x
                self._touch_max_y = max_y
                self._touch_device_detected = True
                logger.info(
                    "检测到触摸设备: %s (max: %dx%d)",
                    current_device, max_x, max_y
                )
            else:
                logger.debug("未找到触摸输入设备，将使用 input tap")
                self._use_sendevent = False

        except Exception as e:
            logger.debug("检测触摸设备失败: %s", e)
            self._use_sendevent = False

    def _sendevent_tap(self, x: int, y: int) -> bool:
        """使用 sendevent 发送触摸事件（绕过 Android 输入过滤）。

        直接写入内核输入设备，需要 root 权限。
        """
        if not self._touch_device_path or not self._touch_device_detected:
            return False

        try:
            # 将设备坐标映射到触摸设备坐标
            if self._touch_max_x > 0 and self._touch_max_y > 0:
                touch_x = int(x * self._touch_max_x / self._device_width)
                touch_y = int(y * self._touch_max_y / self._device_height)
            else:
                touch_x = x
                touch_y = y

            # 限制坐标范围
            touch_x = max(0, min(touch_x, self._touch_max_x if self._touch_max_x > 0 else self._device_width))
            touch_y = max(0, min(touch_y, self._touch_max_y if self._touch_max_y > 0 else self._device_height))

            # 递增跟踪 ID
            self._tracking_id = (self._tracking_id + 1) % 65535

            dev = self._touch_device_path

            # 构建触摸事件命令（使用 su 提权）
            events = [
                # 触摸按下
                f"sendevent {dev} 3 57 {self._tracking_id}",  # EV_ABS ABS_MT_TRACKING_ID
                f"sendevent {dev} 3 53 {touch_x}",            # EV_ABS ABS_MT_POSITION_X
                f"sendevent {dev} 3 54 {touch_y}",            # EV_ABS ABS_MT_POSITION_Y
                f"sendevent {dev} 1 330 1",                   # EV_KEY BTN_TOUCH
                f"sendevent {dev} 0 0 0",                     # EV_SYN SYN_REPORT
                # 触摸抬起
                f"sendevent {dev} 3 57 -1",                   # EV_ABS ABS_MT_TRACKING_ID (释放)
                f"sendevent {dev} 1 330 0",                   # EV_KEY BTN_TOUCH
                f"sendevent {dev} 0 0 0",                     # EV_SYN SYN_REPORT
            ]

            # 使用 su -c 执行所有事件（需要 root 权限）
            shell_cmd = " && ".join(events)
            su_cmd = f'su -c "{shell_cmd}"'

            cmd = ["adb", "-s", self._device_serial, "shell", su_cmd]
            result = subprocess.run(
                cmd, capture_output=True, timeout=5,
                creationflags=_NO_WINDOW,
                startupinfo=_STARTUPINFO
            )

            success = (result.returncode == 0)
            if success:
                logger.debug("sendevent tap 成功: (%d, %d) -> (%d, %d)", x, y, touch_x, touch_y)
            else:
                stderr_msg = result.stderr.decode(errors='replace')[:200]
                logger.warning("sendevent tap 失败: %s", stderr_msg)
                # 如果是权限问题，禁用 sendevent
                if "Permission denied" in stderr_msg or "su:" in stderr_msg:
                    logger.info("设备无 root 权限，禁用 sendevent，回退到 input tap")
                    self._use_sendevent = False

            return success

        except Exception as e:
            logger.warning("sendevent tap 异常: %s", e)
            return False

    # -- tap 注入 --

    def _send_tap_async(self, x: int, y: int):
        """通过 adb 异步发送点击事件到设备（单 worker 线程顺序执行）。

        优先使用 sendevent（绕过 Android 输入过滤），失败则回退到多种 input 命令。
        使用单线程 worker 防止并发 ADB 命令堆积导致设备无响应。
        """
        # 前置条件检查
        if not self._device_serial:
            logger.warning("tap 跳过: device_serial 为空, 坐标=(%d,%d)", x, y)
            return

        logger.debug(
            "tap 请求: (%d,%d), 设备=%s, 分辨率=%dx%d, 旋转=%d°",
            x, y, self._device_serial,
            self._device_width, self._device_height,
            self._device_rotation,
        )

        # 速率限制：防止快速连击堆积 ADB 命令
        now = time.monotonic()
        with self._tap_lock:
            if now - self._last_tap_time < self._TAP_MIN_INTERVAL:
                logger.debug("tap 被限流: 距上次 %.3fs < %.3fs",
                             now - self._last_tap_time, self._TAP_MIN_INTERVAL)
                return
            self._last_tap_time = now
            # 更新待执行的点击坐标（快速连续点击只保留最新）
            self._tap_pending_x = x
            self._tap_pending_y = y
            self._tap_pending = True
            # 如果 worker 线程已在运行，只需更新坐标，不创建新线程
            if self._tap_in_flight:
                return
            self._tap_in_flight = True

        threading.Thread(
            target=self._tap_worker, daemon=True, name="tap-worker"
        ).start()

    def _tap_worker(self):
        """单线程 tap worker，顺序处理所有待执行的点击。"""
        while True:
            with self._tap_lock:
                if not self._tap_pending:
                    self._tap_in_flight = False
                    return
                x = self._tap_pending_x
                y = self._tap_pending_y
                self._tap_pending = False

            self._execute_single_tap(x, y)

    def _execute_single_tap(self, x: int, y: int):
        """执行单次 tap 注入（在 worker 线程中调用）。"""
        success = False
        method = "unknown"

        try:
            # 优先使用 sendevent（绕过应用过滤）
            if self._use_sendevent and self._touch_device_detected:
                method = "sendevent"
                success = self._sendevent_tap(x, y)

            # sendevent 失败或不可用时，尝试多种 input 命令
            if not success:
                method = "input"
                serial = self._device_serial
                methods = [
                    (["input", "touchscreen", "tap", str(x), str(y)], "input touchscreen tap"),
                    (["input", "tap", str(x), str(y)], "input tap"),
                    (["input", "motionevent", "DOWN", str(x), str(y), "&&",
                      "input", "motionevent", "UP", str(x), str(y)], "input motionevent"),
                ]

                for args, method_name in methods:
                    try:
                        if self._adb_core:
                            result = self._adb_core.execute(
                                ["shell"] + args, device=serial, timeout=5
                            )
                        else:
                            cmd = ["adb", "-s", serial, "shell"] + args
                            result = subprocess.run(
                                cmd, capture_output=True, timeout=5,
                                creationflags=_NO_WINDOW,
                                startupinfo=_STARTUPINFO
                            )
                        if result.returncode == 0:
                            success = True
                            method = method_name
                            logger.debug("tap 成功 (%s): (%d, %d)", method_name, x, y)
                            break
                        else:
                            logger.debug("%s 失败(rc=%d)，尝试下一种", method_name, result.returncode)
                    except Exception as e:
                        logger.debug("%s 异常: %s，尝试下一种", method_name, e)
                        continue

            if not success:
                logger.warning("tap 失败 (所有方式均失败): (%d, %d), 设备=%s", x, y, self._device_serial)

        except Exception as e:
            logger.warning("tap 发送异常: (%d, %d) %s", x, y, e)

    # -- 公开接口 --

    def set_screen_capture(self, screen_capture):
        """设置屏幕采集对象。"""
        self._screen_capture = screen_capture
        self._connect_signals()

    def start(self, serial: str):
        """启动投屏。"""
        self._device_serial = serial
        self._connected = True

        # 检测设备分辨率
        self._detect_device_resolution()

        # 检测触摸输入设备（用于 sendevent）
        self._detect_touch_device()

        # 启动旋转检测
        self._start_rotation_detection()

        # 启动帧轮询定时器（~30fps）
        if not self._frame_timer:
            self._frame_timer = QTimer(self)
            self._frame_timer.timeout.connect(self._poll_latest_frame)
            self._frame_timer.start(33)

    def stop(self):
        """停止投屏。"""
        self._connected = False
        # self._status_label.setText("未连接")
        # self._status_label.setStyleSheet("color: #8b949e; font-size: 12px;")

        # 停止帧轮询
        if self._frame_timer:
            self._frame_timer.stop()
            self._frame_timer = None

        # 停止旋转检测
        self._stop_rotation_detection()

    def capture_and_display(self):
        """兼容旧接口 - 现在是实时投屏，无需手动截屏。"""
        pass

    def clear_markers(self):
        """清除所有标记。"""
        self._view.clear_markers()
        # self._coord_label.setText("设备坐标: (-, -)")
        # self._update_markers_label()

    def get_selected_point(self):
        """获取选中的坐标点。"""
        return self._view.get_active_marker()

    def set_calibration_mode(self, enabled: bool):
        """设置校准模式。"""
        self._btn_calibrate.setChecked(enabled)
        self._on_calibrate_toggled(enabled)

    def set_base_resolution(self, width: int, height: int):
        """设置设备分辨率（外部调用）。"""
        self._device_width = width
        self._device_height = height
        self._view.set_device_resolution(width, height)
        # self._resolution_label.setText(f"分辨率: {width}x{height}")

    def update_frame(self, frame: np.ndarray):
        """更新帧（外部调用）。"""
        if frame is not None and frame.size > 0:
            self._view.update_frame(frame)

    def enter_pickup_mode(self):
        """进入坐标选择模式 — 投屏变灰，等待用户点击。"""
        self._view.set_pickup_mode(True)

    def exit_pickup_mode(self):
        """退出坐标选择模式 — 恢复正常显示。"""
        self._view.set_pickup_mode(False)
