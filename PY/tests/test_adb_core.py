"""ADB 核心模块单元测试。"""
import unittest
import unittest.mock
import subprocess
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.adb_core import AdbCore, AdbError


class TestAdbCoreExecute(unittest.TestCase):
    """execute() 基础行为。"""

    def setUp(self):
        self.adb = AdbCore()
        self.adb.set_device("emulator-5554")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_builds_command_list(self, mock_run):
        """execute() 应构建参数列表而非字符串。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.execute(["shell", "input", "tap", "100", "200"])
        cmd = mock_run.call_args[0][0]
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd, ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_no_device(self, mock_run):
        """未设置设备时不应包含 -s 参数。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.execute(["devices"])
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["adb", "devices"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_shell_false(self, mock_run):
        """execute() 必须使用 shell=False。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.adb.execute(["shell", "echo", "test"])
        self.assertFalse(mock_run.call_args[1].get("shell", True))

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_nonzero_raises_adb_error(self, mock_run):
        """非零返回码应抛出 AdbError。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=1, stdout="", stderr="error")
        with self.assertRaises(AdbError):
            self.adb.execute(["shell", "ls"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_execute_timeout_raises_adb_error(self, mock_run):
        """超时应抛出 AdbError。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="adb", timeout=30)
        with self.assertRaises(AdbError):
            self.adb.execute(["shell", "ls"])


class TestAdbCoreActions(unittest.TestCase):
    """各操作方法测试。"""

    def setUp(self):
        self.adb = AdbCore()
        self.adb.set_device("dev1")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_tap_calls_correct_args(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.tap(100, 200))
        cmd = mock_run.call_args[0][0]
        self.assertIn("tap", cmd)
        self.assertIn("100", cmd)
        self.assertIn("200", cmd)

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_swipe_calls_correct_args(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.swipe(10, 20, 30, 40, 500))
        cmd = mock_run.call_args[0][0]
        self.assertIn("swipe", cmd)
        self.assertIn("500", cmd)

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_input_text_calls_correct_args(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.input_text("hello"))
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[-1], "hello")

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_force_stop_validates_package(self, mock_run):
        """合法包名应成功。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="", stderr="")
        self.assertTrue(self.adb.force_stop("com.tencent.tmgp.dfm"))

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_force_stop_rejects_injection(self, mock_run):
        """含注入字符的包名应被拒绝。"""
        self.assertFalse(self.adb.force_stop("com.test;rm -rf /"))
        mock_run.assert_not_called()

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_get_device_list_parses_output(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\n192.168.1.100:5555\tdevice\n",
            stderr=""
        )
        devices = self.adb.get_device_list()
        self.assertEqual(devices, ["emulator-5554", "192.168.1.100:5555"])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_get_device_list_empty(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0,
            stdout="List of devices attached\n\n",
            stderr=""
        )
        self.assertEqual(self.adb.get_device_list(), [])

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_get_device_resolution_parses(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0, stdout="Physical size: 1080x1920\n", stderr=""
        )
        w, h = self.adb.get_device_resolution()
        self.assertEqual(w, 1080)
        self.assertEqual(h, 1920)

    @unittest.mock.patch("core.adb_core.subprocess.run")
    def test_shell_uses_shlex(self, mock_run):
        """shell() 应将命令拆分为参数列表。"""
        mock_run.return_value = unittest.mock.MagicMock(returncode=0, stdout="result", stderr="")
        self.adb.shell("wm size")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["adb", "-s", "dev1", "shell", "wm", "size"])


if __name__ == "__main__":
    unittest.main()
