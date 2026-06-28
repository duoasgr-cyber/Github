"""投屏录制集成测试：录制 → 追加工作流 → 验证步骤格式。

端到端验证 StepRecorder 的完整流程：
1. 启动录制
2. 模拟一系列交互（tap、swipe、操作间等待）
3. 停止录制
4. 验证生成的步骤列表格式正确
5. 验证步骤可追加到 WorkflowPanel 的工作流
6. 验证步骤格式与 StepExecutor 兼容
"""
import copy
import unittest
from unittest import mock

from core.recorder import StepRecorder


class TestRecordReplayFlow(unittest.TestCase):
    """录制 → 回放完整流程。"""

    def setUp(self):
        self.recorder = StepRecorder()
        self.recorder.set_base_resolution(2400, 1080)

    def test_record_tap_swipe_wait_sequence(self):
        """录制典型操作序列：点击 → 等待 → 滑动 → 等待 → 点击。"""
        self.recorder.start_recording()

        # 1. 点击按钮 (0.0s → 0.05s)
        self.recorder.on_interaction_started(1200, 800, 0.0)
        self.recorder.on_interaction_ended(1200, 800, 0.05)

        # 等待 0.8s

        # 2. 向上滑动 (0.85s → 1.15s)
        self.recorder.on_interaction_started(1200, 900, 0.85)
        self.recorder.on_interaction_ended(1200, 300, 1.15)

        # 等待 0.5s

        # 3. 点击另一个按钮 (1.65s → 1.70s)
        self.recorder.on_interaction_started(600, 540, 1.65)
        self.recorder.on_interaction_ended(600, 540, 1.70)

        steps = self.recorder.stop_recording()

        # 验证步骤数量
        self.assertEqual(len(steps), 3)

        # 步骤 1: tap
        self.assertEqual(steps[0]["type"], "tap")
        self.assertEqual(steps[0]["x"], 1200)
        self.assertEqual(steps[0]["y"], 800)
        self.assertAlmostEqual(steps[0]["wait_after"], 0.8, places=3)
        self.assertEqual(steps[0]["comment"], "录制 #1")

        # 步骤 2: swipe
        self.assertEqual(steps[1]["type"], "swipe")
        self.assertEqual(steps[1]["x1"], 1200)
        self.assertEqual(steps[1]["y1"], 900)
        self.assertEqual(steps[1]["x2"], 1200)
        self.assertEqual(steps[1]["y2"], 300)
        self.assertEqual(steps[1]["duration"], 300)  # 0.3s → 300ms
        self.assertAlmostEqual(steps[1]["wait_after"], 0.5, places=3)
        self.assertEqual(steps[1]["comment"], "录制 #2")

        # 步骤 3: tap (最后一步 wait_after=0)
        self.assertEqual(steps[2]["type"], "tap")
        self.assertEqual(steps[2]["x"], 600)
        self.assertEqual(steps[2]["y"], 540)
        self.assertEqual(steps[2]["wait_after"], 0)
        self.assertEqual(steps[2]["comment"], "录制 #3")

    def test_recorded_steps_are_deep_copiable(self):
        """录制的步骤应可深拷贝（追加到工作流时需要）。"""
        self.recorder.start_recording()
        self.recorder.on_interaction_started(100, 100, 0.0)
        self.recorder.on_interaction_ended(100, 100, 0.05)
        steps = self.recorder.stop_recording()

        copied = copy.deepcopy(steps)
        self.assertEqual(copied, steps)
        copied[0]["x"] = 999
        self.assertNotEqual(steps[0]["x"], 999)  # 原列表不受影响

    def test_recorded_tap_format_matches_step_executor(self):
        """tap 步骤格式与 StepExecutor 期望一致：type, x, y, comment, wait_after。"""
        self.recorder.start_recording()
        self.recorder.on_interaction_started(100, 200, 0.0)
        self.recorder.on_interaction_ended(100, 200, 0.05)
        steps = self.recorder.stop_recording()

        tap = steps[0]
        required_keys = {"type", "x", "y", "comment", "wait_after"}
        self.assertTrue(required_keys.issubset(tap.keys()))
        self.assertEqual(tap["type"], "tap")
        self.assertIsInstance(tap["x"], int)
        self.assertIsInstance(tap["y"], int)
        self.assertIsInstance(tap["wait_after"], (int, float))

    def test_recorded_swipe_format_matches_step_executor(self):
        """swipe 步骤格式与 StepExecutor 期望一致：type, x1, y1, x2, y2, duration, comment, wait_after。"""
        self.recorder.start_recording()
        self.recorder.on_interaction_started(100, 100, 0.0)
        self.recorder.on_interaction_ended(500, 800, 0.3)
        steps = self.recorder.stop_recording()

        swipe = steps[0]
        required_keys = {"type", "x1", "y1", "x2", "y2", "duration", "comment", "wait_after"}
        self.assertTrue(required_keys.issubset(swipe.keys()))
        self.assertEqual(swipe["type"], "swipe")
        self.assertIsInstance(swipe["duration"], int)  # 毫秒，整数
        self.assertIsInstance(swipe["x1"], int)
        self.assertIsInstance(swipe["x2"], int)

    def test_empty_recording_produces_no_steps(self):
        """开启后立即停止，不产生步骤。"""
        self.recorder.start_recording()
        steps = self.recorder.stop_recording()
        self.assertEqual(len(steps), 0)

    def test_rapid_taps_produce_separate_steps(self):
        """连续快速点击应生成多个独立 tap 步骤。"""
        self.recorder.start_recording()
        for i in range(5):
            t = i * 0.15
            self.recorder.on_interaction_started(100 * i, 200, t)
            self.recorder.on_interaction_ended(100 * i, 200, t + 0.02)

        steps = self.recorder.stop_recording()
        self.assertEqual(len(steps), 5)
        for step in steps:
            self.assertEqual(step["type"], "tap")

    def test_coordinates_are_device_resolution(self):
        """录制坐标应为设备物理分辨率（非视频流坐标）。

        MirrorWidget 在发出 interaction_started/ended 信号时，
        已通过 _img_to_device 将坐标转换为设备物理坐标系。
        StepRecorder 直接记录收到的坐标，不做二次转换。
        """
        self.recorder.start_recording()
        # 模拟 MirrorWidget 发出的设备坐标
        self.recorder.on_interaction_started(1200, 540, 0.0)
        self.recorder.on_interaction_ended(1200, 540, 0.05)
        steps = self.recorder.stop_recording()

        self.assertEqual(steps[0]["x"], 1200)
        self.assertEqual(steps[0]["y"], 540)


