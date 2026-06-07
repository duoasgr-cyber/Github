"""Workflow replay tests - verifies core modules work end-to-end with mocks."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.error_policy import (
    ErrorPolicyConfig, ErrorPolicyExecutor, ErrorCategory,
    classify_error, classify_step_failure, ErrorPolicy
)
from core.expression_eval import evaluate_expression, step_expression, ExpressionError
from core.config_migrator import (
    validate_config, validate_workflow, validate_workflows,
    migrate_config, CURRENT_CONFIG_VERSION
)


class TestErrorPolicy(unittest.TestCase):
    def test_default_config(self):
        cfg = ErrorPolicyConfig()
        self.assertEqual(cfg.default_policy, ErrorPolicy.FAIL)
        self.assertEqual(cfg.max_retries, 3)

    def test_classify_adb_timeout(self):
        cat = classify_error(TimeoutError("connection timed out"))
        self.assertEqual(cat, ErrorCategory.ADB_TIMEOUT)

    def test_classify_ocr_fail(self):
        cat = classify_step_failure("ocr_region", "ocr failed to recognize")
        self.assertEqual(cat, ErrorCategory.OCR_FAIL)

    def test_classify_template_not_found(self):
        cat = classify_step_failure("check_image", "template not found")
        self.assertEqual(cat, ErrorCategory.TEMPLATE_NOT_FOUND)

    def test_policy_override_in_step(self):
        cfg = ErrorPolicyConfig()
        policy = cfg.get_policy(ErrorCategory.ADB_TIMEOUT, step_override="skip")
        self.assertEqual(policy, ErrorPolicy.SKIP)

    def test_policy_category_default(self):
        cfg = ErrorPolicyConfig()
        policy = cfg.get_policy(ErrorCategory.ADB_TIMEOUT)
        self.assertEqual(policy, ErrorPolicy.RETRY)

    def test_executor_skip_policy(self):
        cfg = ErrorPolicyConfig({"default_policy": "skip"})
        executor = ErrorPolicyExecutor(cfg)
        call_count = 0
        def failing_step(step):
            nonlocal call_count
            call_count += 1
            return False
        result = executor.execute_with_policy({"type": "tap"}, failing_step)
        self.assertTrue(result)
        self.assertEqual(call_count, 1)

    def test_executor_retry_policy(self):
        cfg = ErrorPolicyConfig({"default_policy": "retry", "max_retries": 2, "retry_delay": 0.01})
        executor = ErrorPolicyExecutor(cfg)
        call_count = 0
        def fail_then_succeed(step):
            nonlocal call_count
            call_count += 1
            return call_count >= 3
        result = executor.execute_with_policy({"type": "tap"}, fail_then_succeed)
        self.assertTrue(result)
        self.assertEqual(call_count, 3)

    def test_executor_fail_policy(self):
        cfg = ErrorPolicyConfig({"default_policy": "fail"})
        executor = ErrorPolicyExecutor(cfg)
        result = executor.execute_with_policy({"type": "tap"}, lambda step: False)
        self.assertFalse(result)


class TestExpressionEval(unittest.TestCase):
    def test_simple_arithmetic(self):
        self.assertEqual(evaluate_expression("2 + 3 * 4"), 14)

    def test_variables(self):
        self.assertEqual(evaluate_expression("x + y", {"x": 10, "y": 20}), 30)

    def test_comparison(self):
        self.assertTrue(evaluate_expression("price > 100", {"price": 150}))

    def test_bool_expression(self):
        self.assertTrue(evaluate_expression("a > 0 and b > 0", {"a": 1, "b": 2}))

    def test_if_expression(self):
        self.assertEqual(evaluate_expression("1 if x > 5 else 0", {"x": 10}), 1)

    def test_safe_function(self):
        self.assertEqual(evaluate_expression("abs(-42)"), 42)

    def test_undefined_variable(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression("x + y", {"x": 1})

    def test_empty_expression(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression("")

    def test_step_expression_assign(self):
        variables = {"price": 100}
        step = {"expression": "price * 2 + 10", "assign_variable": "total"}
        result = step_expression(step, variables)
        self.assertTrue(result)
        self.assertEqual(variables["total"], 210)


class TestConfigMigrator(unittest.TestCase):
    def test_validate_config_valid(self):
        config = {
            "buy_params": {"user_price": 0.5, "max_mail_count": 100},
            "mail_params": {}, "recognition": {},
            "device": {"base_resolution": {"width": 2400, "height": 1080}},
            "timing": {}, "logging": {"log_file": "app.log"}
        }
        valid, issues = validate_config(config)
        self.assertTrue(valid, f"Issues: {issues}")

    def test_validate_config_missing_keys(self):
        valid, issues = validate_config({"buy_params": {}})
        self.assertFalse(valid)
        self.assertTrue(len(issues) > 0)

    def test_validate_workflow_valid(self):
        wf = {"steps": [{"type": "tap", "x": 100, "y": 200}]}
        valid, issues = validate_workflow("test", wf)
        self.assertTrue(valid, f"Issues: {issues}")

    def test_validate_workflow_no_steps(self):
        valid, issues = validate_workflow("test", {})
        self.assertFalse(valid)

    def test_migrate_v1_to_v2(self):
        config = {"buy_params": {"user_price": 1}}
        migrated, was_migrated = migrate_config(config)
        self.assertTrue(was_migrated)
        self.assertEqual(migrated["config_version"], 2)
        self.assertIn("execution", migrated)
        self.assertIn("coordinate", migrated)

    def test_no_migration_needed(self):
        config = {"config_version": CURRENT_CONFIG_VERSION}
        migrated, was_migrated = migrate_config(config)
        self.assertFalse(was_migrated)


if __name__ == "__main__":
    unittest.main()
