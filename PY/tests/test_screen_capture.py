"""screen_capture.py 单元测试。

测试 scrcpy + screencap 双模式采集的各条路径。
不依赖 pytest-qt，手动创建 QApplication 处理信号。
"""

import os
import subprocess
import sys
import threading
import time
from unittest import mock
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# 项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 确保 QApplication 存在（PyQt5 要求在创建 QObject 前有 QApplication）
from PyQt5.QtWidgets import QApplication

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

from core.screen_capture import _DEFAULT_SERVER_JAR, ScrcpyCapture

# =========================================================================
#  Fixtures
# =========================================================================


@pytest.fixture
def capture():
    """创建 ScrcpyCapture 实例。"""
    cap = ScrcpyCapture()
    yield cap
    # teardown
    try:
        if cap.is_running():
            cap.stop()
    except Exception:
        pass


@pytest.fixture
def fake_frame():
    """返回一个假的 BGR numpy 帧。"""
    return np.zeros((100, 200, 3), dtype=np.uint8)


# =========================================================================
#  基本属性测试
# =========================================================================


class TestBasicProperties:
    def test_initial_state(self, capture):
        assert not capture.is_running()
        assert not capture.is_connected()
        assert capture.get_current_frame() is None

    def test_set_current_frame_caches_and_copies(self, capture, fake_frame):
        """set_current_frame 缓存帧，get_current_frame 返回拷贝。"""
        capture.set_current_frame(fake_frame)
        result = capture.get_current_frame()
        assert result is not None
        assert result.shape == fake_frame.shape
        # 修改返回值不影响缓存
        result[:] = 255
        result2 = capture.get_current_frame()
        assert not np.array_equal(result2, np.full_like(fake_frame, 255))


# =========================================================================
#  Scrcpy 启动失败 → 回退 screencap
# =========================================================================


class TestScrcpyFailureFallback:
    """测试 scrcpy 启动失败时自动回退到 screencap。"""

    @patch("core.screen_capture.os.path.isfile", return_value=False)
    def test_no_jar_skips_scrcpy(self, mock_isfile, capture):
        """JAR 文件不存在时 _try_start_scrcpy 返回 False。"""
        result = capture._try_start_scrcpy()
        assert result is False

    @patch("core.screen_capture.os.path.isfile", return_value=True)
    @patch("subprocess.run")
    def test_push_failure_returns_false(self, mock_run, mock_isfile, capture):
        """adb push 失败时 _try_start_scrcpy 返回 False。"""
        push_result = MagicMock()
        push_result.returncode = 1
        push_result.stderr = "push failed"
        push_result.stdout = ""
        mock_run.return_value = push_result

        result = capture._try_start_scrcpy()
        assert result is False


# =========================================================================
#  stop() 资源清理测试
# =========================================================================


class TestStopCleanup:
    def test_stop_clears_state(self, capture, fake_frame):
        """stop() 后所有状态被重置。"""
        capture.set_current_frame(fake_frame)
        capture._running = True
        capture._connected = True

        capture.stop()

        assert not capture.is_running()
        assert not capture.is_connected()
        assert capture.get_current_frame() is None

    def test_stop_terminates_server_process(self, capture):
        """stop() 终止 server 子进程。"""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = 0
        capture._server_process = mock_proc
        capture._running = True

        capture.stop()

        mock_proc.terminate.assert_called()

    def test_stop_cleans_up_port_forward(self, capture):
        """stop() 清理 adb forward 端口。"""
        capture._serial = "test-device"
        capture._local_port = 27183
        capture._running = True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            capture.stop()

        assert capture._local_port == 0

    def test_stop_cleans_up_resources(self, capture):
        """stop() 清理所有资源（不再使用 ffmpeg 子进程，改用 PyAV 进程内解码）。"""
        capture._running = True

        capture.stop()

        # 验证 socket 和 server 进程被清理
        assert capture._video_socket is None
        assert capture._server_process is None

    def test_stop_closes_socket(self, capture):
        """stop() 关闭 video socket。"""
        mock_sock = MagicMock()
        capture._video_socket = mock_sock
        capture._running = True

        capture.stop()

        mock_sock.close.assert_called()
        assert capture._video_socket is None


# =========================================================================
#  连接状态信号测试
# =========================================================================


