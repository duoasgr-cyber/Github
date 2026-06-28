"""ScrcpyControl 报文构造与状态单元测试。

验证 scrcpy 2.0 INJECT_TOUCH_EVENT 报文的字节布局（32 字节），
以及 ScrcpyControl 的连接状态管理逻辑。
"""
import struct
import socket
import threading
import unittest
from unittest import mock

from core.scrcpy_control import (
    ScrcpyControl,
    TYPE_INJECT_TOUCH_EVENT,
    ACTION_DOWN,
    ACTION_MOVE,
    ACTION_UP,
    _TOUCH_BODY_FMT,
    _TOUCH_BODY_SIZE,
    _TOUCH_MSG_SIZE,
    _DEFAULT_POINTER_ID,
    _PRESSURE_MAX,
    _BUTTON_PRIMARY,
)


class TestTouchMessageLayout(unittest.TestCase):
    """验证 32 字节报文的精确字节布局。"""

    def test_message_size_is_32_bytes(self):
        """报文总长度必须恰好 32 字节（1 type + 31 body）。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 100, 200, 1080, 1920
        )
        self.assertEqual(len(msg), 32)
        self.assertEqual(_TOUCH_MSG_SIZE, 32)
        self.assertEqual(_TOUCH_BODY_SIZE, 31)

    def test_type_byte_is_inject_touch_event(self):
        """第一个字节必须是 2 (TYPE_INJECT_TOUCH_EVENT)。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920
        )
        self.assertEqual(msg[0], TYPE_INJECT_TOUCH_EVENT)
        self.assertEqual(msg[0], 2)

    def test_action_byte_at_offset_1(self):
        """action 在偏移 1：0=DOWN, 1=UP, 2=MOVE。"""
        for action in (ACTION_DOWN, ACTION_UP, ACTION_MOVE):
            msg = ScrcpyControl.build_touch_message(
                action, 10, 20, 1080, 1920
            )
            self.assertEqual(msg[1], action)

    def test_pointer_id_big_endian_at_offset_2(self):
        """pointer_id: int64 大端，偏移 2。"""
        pid = 0x1234567887654321
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920, pointer_id=pid
        )
        unpacked = struct.unpack(">q", msg[2:10])[0]
        self.assertEqual(unpacked, pid)

    def test_xy_coordinates_big_endian(self):
        """x: int32 大端偏移 10, y: int32 大端偏移 14。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 540, 960, 1080, 1920
        )
        x = struct.unpack(">i", msg[10:14])[0]
        y = struct.unpack(">i", msg[14:18])[0]
        self.assertEqual(x, 540)
        self.assertEqual(y, 960)

    def test_video_dimensions_uint16_big_endian(self):
        """video_width: uint16 偏移 18, video_height: uint16 偏移 20。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920
        )
        vw = struct.unpack(">H", msg[18:20])[0]
        vh = struct.unpack(">H", msg[20:22])[0]
        self.assertEqual(vw, 1080)
        self.assertEqual(vh, 1920)

    def test_pressure_uint16_big_endian(self):
        """pressure: uint16 偏移 22。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920, pressure=0x8000
        )
        p = struct.unpack(">H", msg[22:24])[0]
        self.assertEqual(p, 0x8000)

    def test_action_button_int32_big_endian(self):
        """action_button: int32 大端偏移 24。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920, action_button=1
        )
        ab = struct.unpack(">i", msg[24:28])[0]
        self.assertEqual(ab, 1)

    def test_buttons_int32_big_endian(self):
        """buttons: int32 大端偏移 28。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_DOWN, 0, 0, 1080, 1920, buttons=1
        )
        btns = struct.unpack(">i", msg[28:32])[0]
        self.assertEqual(btns, 1)

    def test_full_unpack_matches_spec(self):
        """完整解包验证所有字段。"""
        msg = ScrcpyControl.build_touch_message(
            ACTION_MOVE, 333, 777, 720, 1280,
            pointer_id=42, pressure=0xC000, action_button=1, buttons=1,
        )
        # 手动按协议解包
        type_byte = msg[0]
        body = struct.unpack(">BqiiHHHii", msg[1:])
        self.assertEqual(type_byte, TYPE_INJECT_TOUCH_EVENT)
        self.assertEqual(body[0], ACTION_MOVE)       # action
        self.assertEqual(body[1], 42)                 # pointer_id
        self.assertEqual(body[2], 333)                # x
        self.assertEqual(body[3], 777)                # y
        self.assertEqual(body[4], 720)                # video_width
        self.assertEqual(body[5], 1280)               # video_height
        self.assertEqual(body[6], 0xC000)             # pressure
        self.assertEqual(body[7], 1)                  # action_button
        self.assertEqual(body[8], 1)                  # buttons


class TestScrcpyControlState(unittest.TestCase):
    """ScrcpyControl 状态管理与降级逻辑。"""

    def test_is_available_false_initially(self):
        ctrl = ScrcpyControl(27183)
        self.assertFalse(ctrl.is_available())

    def test_is_available_false_without_video_size(self):
        """有 socket 但没设 video_size 时不可用。"""
        ctrl = ScrcpyControl(27183)
        ctrl._socket = mock.MagicMock()
        self.assertFalse(ctrl.is_available())

    def test_is_available_true_with_socket_and_video_size(self):
        ctrl = ScrcpyControl(27183)
        ctrl._socket = mock.MagicMock()
        ctrl.set_video_size(1080, 1920)
        self.assertTrue(ctrl.is_available())

    def test_is_available_false_after_close(self):
        ctrl = ScrcpyControl(27183)
        ctrl._socket = mock.MagicMock()
        ctrl.set_video_size(1080, 1920)
        self.assertTrue(ctrl.is_available())
        ctrl.close()
        self.assertFalse(ctrl.is_available())
        self.assertIsNone(ctrl._socket)

    def test_set_video_size_updates_state(self):
        ctrl = ScrcpyControl(27183)
        ctrl.set_video_size(720, 1280)
        self.assertEqual(ctrl.get_video_size(), (720, 1280))

    def test_inject_returns_false_when_unavailable(self):
        ctrl = ScrcpyControl(27183)
        self.assertFalse(ctrl.inject_touch_event(ACTION_DOWN, 100, 200))
        self.assertFalse(ctrl.inject_tap(100, 200))
        self.assertFalse(ctrl.inject_swipe(100, 200, 300, 400))

    def test_send_touch_sets_buttons_zero_on_up(self):
        """_send_touch 在 ACTION_UP 时应把 buttons 设为 0。"""
        ctrl = ScrcpyControl(27183)
        ctrl._socket = mock.MagicMock()
        ctrl.set_video_size(1080, 1920)

        with mock.patch.object(ScrcpyControl, 'build_touch_message',
                               wraps=ScrcpyControl.build_touch_message) as mock_build:
            ctrl._send_touch(ACTION_UP, 100, 200)
            # 检查最后一次调用中 buttons=0
            last_call = mock_build.call_args
            self.assertEqual(last_call.kwargs.get('buttons', _BUTTON_PRIMARY), 0)

    def test_send_touch_keeps_buttons_on_down(self):
        """_send_touch 在 ACTION_DOWN 时 buttons 保持默认值。"""
        ctrl = ScrcpyControl(27183)
        ctrl._socket = mock.MagicMock()
        ctrl.set_video_size(1080, 1920)

        with mock.patch.object(ScrcpyControl, 'build_touch_message',
                               wraps=ScrcpyControl.build_touch_message) as mock_build:
            ctrl._send_touch(ACTION_DOWN, 100, 200)
            last_call = mock_build.call_args
            self.assertEqual(last_call.kwargs.get('buttons', 0), _BUTTON_PRIMARY)

    def test_send_failure_marks_unavailable(self):
        """socket 发送失败时应标记为不可用。"""
        ctrl = ScrcpyControl(27183)
        sock = mock.MagicMock()
        sock.sendall.side_effect = BrokenPipeError("disconnected")
        ctrl._socket = sock
        ctrl.set_video_size(1080, 1920)
        self.assertTrue(ctrl.is_available())

        result = ctrl._send(b"\x00" * 32)
        self.assertFalse(result)
        self.assertFalse(ctrl.is_available())


class TestScrcpyControlConnect(unittest.TestCase):
    """control socket 连接逻辑（使用本地 mock server）。"""

    def test_connect_to_mock_server(self):
        """启动一个本地 TCP server 模拟 scrcpy forward 端口，验证连接成功。"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        port = server.getsockname()[1]

        # 模拟 video socket 先连接（scrcpy server 先 accept video）
        accepted = []
        def accept_thread():
            for _ in range(2):
                try:
                    conn, _ = server.accept()
                    accepted.append(conn)
                except Exception:
                    break

        t = threading.Thread(target=accept_thread, daemon=True)
        t.start()

        # 先建立 video socket
        video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_sock.connect(("127.0.0.1", port))

        # 再建立 control socket
        ctrl = ScrcpyControl(port)
        ok = ctrl.connect()
        self.assertTrue(ok)

        ctrl.close()
        video_sock.close()
        for conn in accepted:
            conn.close()
        server.close()

    def test_connect_fails_after_retries(self):
        """连接不存在的端口应重试后返回 False。"""
        ctrl = ScrcpyControl(1)  # 端口 1 通常无服务
        # 减少重试次数以加速测试
        with mock.patch("core.scrcpy_control._CONTROL_CONNECT_RETRIES", 2):
            with mock.patch("core.scrcpy_control._CONTROL_CONNECT_INTERVAL", 0.01):
                ok = ctrl.connect()
        self.assertFalse(ok)
        self.assertFalse(ctrl.is_available())


if __name__ == "__main__":
    unittest.main()
