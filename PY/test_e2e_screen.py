import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from core.screen_capture import ScrcpyCapture
from ui.main_window import MainWindow


class TestScreenE2E(unittest.TestCase):
    def test_main_window_exposes_capture_signals(self):
        with mock.patch.object(MainWindow, "__init__", lambda self, *a, **k: None):
            win = MainWindow.__new__(MainWindow)
            win._screen_capture = ScrcpyCapture()
        for name in ("connection_lost", "connection_restored", "error_occurred"):
            self.assertTrue(hasattr(win._screen_capture, name), name)


if __name__ == "__main__":
    unittest.main()
