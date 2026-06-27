"""StepRecorder 单元测试。

验证手势分类（tap/swipe）、操作间等待记录、噪点过滤、录制启停。
"""
import math
import unittest

from core.recorder import StepRecorder, _TAP_THRESHOLD_PCT, _NOISE_MIN_DURATION


class TestStepRecorderTap(unittest.TestCase):
    """tap 手势分类：按下点 ≈ 抬起点（位移 < 阈值）。"""

    def setUp(self):
        self.rec = StepRecorder()
        self.rec.set_base_resolution(2400, 1080)
        self.rec.start_recording()

    def test_tap_generates_tap_step(self):
        """短距离按下抬起 → tap 步骤。"""
        self.rec.on_interaction_started(500, 500, 0.0)
        self.rec.on_interaction_ended(501, 502, 0.05)
        steps = self.rec.get_steps()
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["type"], "tap")
        self.assertEqual(steps[0]["x"], 500)
        self.assertEqual(steps[0]["y"], 500)

    def test_tap_uses_press_point_not_release(self):
        """tap 步骤的坐标应为按下点，非抬起点。"""
        self.rec.on_interaction_started(100, 200, 0.0)
        self.rec.on_interaction_ended(102, 203, 0.03)  # dist=3.6 < 5.4 → tap
        steps = self.rec.get_steps()
        self.assertEqual(steps[0]["x"], 100)
        self.assertEqual(steps[0]["y"], 200)

    def test_tap_threshold_is_half_percent_of_short_side(self):
        """阈值 = min(2400, 1080) * 0.005 = 5.4 像素。"""
        threshold = min(2400, 1080) * _TAP_THRESHOLD_PCT
        self.assertAlmostEqual(threshold, 5.4, places=1)

        # 位移 5 像素 → tap
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(5, 0, 0.02)
        self.assertEqual(self.rec.get_steps()[-1]["type"], "tap")

        # 位移 6 像素 → swipe
        self.rec.on_interaction_started(0, 0, 0.1)
        self.rec.on_interaction_ended(6, 0, 0.15)
        self.assertEqual(self.rec.get_steps()[-1]["type"], "swipe")


class TestStepRecorderSwipe(unittest.TestCase):
    """swipe 手势分类：有位移 → swipe 步骤（含 duration，单位毫秒）。"""

    def setUp(self):
        self.rec = StepRecorder()
        self.rec.set_base_resolution(2400, 1080)
        self.rec.start_recording()

    def test_swipe_generates_swipe_step(self):
        """长距离按下抬起 → swipe 步骤。"""
        self.rec.on_interaction_started(100, 200, 0.0)
        self.rec.on_interaction_ended(500, 800, 0.3)
        steps = self.rec.get_steps()
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["type"], "swipe")
        self.assertEqual(steps[0]["x1"], 100)
        self.assertEqual(steps[0]["y1"], 200)
        self.assertEqual(steps[0]["x2"], 500)
        self.assertEqual(steps[0]["y2"], 800)

    def test_swipe_duration_in_milliseconds(self):
        """swipe duration 必须是毫秒（秒 × 1000，四舍五入）。"""
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.250)
        steps = self.rec.get_steps()
        self.assertEqual(steps[0]["duration"], 250)

    def test_swipe_duration_rounds_correctly(self):
        """0.2995s → 300ms（四舍五入）。"""
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.2995)
        steps = self.rec.get_steps()
        self.assertEqual(steps[0]["duration"], 300)


class TestStepRecorderWait(unittest.TestCase):
    """操作间等待：写入上一步的 wait_after（单位秒）。"""

    def setUp(self):
        self.rec = StepRecorder()
        self.rec.set_base_resolution(2400, 1080)
        self.rec.start_recording()

    def test_wait_after_is_gap_between_steps(self):
        """第二步的 wait_after = 第二次按下时间 - 第一次抬起时间。"""
        # 第一步：0.0s 按下，0.05s 抬起
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)
        # 间隔 1.5s
        # 第二步：1.55s 按下，1.60s 抬起
        self.rec.on_interaction_started(200, 200, 1.55)
        self.rec.on_interaction_ended(200, 200, 1.60)
        steps = self.rec.get_steps()
        self.assertEqual(len(steps), 2)
        # 第一步的 wait_after = 1.55 - 0.05 = 1.50s
        self.assertAlmostEqual(steps[0]["wait_after"], 1.5, places=3)
        # 最后一步的 wait_after 默认 0（无下一步承接）
        self.assertEqual(steps[1]["wait_after"], 0)

    def test_wait_after_zero_for_first_step(self):
        """第一步的 wait_after 默认 0（无前序步骤）。"""
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)
        steps = self.rec.get_steps()
        self.assertEqual(steps[0]["wait_after"], 0)

    def test_wait_after_three_steps(self):
        """三步连续操作，验证每步等待正确。"""
        # 步骤 1: 0.0→0.05
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(0, 0, 0.05)
        # 间隔 0.5s
        # 步骤 2: 0.55→0.60
        self.rec.on_interaction_started(10, 10, 0.55)
        self.rec.on_interaction_ended(10, 10, 0.60)
        # 间隔 1.0s
        # 步骤 3: 1.60→1.65
        self.rec.on_interaction_started(20, 20, 1.60)
        self.rec.on_interaction_ended(20, 20, 1.65)

        steps = self.rec.get_steps()
        self.assertEqual(len(steps), 3)
        self.assertAlmostEqual(steps[0]["wait_after"], 0.5, places=3)
        self.assertAlmostEqual(steps[1]["wait_after"], 1.0, places=3)
        self.assertEqual(steps[2]["wait_after"], 0)


