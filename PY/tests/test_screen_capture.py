"""ScrcpyCapture 单元测试：坐标转换、控制委托、降级逻辑。

验证视频流坐标 ↔ 设备物理坐标的转换，
以及 control 模式与 adb 降级模式下的 begin/end_touch 行为。
"""
import unittest
from unittest import mock

import numpy as np

from core.screen_capture import ScrcpyCapture
from core.scrcpy_control import ACTION_DOWN, ACTION_MOVE, ACTION_UP


class TestVideoToDeviceCoordinate(unittest.TestCase):
    """视频流坐标 → 设备物理坐标转换。"""

    def setUp(self):
        self.cap = ScrcpyCapture()
        self.cap._base_resolution = (2400, 1080)

    def test_video_to_device_same_resolution(self):
        """视频尺寸 = 设备分辨率时，坐标 1:1。"""
        self.cap._video_size = (2400, 1080)
        # 100, 200 in video → 100, 200 in device
        dx, dy = self.cap._video_to_device(100, 200)
        self.assertEqual(dx, 100)
        self.assertEqual(dy, 200)

    def test_video_to_device_half_scale(self):
        """视频尺寸为设备分辨率的一半时，坐标 ×2。"""
        self.cap._video_size = (1200, 540)  # 半尺寸
        self.cap._base_resolution = (2400, 1080)
        dx, dy = self.cap._video_to_device(500, 270)
        self.assertEqual(dx, 1000)
        self.assertEqual(dy, 540)

    def test_video_to_device_rounds_to_int(self):
        """坐标转换结果应为整数。"""
        self.cap._video_size = (1080, 1920)
        self.cap._base_resolution = (2400, 1080)
        dx, dy = self.cap._video_to_device(333, 999)
        self.assertIsInstance(dx, int)
        self.assertIsInstance(dy, int)

    def test_video_to_device_preserves_aspect_ratio(self):
        """不同宽高比下仍按各自维度独立缩放。"""
        self.cap._video_size = (1080, 486)  # scrcpy max_size=1080 后的尺寸
        self.cap._base_resolution = (2400, 1080)
        # x: 1080 → 2400 (clamped to bw-1=2399), y: 486 → 1080 (clamped to bh-1=1079)
        dx, dy = self.cap._video_to_device(1080, 486)
        self.assertEqual(dx, 2399)  # clamped to bw-1
        self.assertEqual(dy, 1079)  # clamped to bh-1


class TestBeginEndTouchControlMode(unittest.TestCase):
    """control 模式下的 begin_touch/end_touch：实时注入。"""

    def setUp(self):
        self.cap = ScrcpyCapture()
        self.cap._base_resolution = (2400, 1080)
        self.cap._video_size = (1080, 486)
        self.cap._control = mock.MagicMock()
        self.cap._control.is_available.return_value = True

    def test_begin_touch_injects_down(self):
        """control 可用时 begin_touch 注入 ACTION_DOWN。"""
        self.cap.begin_touch(500, 200)
        self.cap._control.inject_touch_event.assert_called_once_with(ACTION_DOWN, 500, 200)

    def test_begin_touch_records_start(self):
        """begin_touch 记录按下起点（供 end_touch 分类用）。"""
        self.cap.begin_touch(500, 200)
        self.assertEqual(self.cap._touch_start, (500, 200))
        self.assertGreater(self.cap._touch_start_time, 0)

    def test_end_touch_tap_when_control_available(self):
        """control 可用时 end_touch 注入 ACTION_UP（不做 tap/swipe 分类）。"""
        self.cap.begin_touch(500, 200)
        self.cap.end_touch(501, 201)  # 近距离 → 实际是 tap
        # control 模式下直接注入 UP
        calls = self.cap._control.inject_touch_event.call_args_list
        # 第一次是 DOWN，最后一次是 UP
        self.assertEqual(calls[0], mock.call(ACTION_DOWN, 500, 200))
        self.assertEqual(calls[-1], mock.call(ACTION_UP, 501, 201))

    def test_move_touch_injects_move(self):
        """move_touch 在 control 模式下注入 ACTION_MOVE。"""
        self.cap.begin_touch(100, 100)
        self.cap.move_touch(200, 200)
        self.cap._control.inject_touch_event.assert_called_with(ACTION_MOVE, 200, 200)