class TestConnectionSignals:
    def test_connection_lost_emitted(self, capture):
        """断连时 emit connection_lost。"""
        received = threading.Event()
        capture.connection_lost.connect(lambda: received.set())

        capture._set_connected(True)
        capture._set_connected(False)

        assert received.wait(timeout=2.0), "connection_lost 信号未 emit"

    def test_connection_restored_emitted(self, capture):
        """恢复时 emit connection_restored。"""
        received = threading.Event()
        capture.connection_restored.connect(lambda: received.set())

        capture._set_connected(True)

        assert received.wait(timeout=2.0), "connection_restored 信号未 emit"

    def test_set_connected_no_duplicate_emit(self, capture):
        """连续两次 set_connected(True) 只 emit 一次 connection_restored。"""
        count = {"value": 0}

        def on_restored():
            count["value"] += 1

        capture.connection_restored.connect(on_restored)

        capture._set_connected(True)
        capture._set_connected(True)
        # 处理信号
        _app.processEvents()
        time.sleep(0.1)
        _app.processEvents()

        assert count["value"] == 1

    def test_set_connected_no_emit_on_same_state(self, capture):
        """状态不变时不 emit 信号。"""
        count = {"lost": 0, "restored": 0}
        capture.connection_lost.connect(lambda: count.__setitem__("lost", count["lost"] + 1))
        capture.connection_restored.connect(lambda: count.__setitem__("restored", count["restored"] + 1))

        # 初始状态是 False，再次设 False 不应 emit
        capture._set_connected(False)
        _app.processEvents()
        assert count["lost"] == 0


# =========================================================================
#  frame_captured 信号测试
# =========================================================================


class TestFrameSignal:
    def test_set_current_frame_no_longer_emits_signal(self, capture, fake_frame):
        """set_current_frame 不再 emit frame_captured 信号（避免重帧数据传递）。

        frame_captured 信号携带帧数据，高频 emit 会导致 Qt 事件队列堆积。
        新行为：frame_ready 信号（无参数）通知 UI，UI 通过版本号拉取帧。
        """
        received = {"frame": None, "count": 0}

        def on_frame(frame):
            received["frame"] = frame
            received["count"] += 1

        capture.frame_captured.connect(on_frame)

        capture.set_current_frame(fake_frame)
        _app.processEvents()

        # frame_captured 信号不应被 emit
        assert received["count"] == 0

    def test_set_current_frame_emits_frame_ready(self, capture, fake_frame):
        """set_current_frame 应 emit frame_ready 信号（信号驱动帧更新）。

        frame_ready 是无参数信号，UI 收到后通过 get_current_frame_if_new() 拉取帧。
        这替代了固定间隔轮询，将显示唤醒延迟从 0~8ms 降到 ~0ms。
        """
        ready_count = {"value": 0}

        def on_ready():
            ready_count["value"] += 1

        capture.frame_ready.connect(on_ready)

        capture.set_current_frame(fake_frame)
        _app.processEvents()

        # frame_ready 信号应被 emit
        assert ready_count["value"] == 1


# =========================================================================
#  set_device 测试
# =========================================================================


class TestSetDevice:
    def test_set_device_restarts(self, capture):
        """set_device 在运行时先 stop 再 start。"""
        with patch.object(capture, "stop") as mock_stop, patch.object(capture, "start") as mock_start:
            capture._running = True
            capture.set_device("new-device")
            mock_stop.assert_called_once()
            mock_start.assert_called_once_with("new-device")


# =========================================================================
#  screencap 回退模式测试
# =========================================================================


class TestScreencapMode:
    def test_capture_screencap_returns_frame(self, capture, fake_frame):
        """screencap 截屏成功返回 numpy 数组。"""
        import cv2

        _, png_data = cv2.imencode(".png", fake_frame)
        png_bytes = png_data.tobytes()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = png_bytes

        with patch("subprocess.run", return_value=mock_result):
            frame = capture._capture_screencap()

        assert frame is not None
        assert frame.shape == fake_frame.shape

    def test_capture_screencap_failure_returns_none(self, capture):
        """screencap 失败时返回 None。"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""

        with patch("subprocess.run", return_value=mock_result):
            frame = capture._capture_screencap()

        assert frame is None

    def test_capture_screencap_timeout_returns_none(self, capture):
        """screencap 超时时返回 None。"""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            frame = capture._capture_screencap()

        assert frame is None

    def test_capture_screencap_empty_output_returns_none(self, capture):
        """screencap 返回空数据时返回 None。"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""

        with patch("subprocess.run", return_value=mock_result):
            frame = capture._capture_screencap()

        assert frame is None


# =========================================================================
#  默认路径测试
# =========================================================================


