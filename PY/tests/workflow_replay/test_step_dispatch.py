"""Step 分发表回归测试：每种 step.type 应路由到对应 _step_* 处理函数。

对应 P1-1：step_executor.py 拆分为 mixin 后，dispatch.py 维护分发表，
本用例确保 21 种 step 类型全部被正确分发。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from core.step_executor import StepExecutor
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


@unittest.skipUnless(HAS_PYQT, "PyQt5 not installed")
class TestStepDispatch(unittest.TestCase):
    """对每种 step.type 喂最小 step dict，断言对应的 _step_* 方法被调用一次。"""

    STEP_TO_HANDLER = [
        ("tap", "_step_tap", {"type": "tap", "x": 0, "y": 0}),
        ("long_press", "_step_long_press", {"type": "long_press", "x": 0, "y": 0, "duration": 1}),
        ("swipe", "_step_swipe", {"type": "swipe", "start_x": 0, "start_y": 0, "end_x": 0, "end_y": 0}),
        ("keyevent", "_step_keyevent", {"type": "keyevent", "keycode": 4}),
        ("wait", "_step_wait", {"type": "wait", "seconds": 0}),
        ("wifi", "_step_wifi", {"type": "wifi", "action": "enable"}),
        ("force_stop", "_step_force_stop", {"type": "force_stop"}),
        ("launch", "_step_launch", {"type": "launch"}),
        ("screenshot", "_step_screenshot", {"type": "screenshot", "path": "x.png"}),
        ("pull_file", "_step_pull_file", {"type": "pull_file", "remote": "/a", "local": "b"}),
        ("delete_file", "_step_delete_file", {"type": "delete_file", "path": "/a"}),
        ("check_image", "_step_check_image", {"type": "check_image", "template": "a.png"}),
        ("ocr_region", "_step_ocr_region", {"type": "ocr_region", "region": {}}),
        ("tap_point", "_step_tap_point", {"type": "tap_point", "x": 0, "y": 0}),
        ("call_workflow", "_step_call_workflow", {"type": "call_workflow", "workflow": "w"}),
        ("condition", "_step_condition", {"type": "condition", "check": {}, "then_steps": []}),
        ("loop", "_step_loop", {"type": "loop", "steps": [], "max_count": 1}),
        ("input_text", "_step_input_text", {"type": "input_text", "text": "x"}),
        ("variable", "_step_variable", {"type": "variable", "name": "v", "value": 0}),
        ("adb_command", "_step_adb_command", {"type": "adb_command", "command": "ls"}),
        ("expression", "_step_expression", {"type": "expression", "expr": "1"}),
    ]

    def _make_executor(self):
        from core.config_manager import ConfigManager
        from PyQt5.QtCore import QObject
        import threading
        executor = StepExecutor.__new__(StepExecutor)
        QObject.__init__(executor)
        executor._config_manager = mock.MagicMock()
        executor._config_manager.get_config.return_value = {}
        executor._adb_core = mock.MagicMock()
        executor._screen_capture = mock.MagicMock()
        executor._ocr_engine = mock.MagicMock()
        executor._device_manager = mock.MagicMock()
        executor._device_manager.get_current_device.return_value = "FAKE"
        executor._device_manager.get_device_resolution.return_value = None
        executor._running = False
        executor._paused = False
        executor._stop_requested = False
        executor._current_workflow = None
        executor._current_step_index = -1
        executor._last_check_result = False
        executor._last_ocr_result = ""
        executor._scale_x = 1.0
        executor._scale_y = 1.0
        executor._workflow_depth = 0
        executor._workflow_call_stack = []
        executor._variables = {}
        executor._pause_event = threading.Event()
        executor._pause_event.set()
        executor._error_policy_config = None
        executor._error_executor = None
        return executor

    def test_each_step_type_dispatches_to_handler(self):
        executor = self._make_executor()
        for step_type, handler_name, step_dict in self.STEP_TO_HANDLER:
            with self.subTest(step_type=step_type):
                with mock.patch.object(executor, handler_name, return_value=True) as handler:
                    ok = executor._execute_single_step(step_dict)
                    self.assertTrue(ok, f"step_type={step_type} should dispatch successfully")
                    handler.assert_called_once_with(step_dict)

    def test_unknown_step_type_returns_false(self):
        executor = self._make_executor()
        ok = executor._execute_single_step({"type": "totally_unknown_xyz"})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
