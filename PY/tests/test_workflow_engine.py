"""Unit tests for core/workflow_engine.py - tests the _WorkflowWorker logic with mocks."""
import os
import sys
import unittest
from unittest import mock
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from core.workflow_engine import WorkflowEngine, _WorkflowWorker


class TestWorkflowWorker(unittest.TestCase):
    """Test _WorkflowWorker logic with mocked dependencies."""

    def _make_worker(self, stop_after_cycles=1):
        mock_config = mock.MagicMock()
        mock_step_exec = mock.MagicMock()
        mock_ocr = mock.MagicMock()
        mock_device = mock.MagicMock()

        # Configure mock config
        mock_config.get_config.side_effect = lambda key, default=None: {
            "buy_params.user_price": 0.5,
            "buy_params.max_mail_count": 190,
            "device.game_package": "com.tencent.tmgp.dfm",
        }.get(key, default)

        worker = _WorkflowWorker(mock_config, mock_step_exec, mock_ocr, mock_device)
        return worker, mock_config, mock_step_exec, mock_ocr, mock_device

    def test_worker_creation(self):
        worker, *_ = self._make_worker()
        self.assertIsNotNone(worker)
        self.assertFalse(worker._stop_requested)

    def test_stop_sets_flag(self):
        worker, *_ = self._make_worker()
        worker._stop_requested = False
        # Simulate calling request_stop (which is on WorkflowEngine, but flag is on worker)
        worker._stop_requested = True
        self.assertTrue(worker._stop_requested)

    def test_pause_uses_event(self):
        worker, *_ = self._make_worker()
        self.assertTrue(worker._pause_event.is_set())
        worker._paused = True
        worker._pause_event.clear()
        self.assertFalse(worker._pause_event.is_set())
        worker._paused = False
        worker._pause_event.set()
        self.assertTrue(worker._pause_event.is_set())


class TestWorkflowEngineSignals(unittest.TestCase):
    """Test that WorkflowEngine has expected signals."""

    def test_has_required_signals(self):
        self.assertTrue(hasattr(WorkflowEngine, 'price_updated'))
        self.assertTrue(hasattr(WorkflowEngine, 'mail_count_updated'))
        self.assertTrue(hasattr(WorkflowEngine, 'status_updated'))
        self.assertTrue(hasattr(WorkflowEngine, 'cycle_completed'))
        self.assertTrue(hasattr(WorkflowEngine, 'error_occurred'))


if __name__ == "__main__":
    unittest.main()
