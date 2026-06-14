import unittest
import unittest.mock
import tempfile
import os
import json
import sys
import shutil
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.config_manager import ConfigManager
from core.adb_core import AdbCore, AdbError
from core.step_executor import StepExecutor
from core.ocr_engine import OcrEngine


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        self.temp_dir = tempfile.mkdtemp()
        config_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(ConfigManager.DEFAULT_CONFIG, f)
        with open(os.path.join(config_dir, "workflows.json"), "w", encoding="utf-8") as f:
            json.dump({"workflows": {"test_wf": {"steps": [{"type": "wait", "seconds": 1}]}}}, f)
        self.cm = ConfigManager(self.temp_dir)

    def tearDown(self):
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_config(self):
        config = self.cm._ensure_config()
        self.assertIn("buy_params", config)
        self.assertEqual(config["buy_params"]["user_price"], 0.5)

    def test_get_config(self):
        value = self.cm.get_config("buy_params.user_price")
        self.assertEqual(value, 0.5)

    def test_set_config(self):
        self.cm.set_config("buy_params.user_price", 1.0)
        self.assertEqual(self.cm.get_config("buy_params.user_price"), 1.0)
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm2 = ConfigManager(self.temp_dir)
        self.assertEqual(cm2.get_config("buy_params.user_price"), 1.0)

    def test_get_workflow(self):
        wf = self.cm.get_workflow("test_wf")
        self.assertIn("steps", wf)
        self.assertEqual(len(wf["steps"]), 1)

    def test_corrupted_recovery(self):
        config_path = os.path.join(self.temp_dir, "config", "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{corrupted!!!")
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm = ConfigManager(self.temp_dir)
        value = cm.get_config("buy_params.user_price")
        self.assertEqual(value, 0.5)


class TestAdbCore(unittest.TestCase):
    def setUp(self):
        self.adb = AdbCore()

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_without_device(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=1, stdout="", stderr="error: no devices"
        )
        with self.assertRaises(AdbError):
            self.adb.execute(["shell", "input", "tap", "100", "200"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_tap_command(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="", stderr=""
        )
        self.adb.set_device("test_device")
        self.adb.tap(100, 200)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["adb", "-s", "test_device", "shell", "input", "tap", "100", "200"])
        # shell=False
        self.assertFalse(mock_run.call_args[1].get("shell", True))

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_wifi_enable(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="", stderr=""
        )
        self.adb.set_device("test_device")
        self.adb.wifi_enable()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["adb", "-s", "test_device", "shell", "svc", "wifi", "enable"])