class TestWorkflowAppendFlow(unittest.TestCase):
    """录制步骤追加到 WorkflowPanel 的流程。"""

    def test_append_steps_to_workflow(self):
        """模拟 WorkflowPanel.append_recorded_steps 的行为。"""
        # 模拟工作流
        workflow = {
            "description": "",
            "device_resolution": {"width": 2400, "height": 1080},
            "steps": [
                {"type": "tap", "x": 100, "y": 100, "comment": "existing", "wait_after": 0},
            ],
        }

        # 录制新步骤
        recorder = StepRecorder()
        recorder.set_base_resolution(2400, 1080)
        recorder.start_recording()
        recorder.on_interaction_started(500, 500, 0.0)
        recorder.on_interaction_ended(500, 500, 0.05)
        recorder.on_interaction_started(600, 600, 0.3)
        recorder.on_interaction_ended(600, 600, 0.35)
        new_steps = recorder.stop_recording()

        # 追加
        start_index = len(workflow["steps"])
        workflow["steps"].extend(copy.deepcopy(new_steps))

        # 验证
        self.assertEqual(len(workflow["steps"]), 3)
        self.assertEqual(workflow["steps"][0]["comment"], "existing")
        self.assertEqual(workflow["steps"][1]["comment"], "录制 #1")
        self.assertEqual(workflow["steps"][2]["comment"], "录制 #2")
        self.assertEqual(start_index, 1)

        # 第一个录制步骤的 wait_after 应为 0.25 (0.3 - 0.05)
        self.assertAlmostEqual(workflow["steps"][1]["wait_after"], 0.25, places=3)

    def test_empty_steps_list_not_appended(self):
        """空步骤列表不应追加。"""
        workflow = {"steps": [{"type": "wait", "seconds": 1}]}
        new_steps = []
        if new_steps:
            workflow["steps"].extend(copy.deepcopy(new_steps))
        self.assertEqual(len(workflow["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
