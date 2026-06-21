import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\tests\test_screen_capture.py'

# Write clean test file
content = '''import unittest
from unittest import mock

import numpy as np

from core.screen_capture import ScrcpyCapture


class TestScrcpyCaptureUnit(unittest.TestCase):
    """Unit tests for ScrcpyCapture core logic."""

    def _make_started_capture(self):
        """Helper: return a ScrcpyCapture that looks like it was started."""
        c = ScrcpyCapture()
        c._device_serial = "FAKE123"
        c._server_jar_path = "lib/scrcpy-server.jar"
        c._forward_port = 27183
        c._server_process = mock.MagicMock()
        c._ffmpeg_process = mock.MagicMock()
        c._socket = mock.MagicMock()
        c._stopping = False
        c._connected = True
        c._use_scrcpy = True
        c._current_frame = np.zeros((2, 2, 3), dtype=np.uint8)
        return c

    # ------------------------------------------------------------------ #
    # 1. start() falls back to screencap when scrcpy fails
    # ------------------------------------------------------------------ #
    @mock.patch(
        "core.screen_capture.subprocess.run",
        return_value=mock.MagicMock(returncode=0, stdout=b"", stderr=b""),
    )
    def test_start_returns_true_when_scrcpy_fails(self, mock_run):
        c = ScrcpyCapture()
        with mock.patch.object(c, "_start_scrcpy", side_effect=RuntimeError("boom")), \\
             mock.patch.object(c, "_start_fallback_reader", return_value=None), \\
             mock.patch("core.screen_capture.time.sleep", return_value=None):
            ok = c.start("FAKE123", "lib/scrcpy-server.jar", max_retries=1)
        self.assertTrue(ok)
        self.assertFalse(c._use_scrcpy)
        self.assertTrue(c._connected)

    # ------------------------------------------------------------------ #
    # 2. stop() sets flags and clears resources
    # ------------------------------------------------------------------ #
    def test_stop_sets_flags_and_clears_state(self):
        c = self._make_started_capture()
        c.stop()
        self.assertTrue(c._stopping)
        self.assertFalse(c._connected)
        self.assertIsNone(c._socket)
        self.assertIsNone(c._ffmpeg_process)

    # ------------------------------------------------------------------ #
    # 3. get_current_frame returns None when empty
    # ------------------------------------------------------------------ #
    def test_get_current_frame_returns_none_when_empty(self):
        c = self._make_started_capture()
        c._current_frame = None
        self.assertIsNone(c.get_current_frame())

    # ------------------------------------------------------------------ #
    # 4. get_current_frame returns a copy (not the original array)
    # ------------------------------------------------------------------ #
    def test_get_current_frame_returns_copy(self):
        c = self._make_started_capture()
        out = c.get_current_frame()
        self.assertIsNotNone(out)
        self.assertEqual(out.shape, (2, 2, 3))
        out[:] = 255
        self.assertTrue((c._current_frame == 0).all())

    # ------------------------------------------------------------------ #
    # 5. Connection failure emits error_occurred signal
    # ------------------------------------------------------------------ #
    def test_connect_failure_emits_error_signal(self):
        c = ScrcpyCapture()
        errors = []
        c.error_occurred.connect(lambda msg: errors.append(msg))
        with mock.patch.object(c, "_start_scrcpy", side_effect=RuntimeError("x")), \\
             mock.patch.object(c, "_start_fallback_reader", return_value=None), \\
             mock.patch("core.screen_capture.time.sleep", return_value=None):
            c.start("FAKE123", "lib/scrcpy-server.jar", max_retries=1)
        self.assertTrue(errors)


class TestScrcpyCaptureCompat(unittest.TestCase):
    """Compatibility / sanity tests."""

    def test_forward_port_fallback_is_numeric(self):
        c = ScrcpyCapture()
        self.assertIsInstance(c._forward_port, int)

    def test_start_accepts_optional_max_retries(self):
        c = ScrcpyCapture()
        with mock.patch.object(c, "_start_scrcpy", side_effect=RuntimeError("boom")), \\
             mock.patch.object(c, "_start_fallback_reader", return_value=None), \\
             mock.patch("core.screen_capture.time.sleep", return_value=None):
            ok = c.start("DEV", "lib/scrcpy-server.jar", max_retries=2)
        self.assertTrue(ok)
        self.assertEqual(c._max_reconnect, 2)


if __name__ == "__main__":
    unittest.main()
'''

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Wrote clean test file")