class TestStepExecutor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.config_manager = unittest.mock.MagicMock()
        self.config_manager.get_config.return_value = {}
        self.adb_core = unittest.mock.MagicMock()
        self.screen_capture = unittest.mock.MagicMock()
        self.ocr_engine = unittest.mock.MagicMock()
        self.device_manager = unittest.mock.MagicMock()
        self.executor = StepExecutor(
            self.config_manager, self.adb_core,
            self.screen_capture, self.ocr_engine,
            self.device_manager
        )

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_wait_step(self, mock_sleep):
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "wait", "seconds": 1.5}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_wifi_step(self, mock_sleep):
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "wifi", "action": "enable"}]
        }
        self.adb_core.wifi_enable.return_value = True
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.adb_core.wifi_enable.assert_called_once()

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_resolution_scaling(self, mock_sleep):
        self.config_manager.get_workflow.return_value = {
            "device_resolution": {"width": 2400, "height": 1080},
            "steps": [{"type": "tap", "x": 1200, "y": 540}]
        }
        self.device_manager.get_device_resolution.return_value = (1920, 900)
        self.adb_core.tap.return_value = True
        def _cfg(key, default=None):
            if key == "coordinate":
                return {"auto_scale": True, "warn_on_mismatch": True}
            if key == "execution.policy":
                return {}
            return default if default is not None else {}
        self.config_manager.get_config.side_effect = _cfg
        self.executor = StepExecutor(
            self.config_manager, self.adb_core,
            self.screen_capture, self.ocr_engine,
            self.device_manager
        )
        self.executor.execute_step("test_wf", 0)
        expected_x = int(round(1200 * 1920 / 2400))
        expected_y = int(round(540 * 900 / 1080))
        self.adb_core.tap.assert_called_once_with(expected_x, expected_y)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_error_recovery_skip(self, mock_sleep):
        self.config_manager.get_workflow.return_value = {
            "steps": [
                {"type": "tap", "x": 100, "y": 200, "on_fail": "skip"},
                {"type": "wait", "seconds": 0.5}
            ]
        }
        self.adb_core.tap.return_value = False
        result = self.executor.execute_workflow("test_wf")
        self.assertTrue(result)



    @unittest.mock.patch('core.step_executor.time.sleep')
    def test_tap_point_uses_scale_coord(self, mock_sleep):
        """tap_point 应像 tap 一样调用 _scale_coord()"""
        self.config_manager.get_workflow.return_value = {
            "device_resolution": {"width": 2400, "height": 1080},
            "steps": [{"type": "tap_point", "x": 100, "y": 200}]
        }
        self.device_manager.get_device_resolution.return_value = (1920, 900)
        self.adb_core.tap.return_value = True
        def _cfg(key, default=None):
            if key == 'coordinate':
                return {"auto_scale": True, "warn_on_mismatch": True}
            if key == 'execution.policy':
                return {}
            return default if default is not None else {}
        self.config_manager.get_config.side_effect = _cfg
        self.executor = StepExecutor(
            self.config_manager, self.adb_core,
            self.screen_capture, self.ocr_engine,
            self.device_manager
        )
        self.executor.execute_step('test_wf', 0)
        expected_x = int(round(100 * 1920 / 2400))
        expected_y = int(round(200 * 900 / 1080))
        self.adb_core.tap.assert_called_once_with(expected_x, expected_y)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_adb_command_safe(self, mock_sleep):
        """adb_command with valid shell command should succeed."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "adb_command", "adb_cmd": "wm size"}]
        }
        self.adb_core.shell.return_value = "Physical size: 2400x1080"
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.adb_core.shell.assert_called_once_with("wm size")

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_adb_command_injection_blocked(self, mock_sleep):
        """adb_command with injection characters should be rejected."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "adb_command", "adb_cmd": "wm size; rm -rf /"}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertFalse(result)
        self.adb_core.shell.assert_not_called()

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_adb_command_pipe_blocked(self, mock_sleep):
        """adb_command with pipe should be rejected."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "adb_command", "adb_cmd": "cat /proc/cpuinfo | grep model"}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertFalse(result)
        self.adb_core.shell.assert_not_called()

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_adb_command_too_long(self, mock_sleep):
        """adb_command exceeding max length should be rejected."""
        long_cmd = "wm size " * 100
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "adb_command", "adb_cmd": long_cmd}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertFalse(result)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_adb_command_assign_variable(self, mock_sleep):
        """adb_command with assign_variable should store result."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "adb_command", "adb_cmd": "wm size", "assign_variable": "resolution"}]
        }
        self.adb_core.shell.return_value = "Physical size: 2400x1080"
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.assertEqual(self.executor.get_variable("resolution"), "Physical size: 2400x1080")

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_expression_step(self, mock_sleep):
        """expression step should evaluate and store result."""
        self.executor.set_variable("price", 100)
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "expression", "expression": "price * 2 + 10", "assign_variable": "total"}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.assertEqual(self.executor.get_variable("total"), 210)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_expression_invalid(self, mock_sleep):
        """expression step with invalid expression should fail."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "expression", "expression": "import os"}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertFalse(result)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_variable_step(self, mock_sleep):
        """variable step should set a variable."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "variable", "var_name": "counter", "var_type": "int", "var_value": "42"}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.assertEqual(self.executor.get_variable("counter"), 42)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_condition_step_true(self, mock_sleep):
        """condition step should execute then_steps when condition is true."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{
                "type": "condition",
                "check": {"type": "image_found", "template": "test.jpg", "threshold": 0.5},
                "then_steps": [{"type": "wait", "seconds": 0.1}],
                "else_steps": [],
            }]
        }
        with unittest.mock.patch.object(self.executor, "_check_image_found", return_value=True):
            result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_condition_step_false(self, mock_sleep):
        """condition step should execute else_steps when condition is false."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{
                "type": "condition",
                "check": {"type": "image_found", "template": "test.jpg", "threshold": 0.99},
                "then_steps": [],
                "else_steps": [{"type": "wait", "seconds": 0.1}],
            }]
        }
        with unittest.mock.patch.object(self.executor, "_check_image_found", return_value=False):
            result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_loop_step_count(self, mock_sleep):
        """loop step should execute inner steps N times."""
        call_count = [0]
        original_wait = self.executor._step_wait
        def counting_wait(step):
            call_count[0] += 1
            return True
        self.executor._step_wait = counting_wait
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "loop", "max_count": 3, "steps": [{"type": "wait", "seconds": 0.1}]}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.assertEqual(call_count[0], 3)
        self.executor._step_wait = original_wait

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_loop_step_zero_count(self, mock_sleep):
        """loop step with max_count=0 should not execute."""
        call_count = [0]
        original_wait = self.executor._step_wait
        def counting_wait(step):
            call_count[0] += 1
            return True
        self.executor._step_wait = counting_wait
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "loop", "max_count": 0, "steps": [{"type": "wait", "seconds": 0.1}]}]
        }
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.assertEqual(call_count[0], 0)
        self.executor._step_wait = original_wait

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_loop_step_inner_failure(self, mock_sleep):
        """loop step should fail if inner step fails."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "loop", "max_count": 5, "steps": [{
                "type": "wait", "seconds": 0.1
            }]}]
        }
        call_count = [0]
        def fail_after_two(step):
            call_count[0] += 1
            return call_count[0] <= 2
        with unittest.mock.patch.object(self.executor, "_step_wait", side_effect=fail_after_two):
            result = self.executor.execute_step("test_wf", 0)
        self.assertFalse(result)
        self.assertGreaterEqual(call_count[0], 3)

    @unittest.mock.patch("core.step_executor.time.sleep")
    def test_execute_input_text_step(self, mock_sleep):
        """input_text step should call adb_core.input_text."""
        self.config_manager.get_workflow.return_value = {
            "steps": [{"type": "input_text", "text": "hello"}]
        }
        self.adb_core.input_text.return_value = True
        result = self.executor.execute_step("test_wf", 0)
        self.assertTrue(result)
        self.adb_core.input_text.assert_called_once_with("hello")

class TestOcrEngine(unittest.TestCase):
    def setUp(self):
        OcrEngine._instance = None

    def tearDown(self):
        OcrEngine._instance = None

    def test_singleton(self):
        engine1 = OcrEngine()
        engine2 = OcrEngine()
        self.assertIs(engine1, engine2)

    def test_not_initialized(self):
        engine = OcrEngine()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.recognize(image)
        self.assertEqual(result, "")

    def test_price_cleaning(self):
        engine = OcrEngine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [
            [[0, 0, 100, 30], "1,234,568", 0.95]
        ]
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.recognize_price(image)
        self.assertEqual(result, 1234560)


if __name__ == "__main__":
    unittest.main()
