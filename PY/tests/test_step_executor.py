"""步骤执行器单元测试。"""
import unittest
import unittest.mock
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt5.QtWidgets import QApplication

# Ensure QApplication exists for QObject-based classes
_app = QApplication.instance() or QApplication(sys.argv)

from core.step_executor import StepExecutor


def _make_executor(config_overrides=None):
    """构造 mock 依赖并返回 StepExecutor 实例。"""
    config = unittest.mock.MagicMock()
    config.get_config.return_value = config_overrides or {}

    adb = unittest.mock.MagicMock()
    adb.tap.return_value = True
    adb.swipe.return_value = True
    adb.keyevent.return_value = True
    adb.input_text.return_value = True
    adb.force_stop.return_value = True
    adb.launch.return_value = True
    adb.wifi_enable.return_value = True
    adb.wifi_disable.return_value = True
    adb.pull_file.return_value = True
    adb.delete_file.return_value = True
    adb.shell.return_value = ""

    capture = unittest.mock.MagicMock()
    capture.get_current_frame.return_value = np.zeros((1920, 1080, 3), dtype=np.uint8)

    ocr = unittest.mock.MagicMock()
    ocr.recognize.return_value = ""
    ocr.recognize_price.return_value = 0

    device = unittest.mock.MagicMock()
    device.get_device_resolution.return_value = (1080, 1920)
    device.get_current_device.return_value = "emulator-5554"

    executor = StepExecutor(config, adb, capture, ocr, device)
    return executor, adb, capture, ocr, config


class TestStepTap(unittest.TestCase):
    def setUp(self):
        self.executor, self.adb, _, _, _ = _make_executor()

    def test_tap_calls_adb_with_scaled_coords(self):
        """tap 步骤应调用 adb.tap() 并传入缩放后的坐标。"""
        self.executor._scale_x = 1.0
        self.executor._scale_y = 1.0
        step = {"type": "tap", "x": 100, "y": 200}
        result = self.executor._step_tap(step)
        self.assertTrue(result)
        self.adb.tap.assert_called_once_with(100, 200)

    def test_tap_with_scaling(self):
        """坐标缩放应正确计算。"""
        self.executor._scale_x = 2.0
        self.executor._scale_y = 1.5
        step = {"type": "tap", "x": 100, "y": 200}
        self.executor._step_tap(step)
        self.adb.tap.assert_called_once_with(200, 300)

    def test_tap_with_wait_after(self):
        """wait_after 参数应导致可中断睡眠。"""
        step = {"type": "tap", "x": 100, "y": 200, "wait_after": 0.1}
        with unittest.mock.patch.object(self.executor, '_interruptible_sleep') as mock_sleep:
            self.executor._step_tap(step)
            mock_sleep.assert_called_once_with(0.1)


class TestStepSwipe(unittest.TestCase):
    def test_swipe_calls_adb(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "swipe", "x1": 10, "y1": 20, "x2": 30, "y2": 40, "duration": 500}
        executor._step_swipe(step)
        adb.swipe.assert_called_once_with(10, 20, 30, 40, 500)


class TestStepKeyevent(unittest.TestCase):
    def test_keyevent_calls_adb(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "keyevent", "key": "KEYCODE_HOME"}
        executor._step_keyevent(step)
        adb.keyevent.assert_called_once_with("KEYCODE_HOME")

    def test_keyevent_injection_rejected(self):
        """含注入字符的 keyevent 应被拒绝。"""
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "keyevent", "key": "3;ls"}
        self.assertFalse(executor._step_keyevent(step))
        adb.keyevent.assert_not_called()


class TestStepWait(unittest.TestCase):
    def test_wait_sleeps(self):
        executor, _, _, _, _ = _make_executor()
        step = {"type": "wait", "seconds": 0.5}
        with unittest.mock.patch.object(executor, '_interruptible_sleep') as mock_sleep:
            executor._step_wait(step)
            mock_sleep.assert_called_once_with(0.5)


class TestStepForceStop(unittest.TestCase):
    def test_force_stop_calls_adb(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "force_stop", "package": "com.tencent.tmgp.dfm"}
        executor._step_force_stop(step)
        adb.force_stop.assert_called_once_with("com.tencent.tmgp.dfm")

    def test_force_stop_injection_rejected(self):
        """非法包名应被拒绝。"""
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "force_stop", "package": "com.test;ls"}
        self.assertFalse(executor._step_force_stop(step))
        adb.force_stop.assert_not_called()


