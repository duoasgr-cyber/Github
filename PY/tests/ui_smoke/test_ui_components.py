"""UI smoke tests - verifies basic UI components initialize correctly."""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.empty_state_widget import EmptyStateWidget, LoadingOverlay, BlockingReason
from ui.components.step_list_widget import StepListWidget


class TestEmptyStateWidget(unittest.TestCase):
    def test_create_default(self):
        w = EmptyStateWidget()
        self.assertIsNotNone(w)

    def test_set_state(self):
        w = EmptyStateWidget()
        w.set_state(icon="?", message="Test", hint="Hint")
        self.assertEqual(w._icon_text, "?")
        self.assertEqual(w._message, "Test")

    def test_set_blocking(self):
        w = EmptyStateWidget()
        w.set_blocking(BlockingReason.NO_DEVICE)
        self.assertEqual(w._blocking_reason, BlockingReason.NO_DEVICE)
        self.assertIn("Device", w._message)

    def test_clear_blocking(self):
        w = EmptyStateWidget()
        w.set_blocking(BlockingReason.NO_DEVICE)
        w.clear_blocking()
        self.assertIsNone(w._blocking_reason)

    def test_all_blocking_reasons(self):
        for reason in BlockingReason:
            w = EmptyStateWidget()
            w.set_blocking(reason)
            self.assertIsNotNone(w._message)
            self.assertIsNotNone(w._icon_text)


class TestLoadingOverlay(unittest.TestCase):
    def test_create(self):
        w = LoadingOverlay("Loading...")
        self.assertIsNotNone(w)
        self.assertFalse(w.isVisible())

    def test_start_stop(self):
        w = LoadingOverlay()
        w.start("Please wait")
        self.assertTrue(w.isVisible())
        w.stop()
        self.assertFalse(w.isVisible())


class TestStepListWidget(unittest.TestCase):
    def test_create(self):
        w = StepListWidget()
        self.assertIsNotNone(w)

    def test_load_steps(self):
        w = StepListWidget()
        steps = [
            {"type": "tap", "x": 100, "y": 200},
            {"type": "wait", "seconds": 1},
        ]
        w.load_steps(steps)
        self.assertEqual(w._raw_steps, steps)

    def test_set_step_state(self):
        w = StepListWidget()
        steps = [{"type": "tap", "x": 100, "y": 200}]
        w.load_steps(steps)
        w.set_step_state(0, "running")
        self.assertEqual(w._step_states[0], "running")

    def test_clear_step_states(self):
        w = StepListWidget()
        steps = [{"type": "tap", "x": 100, "y": 200}]
        w.load_steps(steps)
        w.set_step_state(0, "success")
        w.clear_step_states()
        self.assertEqual(len(w._step_states), 0)


if __name__ == "__main__":
    unittest.main()
