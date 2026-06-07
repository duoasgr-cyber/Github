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
            self.adb.execute("shell input tap 100 200")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_tap_command(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="", stderr=""
        )
        self.adb.set_device("test_device")
        self.adb.tap(100, 200)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, "adb -s test_device shell input tap 100 200")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_wifi_enable(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="", stderr=""
        )
        self.adb.set_device("test_device")
        self.adb.wifi_enable()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, "adb -s test_device shell svc wifi enable")


class TestStepExecutor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.config_manager = unittest.mock.MagicMock()
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