class TestStepLaunch(unittest.TestCase):
    def test_launch_calls_adb(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "launch", "package": "com.tencent.tmgp.dfm"}
        executor._step_launch(step)
        adb.launch.assert_called_once_with("com.tencent.tmgp.dfm")

    def test_launch_injection_rejected(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "launch", "package": "com.test|ls"}
        self.assertFalse(executor._step_launch(step))
        adb.launch.assert_not_called()


class TestStepScreenshot(unittest.TestCase):
    def test_screenshot_saves_frame(self):
        executor, _, capture, _, _ = _make_executor()
        step = {"type": "screenshot", "save_path": "/tmp/test.png"}
        with unittest.mock.patch("cv2.imwrite", return_value=True) as mock_write:
            result = executor._step_screenshot(step)
            self.assertTrue(result)
            mock_write.assert_called_once()

    def test_screenshot_no_frame_fails(self):
        executor, _, capture, _, _ = _make_executor()
        capture.get_current_frame.return_value = None
        step = {"type": "screenshot", "save_path": "/tmp/test.png"}
        self.assertFalse(executor._step_screenshot(step))


class TestStepCheckImage(unittest.TestCase):
    def test_check_image_found(self):
        """当模板匹配度 >= 阈值时应标记为 found。"""
        executor, _, capture, _, _ = _make_executor()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:20, 10:20] = 255
        template = frame[10:20, 10:20].copy()
        capture.get_current_frame.return_value = frame

        with unittest.mock.patch("core.step_executor.StepExecutor._load_template", return_value=template), \
             unittest.mock.patch("cv2.matchTemplate") as mock_match, \
             unittest.mock.patch("cv2.minMaxLoc", return_value=(0, 0.95, None, None)):
            mock_match.return_value = np.array([[0.95]])
            step = {"type": "check_image", "template": "test.png", "threshold": 0.85}
            executor._step_check_image(step)
            self.assertTrue(executor._last_check_result)

    def test_check_image_not_found(self):
        executor, _, capture, _, _ = _make_executor()
        capture.get_current_frame.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        with unittest.mock.patch("core.step_executor.StepExecutor._load_template", return_value=np.zeros((10, 10, 3), dtype=np.uint8)), \
             unittest.mock.patch("cv2.matchTemplate") as mock_match, \
             unittest.mock.patch("cv2.minMaxLoc", return_value=(0, 0.3, None, None)):
            mock_match.return_value = np.array([[0.3]])
            step = {"type": "check_image", "template": "test.png", "threshold": 0.85}
            executor._step_check_image(step)
            self.assertFalse(executor._last_check_result)


class TestStepOcrRegion(unittest.TestCase):
    def test_ocr_recognizes_text(self):
        executor, _, _, ocr, _ = _make_executor()
        ocr.recognize.return_value = "购买"
        step = {"type": "ocr_region", "region": {"left": 0, "top": 0, "right": 100, "bottom": 50}}
        executor._step_ocr_region(step)
        self.assertEqual(executor._last_ocr_result, "购买")

    def test_ocr_assigns_variable(self):
        executor, _, _, ocr, _ = _make_executor()
        ocr.recognize.return_value = "12000"
        step = {"type": "ocr_region", "assign_variable": "price", "region": {"left": 0, "top": 0, "right": 100, "bottom": 50}}
        executor._step_ocr_region(step)
        self.assertEqual(executor._variables["price"], "12000")


class TestStepVariable(unittest.TestCase):
    def setUp(self):
        self.executor, _, _, _, _ = _make_executor()

    def test_variable_string(self):
        step = {"type": "variable", "var_name": "x", "var_type": "string", "var_value": "hello"}
        self.executor._step_variable(step)
        self.assertEqual(self.executor._variables["x"], "hello")

    def test_variable_int(self):
        step = {"type": "variable", "var_name": "n", "var_type": "int", "var_value": "42"}
        self.executor._step_variable(step)
        self.assertEqual(self.executor._variables["n"], 42)

    def test_variable_bool(self):
        step = {"type": "variable", "var_name": "flag", "var_type": "bool", "var_value": "true"}
        self.executor._step_variable(step)
        self.assertTrue(self.executor._variables["flag"])


