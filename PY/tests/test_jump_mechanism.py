"""跳转机制单元测试。

覆盖：
- _build_jump_labels: 映射表构建 + 自动生成标签
- _generate_label: 唯一性与格式
- _handle_jump: 无条件/条件/循环回跳/防死循环/目标不存在
"""
import re
import sys
import os
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt5.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)

from core.step_executor import StepExecutor, _MAX_JUMPS


def _make_executor():
    """构造 mock 依赖并返回 StepExecutor 实例。"""
    import numpy as np
    config = unittest.mock.MagicMock()
    config.get_config.return_value = {}
    adb = unittest.mock.MagicMock()
    capture = unittest.mock.MagicMock()
    capture.get_current_frame.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
    ocr = unittest.mock.MagicMock()
    device = unittest.mock.MagicMock()
    device.get_device_resolution.return_value = (1080, 1920)
    device.get_current_device.return_value = "emulator-5554"
    executor = StepExecutor(config, adb, capture, ocr, device)
    # 初始化 execute_workflow 才设置的运行时属性
    executor._current_step_index = -1
    executor._stop_requested = False
    return executor


class TestBuildJumpLabels(unittest.TestCase):
    """测试 _build_jump_labels 映射表构建。"""

    def test_explicit_labels(self):
        """显式 jump_label 的步骤应进入映射表。"""
        steps = [
            {"type": "tap", "jump_label": "#AAAA"},
            {"type": "wait"},
            {"type": "tap", "jump_label": "#BBBB"},
        ]
        labels = StepExecutor._build_jump_labels(steps)
        self.assertEqual(labels, {"#AAAA": 0, "#BBBB": 2})

    def test_auto_generate_for_jump_target(self):
        """is_jump_target=true 但无 jump_label 时应自动生成。"""
        steps = [
            {"type": "tap", "is_jump_target": True},
            {"type": "wait"},
        ]
        labels = StepExecutor._build_jump_labels(steps)
        self.assertEqual(len(labels), 1)
        label = list(labels.keys())[0]
        self.assertTrue(re.match(r"^#[0-9A-F]{4}$", label))
        self.assertEqual(labels[label], 0)
        # 自动生成的标签应写回 step
        self.assertEqual(steps[0]["jump_label"], label)

    def test_no_labels_returns_empty(self):
        """无跳入点的步骤集应返回空映射。"""
        steps = [{"type": "tap"}, {"type": "wait"}]
        labels = StepExecutor._build_jump_labels(steps)
        self.assertEqual(labels, {})

    def test_duplicate_labels_last_wins(self):
        """重复标签时后者覆盖前者索引。"""
        steps = [
            {"type": "tap", "jump_label": "#DUP"},
            {"type": "wait", "jump_label": "#DUP"},
        ]
        labels = StepExecutor._build_jump_labels(steps)
        self.assertEqual(labels, {"#DUP": 1})


class TestGenerateLabel(unittest.TestCase):
    """测试 _generate_label 标签生成。"""

    def test_format(self):
        """生成的标签应符合 #XXXX 格式（4位十六进制大写）。"""
        label = StepExecutor._generate_label(set())
        self.assertTrue(re.match(r"^#[0-9A-F]{4}$", label))

    def test_uniqueness(self):
        """生成的标签不应与 existing 集合冲突。"""
        existing = {"#0000", "#FFFF", "#ABCD"}
        for _ in range(50):
            label = StepExecutor._generate_label(existing)
            self.assertNotIn(label, existing)
            existing.add(label)

    def test_many_unique(self):
        """连续生成多个标签应互不重复。"""
        labels = set()
        for _ in range(100):
            labels.add(StepExecutor._generate_label(labels))
        self.assertEqual(len(labels), 100)


