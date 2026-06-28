"""递归防护回归测试：A→B→A 循环与深度超限必须返回 False 且不栈溢出。

对应 P1-2：execute_workflow 加 max_call_depth=8 + _workflow_call_stack 循环检测。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtCore import QObject
    from core.config_manager import ConfigManager
    from core.step_executor import StepExecutor
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


@unittest.skipUnless(HAS_PYQT, "PyQt5 not installed")
class TestCallWorkflowRecursion(unittest.TestCase):
    def _make_executor_with_cycle(self):
        """构造 A→B→A 循环配置：A 调用 B，B 调用 A。"""
        import tempfile
        import json
        tmp = tempfile.mkdtemp(prefix="recursion_")
        cfg_dir = os.path.join(tmp, "config")
        os.makedirs(cfg_dir)
        with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(ConfigManager.DEFAULT_CONFIG, f)
        workflows = {
            "workflows": {
                "A": {"steps": [{"type": "call_workflow", "workflow": "B"}]},
                "B": {"steps": [{"type": "call_workflow", "workflow": "A"}]},
            }
        }
        with open(os.path.join(cfg_dir, "workflows.json"), "w", encoding="utf-8") as f:
            json.dump(workflows, f)

        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm = ConfigManager(tmp)

        executor = StepExecutor.__new__(StepExecutor)
        QObject.__init__(executor)
        executor._config_manager = cm
        executor._running = False
        executor._paused = False
        executor._stop_requested = False
        executor._current_workflow = None
        executor._current_step_index = -1
        executor._scale_x = 1.0
        executor._scale_y = 1.0
        executor._workflow_depth = 0
        executor._workflow_call_stack = []
        executor._variables = {}
        import threading
        executor._pause_event = threading.Event()
        executor._pause_event.set()
        executor._error_policy_config = None
        executor._error_executor = None
        return executor, tmp

    def test_cycle_detected(self):
        executor, tmp = self._make_executor_with_cycle()
        try:
            result = executor.execute_workflow("A")
            self.assertFalse(result, "Cycle should be rejected with False")
            # 顶层的 _workflow_call_stack 必须在 finally 中清空
            self.assertEqual(executor._workflow_call_stack, [])
            self.assertEqual(executor._workflow_depth, 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_max_depth_enforced(self):
        """构造 self-loop A→A，max_call_depth=8 应在递归到第 9 层时拒绝。"""
        import tempfile
        import json
        import threading
        tmp = tempfile.mkdtemp(prefix="maxdepth_")
        cfg_dir = os.path.join(tmp, "config")
        os.makedirs(cfg_dir)
        cfg = dict(ConfigManager.DEFAULT_CONFIG)
        cfg.setdefault("execution", {})["max_call_depth"] = 3
        with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        workflows = {
            "workflows": {
                "A": {"steps": [{"type": "call_workflow", "workflow": "A"}]},
            }
        }
        with open(os.path.join(cfg_dir, "workflows.json"), "w", encoding="utf-8") as f:
            json.dump(workflows, f)

        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm = ConfigManager(tmp)

        executor = StepExecutor.__new__(StepExecutor)
        QObject.__init__(executor)
        executor._config_manager = cm
        executor._running = False
        executor._paused = False
        executor._stop_requested = False
        executor._current_workflow = None
        executor._current_step_index = -1
        executor._scale_x = 1.0
        executor._scale_y = 1.0
        executor._workflow_depth = 0
        executor._workflow_call_stack = []
        executor._variables = {}
        executor._pause_event = threading.Event()
        executor._pause_event.set()
        executor._error_policy_config = None
        executor._error_executor = None

        try:
            result = executor.execute_workflow("A")
            self.assertFalse(result, "Max-depth recursion should be rejected with False")
            self.assertEqual(executor._workflow_depth, 0)
            self.assertEqual(executor._workflow_call_stack, [])
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