class TestStepCondition(unittest.TestCase):
    def test_condition_then_branch(self):
        """满足条件时执行 then_steps。"""
        executor, _, _, _, _ = _make_executor()
        with unittest.mock.patch.object(executor, '_evaluate_condition', return_value=True):
            mock_step = {"type": "wait", "seconds": 0}
            step = {"type": "condition", "check": {}, "then_steps": [mock_step], "else_steps": []}
            with unittest.mock.patch.object(executor, '_execute_single_step', return_value=True) as mock_exec:
                executor._step_condition(step)
                mock_exec.assert_called_once_with(mock_step)

    def test_condition_else_branch(self):
        executor, _, _, _, _ = _make_executor()
        with unittest.mock.patch.object(executor, '_evaluate_condition', return_value=False):
            mock_step = {"type": "wait", "seconds": 0}
            step = {"type": "condition", "check": {}, "then_steps": [], "else_steps": [mock_step]}
            with unittest.mock.patch.object(executor, '_execute_single_step', return_value=True) as mock_exec:
                executor._step_condition(step)
                mock_exec.assert_called_once_with(mock_step)


class TestStepLoop(unittest.TestCase):
    def test_loop_respects_max_count(self):
        """循环应执行 max_count 次后停止。"""
        executor, _, _, _, _ = _make_executor()
        step = {"type": "loop", "max_count": 3, "steps": [{"type": "wait", "seconds": 0}]}
        call_count = [0]
        def counting_exec(s):
            call_count[0] += 1
            return True
        with unittest.mock.patch.object(executor, '_execute_single_step', side_effect=counting_exec):
            executor._step_loop(step)
        self.assertEqual(call_count[0], 3)

    def test_loop_respects_condition(self):
        """条件不满足时循环应停止。"""
        executor, _, _, _, _ = _make_executor()
        call_count = [0]
        def side_effect(check):
            call_count[0] += 1
            return call_count[0] <= 2
        step = {"type": "loop", "max_count": -1, "condition": {}, "steps": [{"type": "wait", "seconds": 0}]}
        with unittest.mock.patch.object(executor, '_evaluate_condition', side_effect=side_effect), \
             unittest.mock.patch.object(executor, '_execute_single_step', return_value=True):
            executor._step_loop(step)
        self.assertEqual(call_count[0], 3)  # 第三次返回 False


class TestExecuteSingleStep(unittest.TestCase):
    def test_unknown_step_type_fails(self):
        executor, _, _, _, _ = _make_executor()
        step = {"type": "nonexistent_type"}
        self.assertFalse(executor._execute_single_step(step))

    def test_step_exception_returns_false(self):
        """handler 抛异常时应返回 False。"""
        executor, _, _, _, _ = _make_executor()
        step = {"type": "tap", "x": 100, "y": 200}
        with unittest.mock.patch.object(executor, '_step_tap', side_effect=RuntimeError("boom")):
            self.assertFalse(executor._execute_single_step(step))


class TestStepWifi(unittest.TestCase):
    def test_wifi_enable(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "wifi", "action": "enable"}
        executor._step_wifi(step)
        adb.wifi_enable.assert_called_once()

    def test_wifi_disable(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "wifi", "action": "disable"}
        executor._step_wifi(step)
        adb.wifi_disable.assert_called_once()


class TestStepAdbCommand(unittest.TestCase):
    def test_adb_command_safe(self):
        executor, adb, _, _, _ = _make_executor()
        adb.shell.return_value = "Physical size: 1080x1920"
        step = {"type": "adb_command", "adb_cmd": "wm size"}
        self.assertTrue(executor._step_adb_command(step))
        adb.shell.assert_called_once_with("wm size")

    def test_adb_command_injection_blocked(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "adb_command", "adb_cmd": "wm size; rm -rf /"}
        self.assertFalse(executor._step_adb_command(step))
        adb.shell.assert_not_called()

    def test_adb_command_too_long(self):
        executor, adb, _, _, _ = _make_executor()
        step = {"type": "adb_command", "adb_cmd": "wm size " * 100}
        self.assertFalse(executor._step_adb_command(step))
        adb.shell.assert_not_called()


if __name__ == "__main__":
    unittest.main()