class TestDefaultPaths:
    def test_default_server_jar_path(self):
        """默认 JAR 路径指向 lib/scrcpy-server.jar。"""
        assert "lib" in _DEFAULT_SERVER_JAR
        assert _DEFAULT_SERVER_JAR.endswith("scrcpy-server.jar")

    def test_start_with_none_jar_uses_default(self, capture):
        """start(server_jar_path=None) 使用默认路径。"""
        with patch.object(capture, "_capture_loop"):
            capture.start(serial="test", server_jar_path=None)
        assert capture._server_jar == _DEFAULT_SERVER_JAR
        capture.stop()

    def test_start_with_empty_jar_uses_default(self, capture):
        """start(server_jar_path='') 使用默认路径。"""
        with patch.object(capture, "_capture_loop"):
            capture.start(serial="test", server_jar_path="")
        assert capture._server_jar == _DEFAULT_SERVER_JAR
        capture.stop()


# =========================================================================
#  幂等性测试
# =========================================================================


class TestIdempotency:
    def test_double_start_does_not_crash(self, capture):
        """重复 start 不会崩溃。"""
        with patch.object(capture, "_capture_loop"):
            capture.start(serial="test1")
            capture.start(serial="test2")
        assert capture._serial == "test2"
        capture.stop()

    def test_double_stop_is_safe(self, capture):
        """重复 stop 不会抛异常。"""
        capture.stop()
        capture.stop()  # 不应抛异常

    def test_stop_when_never_started(self, capture):
        """从未 start 过时调用 stop 不会抛异常。"""
        capture.stop()


# =========================================================================
#  interruptible_sleep 测试
# =========================================================================


class TestInterruptibleSleep:
    def test_returns_true_on_normal_completion(self, capture):
        """正常完成返回 True。"""
        capture._running = True
        result = capture._interruptible_sleep(0.05)
        assert result is True

    def test_returns_false_when_stopped(self, capture):
        """被停止信号中断返回 False。"""
        capture._running = True

        def stop_later():
            time.sleep(0.02)
            capture._running = False

        t = threading.Thread(target=stop_later)
        t.start()
        result = capture._interruptible_sleep(1.0)
        t.join()
        assert result is False


# =========================================================================
#  连接 Socket 测试
# =========================================================================


class TestConnectSocket:
    def test_connect_socket_returns_none_when_not_running(self, capture):
        """_running=False 时 _connect_socket 返回 None。"""
        capture._running = False
        result = capture._connect_socket()
        assert result is None

    @patch("socket.socket")
    def test_connect_socket_retries_on_refused(self, mock_socket_cls):
        """连接被拒绝时重试直到超时。"""
        capture = ScrcpyCapture()
        capture._running = True
        capture._local_port = 27183

        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError()
        mock_socket_cls.return_value = mock_sock

        # 使用很短的超时
        with patch("core.screen_capture._SCRCPY_CONNECT_TIMEOUT", 0.3):
            result = capture._connect_socket()

        assert result is None
        # 验证确实重试了
        assert mock_sock.connect.call_count >= 1


# =========================================================================
#  帧率优化测试（TDD: 先写失败测试，再实现优化）
# =========================================================================


class TestFrameSkipping:
    """测试 _scrcpy_read_loop 中的帧跳过逻辑。"""

    def test_set_current_frame_only_keeps_latest_frame(self, capture, fake_frame):
        """连续调用 set_current_frame 时，get_current_frame 只返回最新帧。"""
        frame1 = np.ones((100, 200, 3), dtype=np.uint8) * 10
        frame2 = np.ones((100, 200, 3), dtype=np.uint8) * 20
        frame3 = np.ones((100, 200, 3), dtype=np.uint8) * 30

        capture.set_current_frame(frame1)
        capture.set_current_frame(frame2)
        capture.set_current_frame(frame3)

        result = capture.get_current_frame()
        assert result is not None
        # 应该返回最后一帧的值
        assert result[0, 0, 0] == 30

    def test_frame_version_increments_on_update(self, capture, fake_frame):
        """帧版本号在每次更新时递增，用于 UI 判断是否有新帧。"""
        # 初始版本号应为 0
        assert capture.get_frame_version() == 0

        capture.set_current_frame(fake_frame)
        assert capture.get_frame_version() == 1

        capture.set_current_frame(fake_frame)
        assert capture.get_frame_version() == 2

    def test_get_current_frame_no_copy_when_version_unchanged(self, capture, fake_frame):
        """当帧版本未变时，get_current_frame 返回 None（避免重复渲染）。"""
        capture.set_current_frame(fake_frame)
        # 第一次获取：有新帧
        result1 = capture.get_current_frame_if_new(last_version=0)
        assert result1 is not None

        # 第二次获取：版本未变，返回 None
        result2 = capture.get_current_frame_if_new(last_version=capture.get_frame_version())
        assert result2 is None


