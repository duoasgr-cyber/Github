"""Stability tests - verifies error recovery and long-running behavior."""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.error_policy import (
    ErrorPolicyConfig, ErrorPolicyExecutor, ErrorPolicy,
    ErrorCategory, classify_step_failure
)
from core.telemetry import Telemetry
from core.structured_log import LogCollector


class TestErrorRecoveryStability(unittest.TestCase):
    """Test error recovery under repeated failures."""

    def test_retry_exhaustion(self):
        cfg = ErrorPolicyConfig({"default_policy": "retry", "max_retries": 5, "retry_delay": 0.001})
        executor = ErrorPolicyExecutor(cfg)
        call_count = 0
        def always_fail(step):
            nonlocal call_count
            call_count += 1
            return False
        result = executor.execute_with_policy({"type": "tap"}, always_fail)
        self.assertFalse(result)
        self.assertEqual(call_count, 6)  # 1 initial + 5 retries

    def test_backoff_timing(self):
        cfg = ErrorPolicyConfig({
            "default_policy": "backoff",
            "max_retries": 3,
            "retry_delay": 0.01,
            "backoff_base": 2.0,
            "backoff_max": 1.0
        })
        executor = ErrorPolicyExecutor(cfg)
        start = time.time()
        executor.execute_with_policy({"type": "tap"}, lambda s: False)
        elapsed = time.time() - start
        # Should have taken at least 0.01 + 0.02 + 0.04 = 0.07s
        self.assertGreater(elapsed, 0.05)

    def test_mixed_policies(self):
        cfg = ErrorPolicyConfig({
            "default_policy": "fail",
            "max_retries": 2,
            "retry_delay": 0.001,
            "category_overrides": {
                "adb_timeout": "retry",
                "template_not_found": "skip"
            }
        })
        # Template not found should skip
        cat = classify_step_failure("check_image", "template not found at tp/x.jpg")
        self.assertEqual(cat, ErrorCategory.TEMPLATE_NOT_FOUND)
        policy = cfg.get_policy(cat)
        self.assertEqual(policy, ErrorPolicy.SKIP)

    def test_stop_check_during_retry(self):
        cfg = ErrorPolicyConfig({"default_policy": "retry", "max_retries": 100, "retry_delay": 0.01})
        stop_flag = {"stopped": False}
        executor = ErrorPolicyExecutor(cfg, stop_check=lambda: stop_flag["stopped"])
        call_count = 0
        def counting_fail(step):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                stop_flag["stopped"] = True
            return False
        result = executor.execute_with_policy({"type": "tap"}, counting_fail)
        self.assertFalse(result)
        self.assertLessEqual(call_count, 5)  # Should stop early


class TestTelemetryStability(unittest.TestCase):
    """Test telemetry collection under load."""

    def setUp(self):
        Telemetry._instance = None
        self.tm = Telemetry()

    def tearDown(self):
        Telemetry._instance = None

    def test_high_volume_events(self):
        for i in range(2000):
            self.tm.record_step_execution("tap", success=(i % 3 != 0))
        stats = self.tm.get_session_stats()
        self.assertEqual(stats["step_counts"]["tap"], 2000)
        self.assertGreater(stats["failure_counts"]["tap"], 0)

    def test_workflow_lifecycle(self):
        self.tm.record_workflow_start("test_wf")
        self.tm.record_workflow_complete("test_wf", 5.2)
        stats = self.tm.get_session_stats()
        self.assertEqual(stats["workflow_runs"], 1)
        self.assertEqual(stats["workflow_completions"], 1)

    def test_crash_report(self):
        self.tm.record_crash("ValueError", "bad value", "Traceback...")
        stats = self.tm.get_session_stats()
        self.assertEqual(stats["crash_count"], 1)

    def test_export_events(self):
        import tempfile
        self.tm.record_workflow_start("test")
        tmp = tempfile.mktemp(suffix=".json")
        try:
            result = self.tm.export_events(tmp)
            self.assertTrue(result)
            import json
            with open(tmp, "r") as f:
                data = json.load(f)
            self.assertIn("session_stats", data)
            self.assertIn("events", data)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


class TestLogCollectorStability(unittest.TestCase):
    """Test log collector under high volume."""

    def test_max_entries(self):
        collector = LogCollector(max_entries=100)
        for i in range(200):
            record = logging.LogRecord("test", logging.INFO, "", 0, f"msg {i}", (), None)
            collector.add_entry(record)
        self.assertEqual(collector.count, 100)

    def test_export_json(self):
        import tempfile
        collector = LogCollector()
        record = logging.LogRecord("test", logging.INFO, "", 0, "test msg", (), None)
        collector.add_entry(record)
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            result = collector.export_json(tmp)
            self.assertTrue(result)
            with open(tmp, "r") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_export_csv(self):
        import tempfile
        collector = LogCollector()
        record = logging.LogRecord("test", logging.WARNING, "", 0, "warn msg", (), None)
        collector.add_entry(record)
        tmp = tempfile.mktemp(suffix=".csv")
        try:
            result = collector.export_csv(tmp)
            self.assertTrue(result)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


import logging


if __name__ == "__main__":
    unittest.main()