class TestStepRecorderNoise(unittest.TestCase):
    """噪点过滤：极短按下抬起（duration < 0.008s）视为误触。"""

    def setUp(self):
        self.rec = StepRecorder()
        self.rec.set_base_resolution(2400, 1080)
        self.rec.start_recording()

    def test_noise_filtered_below_threshold(self):
        """duration < 0.008s 的操作被忽略。"""
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.005)  # 5ms < 8ms
        self.assertEqual(len(self.rec.get_steps()), 0)

    def test_valid_above_threshold(self):
        """duration ≥ 0.008s 的操作正常记录。"""
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.01)  # 10ms ≥ 8ms
        self.assertEqual(len(self.rec.get_steps()), 1)

    def test_noise_does_not_break_wait_chain(self):
        """噪点被过滤后不应影响后续步骤的等待计算。"""
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)  # 正常步骤
        self.rec.on_interaction_started(200, 200, 0.10)
        self.rec.on_interaction_ended(200, 200, 0.102)  # 噪点（2ms < 8ms）
        self.rec.on_interaction_started(300, 300, 0.50)
        self.rec.on_interaction_ended(300, 300, 0.55)  # 正常步骤

        steps = self.rec.get_steps()
        # 噪点被过滤，只有 2 步
        self.assertEqual(len(steps), 2)
        # 第一步的 wait_after = 0.50 - 0.05 = 0.45s（噪点的按下时间不被使用）
        self.assertAlmostEqual(steps[0]["wait_after"], 0.45, places=3)


class TestStepRecorderLifecycle(unittest.TestCase):
    """录制启停与状态管理。"""

    def setUp(self):
        self.rec = StepRecorder()
        self.rec.set_base_resolution(2400, 1080)

    def test_start_sets_recording_flag(self):
        self.assertFalse(self.rec.is_recording())
        self.rec.start_recording()
        self.assertTrue(self.rec.is_recording())

    def test_start_twice_returns_false(self):
        self.rec.start_recording()
        self.assertFalse(self.rec.start_recording())

    def test_stop_returns_steps(self):
        self.rec.start_recording()
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)
        steps = self.rec.stop_recording()
        self.assertEqual(len(steps), 1)
        self.assertFalse(self.rec.is_recording())

    def test_stop_when_not_recording_returns_empty(self):
        steps = self.rec.stop_recording()
        self.assertEqual(steps, [])

    def test_start_clears_previous_steps(self):
        self.rec.start_recording()
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)
        self.rec.stop_recording()
        self.assertEqual(len(self.rec.get_steps()), 1)

        # 重新开始录制，之前步骤应清空
        self.rec.start_recording()
        self.assertEqual(len(self.rec.get_steps()), 0)

    def test_interaction_ignored_when_not_recording(self):
        """未录制时交互信号不产生步骤。"""
        self.rec.on_interaction_started(100, 100, 0.0)
        self.rec.on_interaction_ended(100, 100, 0.05)
        self.assertEqual(len(self.rec.get_steps()), 0)

    def test_step_comment_increments(self):
        """步骤注释编号递增。"""
        self.rec.start_recording()
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(0, 0, 0.02)
        self.rec.on_interaction_started(10, 10, 0.1)
        self.rec.on_interaction_ended(15, 15, 0.12)

        steps = self.rec.get_steps()
        self.assertEqual(steps[0]["comment"], "录制 #1")
        self.assertEqual(steps[1]["comment"], "录制 #2")

    def test_recording_started_signal_emitted(self):
        """start_recording 应发出 recording_started 信号。"""
        emitted = []
        self.rec.recording_started.connect(lambda: emitted.append(True))
        self.rec.start_recording()
        self.assertTrue(emitted)

    def test_recording_stopped_signal_emitted_with_steps(self):
        """stop_recording 应发出 recording_stopped 信号（参数为步骤列表）。"""
        emitted = []
        self.rec.recording_stopped.connect(lambda steps: emitted.append(steps))
        self.rec.start_recording()
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(0, 0, 0.02)
        self.rec.stop_recording()
        self.assertEqual(len(emitted), 1)
        self.assertEqual(len(emitted[0]), 1)

    def test_event_recorded_signal_emitted_per_step(self):
        """每录制一个步骤应发出 event_recorded 信号。"""
        emitted = []
        self.rec.event_recorded.connect(lambda step: emitted.append(step))
        self.rec.start_recording()
        self.rec.on_interaction_started(0, 0, 0.0)
        self.rec.on_interaction_ended(0, 0, 0.02)
        self.rec.on_interaction_started(50, 50, 0.1)
        self.rec.on_interaction_ended(200, 200, 0.4)
        self.assertEqual(len(emitted), 2)
        self.assertEqual(emitted[0]["type"], "tap")
        self.assertEqual(emitted[1]["type"], "swipe")


class TestStepRecorderBaseResolution(unittest.TestCase):
    """不同 base_resolution 下的阈值适配。"""

    def test_threshold_scales_with_resolution(self):
        """1080p 设备阈值 = 1080 * 0.005 = 5.4px；720p 设备 = 720 * 0.005 = 3.6px。"""
        rec1 = StepRecorder()
        rec1.set_base_resolution(1920, 1080)
        rec1.start_recording()
        rec1.on_interaction_started(0, 0, 0.0)
        rec1.on_interaction_ended(5, 0, 0.02)
        self.assertEqual(rec1.get_steps()[-1]["type"], "tap")  # 5 < 5.4

        rec2 = StepRecorder()
        rec2.set_base_resolution(1280, 720)
        rec2.start_recording()
        rec2.on_interaction_started(0, 0, 0.0)
        rec2.on_interaction_ended(5, 0, 0.02)
        self.assertEqual(rec2.get_steps()[-1]["type"], "swipe")  # 5 > 3.6


if __name__ == "__main__":
    unittest.main()