class TestBeginEndTouchAdbFallback(unittest.TestCase):
    """adb 降级模式下的 begin_touch/end_touch：抬起时整体注入。"""

    def setUp(self):
        self.cap = ScrcpyCapture()
        self.cap._base_resolution = (2400, 1080)
        self.cap._video_size = (1080, 486)
        self.cap._control = mock.MagicMock()
        self.cap._control.is_available.return_value = False
        self.cap._adb_core = mock.MagicMock()

    def test_begin_touch_no_inject_in_adb_mode(self):
        """adb 模式下 begin_touch 不注入（只记录起点）。"""
        self.cap.begin_touch(500, 200)
        self.cap._control.inject_touch_event.assert_not_called()
        self.assertEqual(self.cap._touch_start, (500, 200))

    def test_end_touch_tap_in_adb_mode(self):
        """adb 模式下近距离抬起 → 调用 adb tap（设备坐标，使用抬起点）。"""
        self.cap.begin_touch(500, 200)  # 视频坐标
        self.cap.end_touch(501, 201)    # 近距离 → tap
        # adb tap 使用抬起点坐标（501, 201）经视频→设备转换
        # _video_to_device(501, 201) with video=1080x486, device=2400x1080
        # x = int(501 * 2400 / 1080) = 1113, y = int(201 * 1080 / 486) = 446
        self.cap._adb_core.tap.assert_called_once()
        args = self.cap._adb_core.tap.call_args[0]
        self.assertEqual(args[0], 1113)
        self.assertEqual(args[1], 446)

    def test_end_touch_swipe_in_adb_mode(self):
        """adb 模式下远距离抬起 → 调用 adb swipe（设备坐标）。"""
        self.cap.begin_touch(100, 100)   # 视频坐标
        self.cap.end_touch(800, 400)     # 远距离 → swipe
        self.cap._adb_core.swipe.assert_called_once()
        # swipe 参数: x1, y1, x2, y2, duration_ms
        args = self.cap._adb_core.swipe.call_args[0]
        # 验证起点和终点都是设备坐标
        # _video_to_device(100, 100) = (222, 222), _video_to_device(800, 400) = (1777, 888)
        self.assertAlmostEqual(args[0], 222, delta=2)
        self.assertAlmostEqual(args[1], 222, delta=2)
        self.assertAlmostEqual(args[2], 1777, delta=2)
        self.assertAlmostEqual(args[3], 888, delta=2)

    def test_move_touch_no_inject_in_adb_mode(self):
        """adb 模式下 move_touch 不注入（抬起时才整体注入）。"""
        self.cap.begin_touch(100, 100)
        self.cap.move_touch(200, 200)
        self.cap._control.inject_touch_event.assert_not_called()


class TestIsControlAvailable(unittest.TestCase):
    """is_control_available 返回 control 通道状态。"""

    def test_false_when_no_control(self):
        cap = ScrcpyCapture()
        self.assertFalse(cap.is_control_available())

    def test_false_when_control_unavailable(self):
        cap = ScrcpyCapture()
        cap._control = mock.MagicMock()
        cap._control.is_available.return_value = False
        self.assertFalse(cap.is_control_available())

    def test_true_when_control_available(self):
        cap = ScrcpyCapture()
        cap._control = mock.MagicMock()
        cap._control.is_available.return_value = True
        self.assertTrue(cap.is_control_available())


class TestSetBaseResolution(unittest.TestCase):
    """set_base_resolution 更新设备物理分辨率。"""

    def test_sets_base_resolution(self):
        cap = ScrcpyCapture()
        cap.set_base_resolution(1920, 1080)
        self.assertEqual(cap._base_resolution, (1920, 1080))

    def test_overwrites_previous(self):
        cap = ScrcpyCapture()
        cap.set_base_resolution(1920, 1080)
        cap.set_base_resolution(2400, 1080)
        self.assertEqual(cap._base_resolution, (2400, 1080))


class TestGetVideoSize(unittest.TestCase):
    """get_video_size 返回当前视频帧尺寸。"""

    def test_returns_current_video_size(self):
        cap = ScrcpyCapture()
        cap._video_size = (1080, 486)
        self.assertEqual(cap.get_video_size(), (1080, 486))

    def test_returns_zero_initially(self):
        cap = ScrcpyCapture()
        self.assertEqual(cap.get_video_size(), (0, 0))


if __name__ == "__main__":
    unittest.main()
