"""ADB 命令注入防护测试。"""
import unittest
import unittest.mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.adb_core import (
    AdbCore, AdbError,
    _validate_package, _validate_keyevent, _validate_path,
)


class TestInputValidation(unittest.TestCase):
    """验证输入校验函数。"""

    def test_validate_package_valid(self):
        self.assertTrue(_validate_package("com.tencent.tmgp.dfm"))

    def test_validate_package_with_dots_and_underscores(self):
        self.assertTrue(_validate_package("com.example.my_app"))

    def test_validate_package_injection_semicolon(self):
        self.assertFalse(_validate_package("com.test;rm -rf /"))

    def test_validate_package_injection_pipe(self):
        self.assertFalse(_validate_package("com.test|ls"))

    def test_validate_package_injection_dollar(self):
        self.assertFalse(_validate_package("com.test$(whoami)"))

    def test_validate_package_empty(self):
        self.assertFalse(_validate_package(""))

    def test_validate_package_none(self):
        self.assertFalse(_validate_package(None))

    def test_validate_keyevent_valid_name(self):
        self.assertTrue(_validate_keyevent("KEYCODE_HOME"))

    def test_validate_keyevent_valid_number(self):
        self.assertTrue(_validate_keyevent("3"))

    def test_validate_keyevent_injection_semicolon(self):
        self.assertFalse(_validate_keyevent("3;ls"))

    def test_validate_keyevent_injection_pipe(self):
        self.assertFalse(_validate_keyevent("3|cat"))

    def test_validate_keyevent_empty(self):
        self.assertFalse(_validate_keyevent(""))

    def test_validate_path_valid(self):
        self.assertTrue(_validate_path("/data/local/tmp/screenshot.png"))

    def test_validate_path_valid_windows_local(self):
        self.assertTrue(_validate_path("C:\\Users\\test\\screenshot.png"))

    def test_validate_path_injection_semicolon(self):
        self.assertFalse(_validate_path("/tmp/test;rm -rf /"))

    def test_validate_path_injection_pipe(self):
        self.assertFalse(_validate_path("/tmp/test|ls"))

    def test_validate_path_injection_dollar(self):
        self.assertFalse(_validate_path("/tmp/test$(cmd)"))

    def test_validate_path_injection_backtick(self):
        self.assertFalse(_validate_path("/tmp/`whoami`"))

    def test_validate_path_empty(self):
        self.assertFalse(_validate_path(""))


class TestAdbCoreShellFalse(unittest.TestCase):
    """验证 execute() 使用 shell=False 和参数列表。"""

    def setUp(self):
        self.adb = AdbCore()
        self.adb.set_device("emulator-5554")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_uses_shell_false(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.execute(["shell", "input", "tap", "100", "200"])
        self.assertFalse(mock_run.call_args[1].get("shell", True))

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_builds_list_args(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.tap(100, 200)
        cmd = mock_run.call_args[0][0]
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], "adb")
        self.assertIn("-s", cmd)
        self.assertIn("shell", cmd)
        self.assertIn("tap", cmd)
        self.assertIn("100", cmd)
        self.assertIn("200", cmd)

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_tap_no_fstring_injection(self, mock_run):
        """tap 的参数应作为独立列表元素传递，不拼接到 shell 字符串。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.tap(100, 200)
        cmd = mock_run.call_args[0][0]
        # 参数应是独立元素，不是 "adb -s dev shell input tap 100 200" 这样的字符串
        self.assertEqual(cmd, ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_force_stop_injection_rejected(self, mock_run):
        """含注入字符的包名应被拒绝，不调用 subprocess。"""
        result = self.adb.force_stop("com.test;rm -rf /")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_launch_injection_rejected(self, mock_run):
        result = self.adb.launch("com.test|ls")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_keyevent_injection_rejected(self, mock_run):
        result = self.adb.keyevent("3;ls")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_input_text_passes_text_safely(self, mock_run):
        """input_text 应将文本作为列表参数传递。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.input_text("hello world")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[-1], "hello world")
        self.assertFalse(mock_run.call_args[1].get("shell", True))

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_shell_uses_shlex(self, mock_run):
        """shell() 应将命令拆分为参数列表。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="result", stderr="")
        self.adb.shell("wm size")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["adb", "-s", "emulator-5554", "shell", "wm", "size"])


class TestAdbCoreActions(unittest.TestCase):
    """各操作方法验证。"""

    def setUp(self):
        self.adb = AdbCore()
        self.adb.set_device("dev1")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_swipe_args(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.swipe(10, 20, 30, 40, 500)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["adb", "-s", "dev1", "shell", "input", "swipe", "10", "20", "30", "40", "500"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_force_stop_valid_package(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.force_stop("com.tencent.tmgp.dfm"))
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["adb", "-s", "dev1", "shell", "am", "force-stop", "com.tencent.tmgp.dfm"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_launch_valid_package(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.launch("com.tencent.tmgp.dfm"))
        cmd = mock_run.call_args[0][0]
        self.assertIn("monkey", cmd)
        self.assertIn("com.tencent.tmgp.dfm", cmd)

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_get_device_list_parses(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\n192.168.1.100:5555\tdevice\n",
            stderr=""
        )
        devices = self.adb.get_device_list()
        self.assertEqual(devices, ["emulator-5554", "192.168.1.100:5555"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_get_device_resolution_parses(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="Physical size: 1080x1920\n", stderr=""
        )
        w, h = self.adb.get_device_resolution()
        self.assertEqual(w, 1080)
        self.assertEqual(h, 1920)


if __name__ == "__main__":
    unittest.main()