class TestFramePollingInterval:
    """测试帧轮询间隔优化。"""

    def test_mirror_window_frame_interval_is_100ms_fallback(self):
        """MirrorWindow 帧定时器应为 100ms fallback（信号驱动为主）。

        原 16ms 高频轮询已被 frame_ready 信号驱动替代，
        定时器仅作为 fallback 防止信号丢失时画面停滞。
        """
        import inspect

        from ui.mirror_window import MirrorWindow

        source = inspect.getsource(MirrorWindow.start)
        # 信号驱动 + 100ms fallback
        assert "frame_ready" in source, "MirrorWindow 应连接 frame_ready 信号"
        assert "100" in source, "MirrorWindow fallback 定时器应为 100ms"

    def test_embedded_mirror_uses_frame_ready_signal(self):
        """EmbeddedMirrorWidget 应使用 frame_ready 信号驱动帧更新。

        原 8ms 高频轮询已被 frame_ready 信号驱动替代，
        定时器仅作为 100ms fallback。
        """
        import inspect

        from ui.components.embedded_mirror_widget import EmbeddedMirrorWidget

        source_connect = inspect.getsource(EmbeddedMirrorWidget._connect_signals)
        assert "frame_ready" in source_connect, "EmbeddedMirrorWidget 应连接 frame_ready 信号"

        source_timer = inspect.getsource(EmbeddedMirrorWidget._start_frame_update)
        assert "100" in source_timer, "EmbeddedMirrorWidget fallback 定时器应为 100ms"


class TestNoRgbSwapped:
    """测试 EmbeddedMirrorView 不再使用 rgbSwapped()。"""

    def test_embedded_mirror_view_no_rgb_swapped(self):
        """EmbeddedMirrorView.update_frame 不应调用 .rgbSwapped() 方法。"""
        import inspect

        from ui.components.embedded_mirror_widget import EmbeddedMirrorView

        source = inspect.getsource(EmbeddedMirrorView.update_frame)
        assert (
            ".rgbSwapped()" not in source
        ), "EmbeddedMirrorView.update_frame 不应调用 .rgbSwapped()，PyAV 输出已是 RGB"


class TestNoFrameCapturedSignalEmission:
    """测试 set_current_frame 不 emit frame_captured 信号（改用 frame_ready）。"""

    def test_set_current_frame_does_not_emit_signal(self, capture, fake_frame):
        """set_current_frame 不应 emit frame_captured 信号（携带帧数据，高频会堆积）。

        frame_ready（无参数）信号替代 frame_captured 用于通知 UI。
        """
        signal_count = {"value": 0}

        def on_frame(frame):
            signal_count["value"] += 1

        capture.frame_captured.connect(on_frame)

        capture.set_current_frame(fake_frame)
        _app.processEvents()
        time.sleep(0.05)
        _app.processEvents()

        # frame_captured 不应被 emit
        assert signal_count["value"] == 0, "set_current_frame 不应 emit frame_captured"


class TestGetFrameVersion:
    """测试帧版本号机制。"""

    def test_initial_version_is_zero(self, capture):
        """初始帧版本号为 0。"""
        assert capture.get_frame_version() == 0

    def test_version_increments_on_each_frame(self, capture):
        """每次 set_current_frame 版本号递增。"""
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        for i in range(5):
            capture.set_current_frame(frame)
        assert capture.get_frame_version() == 5

    def test_get_current_frame_if_new_returns_frame_on_new_version(self, capture, fake_frame):
        """有新帧时 get_current_frame_if_new 返回帧和版本号。"""
        capture.set_current_frame(fake_frame)
        result = capture.get_current_frame_if_new(last_version=0)
        assert result is not None
        frame, version = result
        assert frame is not None
        assert version == 1

    def test_get_current_frame_if_new_returns_none_on_same_version(self, capture, fake_frame):
        """版本号未变时 get_current_frame_if_new 返回 None。"""
        capture.set_current_frame(fake_frame)
        current_version = capture.get_frame_version()
        result = capture.get_current_frame_if_new(last_version=current_version)
        assert result is None

    def test_get_current_frame_if_new_returns_reference_not_copy(self, capture, fake_frame):
        """get_current_frame_if_new 返回内部引用而非拷贝（性能优化）。

        消除 1080×2400 RGB 帧 ~7.4MB/帧 的内存拷贝。
        采集线程每次生成新数组，UI 只读不写，返回引用是安全的。
        """
        capture.set_current_frame(fake_frame)
        result = capture.get_current_frame_if_new(last_version=0)
        assert result is not None
        frame, version = result
        # 返回的应是同一个 numpy 数组对象（引用，非拷贝）
        assert frame is fake_frame, "get_current_frame_if_new 应返回引用而非拷贝"