class TestHandleJump(unittest.TestCase):
    """测试 _handle_jump 跳转决策。"""

    def setUp(self):
        self.executor = _make_executor()
        self.executor._current_workflow = "test_wf"
        self.executor._jump_labels = {"#T1": 5}
        self.executor._jump_counters = {}
        self.executor._total_jumps = 0

    def test_no_jump_to_returns_continue(self):
        """jump_to 为空时返回 continue。"""
        result = self.executor._handle_jump({"type": "tap"}, 0, [])
        self.assertEqual(result, "continue")

    def test_target_not_found_returns_continue(self):
        """跳转目标不存在时降级为 continue。"""
        step = {"type": "tap", "jump_to": "#NONEXIST"}
        result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "continue")

    def test_unconditional_jump(self):
        """无条件跳转应返回 jumped。"""
        step = {"type": "tap", "jump_to": "#T1"}
        result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "jumped")
        self.assertEqual(self.executor._total_jumps, 1)

    def test_conditional_jump_satisfied(self):
        """条件满足时应跳转。"""
        step = {"type": "tap", "jump_to": "#T1", "jump_condition": {"type": "image_found"}}
        with unittest.mock.patch.object(self.executor, '_evaluate_condition', return_value=True):
            result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "jumped")

    def test_conditional_jump_not_satisfied(self):
        """条件不满足时应继续（不跳转）。"""
        step = {"type": "tap", "jump_to": "#T1", "jump_condition": {"type": "image_found"}}
        with unittest.mock.patch.object(self.executor, '_evaluate_condition', return_value=False):
            result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "continue")
        self.assertEqual(self.executor._total_jumps, 0)

    def test_loop_jump_within_limit(self):
        """循环回跳未达次数限制时应跳转。"""
        step = {"type": "wait", "jump_to": "#T1", "jump_count": 3}
        # 第一次跳转
        self.assertEqual(self.executor._handle_jump(step, 0, []), "jumped")
        # 第二次跳转
        self.assertEqual(self.executor._handle_jump(step, 0, []), "jumped")
        # 第三次跳转
        self.assertEqual(self.executor._handle_jump(step, 0, []), "jumped")

    def test_loop_jump_exceeds_limit(self):
        """循环回跳达次数限制后应继续（不跳转）。"""
        step = {"type": "wait", "jump_to": "#T1", "jump_count": 2}
        self.executor._handle_jump(step, 0, [])  # 第1次
        self.executor._handle_jump(step, 0, [])  # 第2次
        # 第3次应不再跳转
        result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "continue")

    def test_loop_jump_count_zero_unlimited(self):
        """jump_count=0 表示无限次跳转。"""
        step = {"type": "wait", "jump_to": "#T1", "jump_count": 0}
        for i in range(50):
            result = self.executor._handle_jump(step, 0, [])
            self.assertEqual(result, "jumped", f"iteration {i} should jump")

    def test_max_jumps_protection(self):
        """全局跳转次数超限应返回 error。"""
        step = {"type": "tap", "jump_to": "#T1"}
        self.executor._total_jumps = _MAX_JUMPS
        result = self.executor._handle_jump(step, 0, [])
        self.assertEqual(result, "error")


class TestRunStepsWithJump(unittest.TestCase):
    """测试 _run_steps 集成跳转逻辑。"""

    def test_unconditional_jump_creates_loop_with_count(self):
        """无条件跳转 + jump_count 应形成有限循环后继续。"""
        executor = _make_executor()
        executor._current_workflow = "test_wf"
        # step0 跳回自身最多2次，然后继续到 step1
        steps = [
            {"type": "wait", "seconds": 0, "jump_to": "#L0", "jump_count": 2,
             "jump_label": "#L0", "is_jump_target": True},
            {"type": "wait", "seconds": 0},
        ]
        executed = []
        with unittest.mock.patch.object(executor, 'execute_step',
                                        side_effect=lambda wf, i: executed.append(i) or True):
            with unittest.mock.patch.object(executor, 'workflow_completed'):
                executor._run_steps(steps, "test_wf", 0, len(steps))
        # step0 执行3次（初始+2次回跳），step1 执行1次
        self.assertEqual(executed, [0, 0, 0, 1])

    def test_no_jump_sequential(self):
        """无跳转字段时应顺序执行。"""
        executor = _make_executor()
        executor._current_workflow = "test_wf"
        steps = [
            {"type": "wait", "seconds": 0},
            {"type": "wait", "seconds": 0},
            {"type": "wait", "seconds": 0},
        ]
        executed = []
        with unittest.mock.patch.object(executor, 'execute_step',
                                        side_effect=lambda wf, i: executed.append(i) or True):
            with unittest.mock.patch.object(executor, 'workflow_completed'):
                executor._run_steps(steps, "test_wf", 0, len(steps))
        self.assertEqual(executed, [0, 1, 2])


if __name__ == '__main__':
    unittest.main()
