"""Unified error handling and recovery policy for step execution.

Policies:
  retry       - retry with linear delay
  backoff     - retry with exponential backoff
  skip        - skip failed step and continue
  fail        - fail the current workflow
  abort       - abort all execution immediately

Error categories map to default policies, but each step can override via on_fail.
"""
import logging
import time
import enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ErrorCategory(enum.Enum):
    ADB_TIMEOUT = "adb_timeout"
    ADB_COMMAND_FAIL = "adb_command_fail"
    TEMPLATE_NOT_FOUND = "template_not_found"
    TEMPLATE_MISMATCH = "template_mismatch"
    OCR_FAIL = "ocr_fail"
    SCREEN_CAPTURE_FAIL = "screen_capture_fail"
    NETWORK_ERROR = "network_error"
    CONFIG_ERROR = "config_error"
    FILE_ERROR = "file_error"
    UNKNOWN = "unknown"


class ErrorPolicy(enum.Enum):
    RETRY = "retry"
    BACKOFF = "backoff"
    SKIP = "skip"
    FAIL = "fail"
    ABORT = "abort"


DEFAULT_POLICY_MAP = {
    ErrorCategory.ADB_TIMEOUT: ErrorPolicy.RETRY,
    ErrorCategory.ADB_COMMAND_FAIL: ErrorPolicy.FAIL,
    ErrorCategory.TEMPLATE_NOT_FOUND: ErrorPolicy.SKIP,
    ErrorCategory.TEMPLATE_MISMATCH: ErrorPolicy.SKIP,
    ErrorCategory.OCR_FAIL: ErrorPolicy.RETRY,
    ErrorCategory.SCREEN_CAPTURE_FAIL: ErrorPolicy.RETRY,
    ErrorCategory.NETWORK_ERROR: ErrorPolicy.BACKOFF,
    ErrorCategory.CONFIG_ERROR: ErrorPolicy.FAIL,
    ErrorCategory.FILE_ERROR: ErrorPolicy.SKIP,
    ErrorCategory.UNKNOWN: ErrorPolicy.FAIL,
}


class ErrorPolicyConfig:
    """Configuration for error policies loaded from config.json -> execution.policy."""

    def __init__(self, config_dict: Optional[dict] = None):
        cfg = config_dict or {}
        self.default_policy = ErrorPolicy(cfg.get("default_policy", "fail"))
        self.max_retries: int = cfg.get("max_retries", 3)
        self.retry_delay: float = cfg.get("retry_delay", 0.5)
        self.backoff_base: float = cfg.get("backoff_base", 1.0)
        self.backoff_max: float = cfg.get("backoff_max", 10.0)
        self.category_overrides: dict = {}
        for key, val in cfg.get("category_overrides", {}).items():
            try:
                cat = ErrorCategory(key)
                pol = ErrorPolicy(val)
                self.category_overrides[cat] = pol
            except (ValueError, KeyError):
                logger.warning("Invalid policy override: %s -> %s", key, val)

    def get_policy(self, category: ErrorCategory, step_override: Optional[str] = None) -> ErrorPolicy:
        if step_override:
            try:
                return ErrorPolicy(step_override)
            except ValueError:
                pass
        if category in self.category_overrides:
            return self.category_overrides[category]
        if category in DEFAULT_POLICY_MAP:
            return DEFAULT_POLICY_MAP[category]
        return self.default_policy

    def to_dict(self) -> dict:
        overrides = {}
        for cat, pol in self.category_overrides.items():
            overrides[cat.value] = pol.value
        return {
            "default_policy": self.default_policy.value,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "backoff_base": self.backoff_base,
            "backoff_max": self.backoff_max,
            "category_overrides": overrides,
        }


def classify_error(exc: Exception, step_type: str = "") -> ErrorCategory:
    """Classify an exception into an ErrorCategory."""
    exc_name = type(exc).__name__.lower()
    exc_msg = str(exc).lower()

    if "timeout" in exc_name or "timeout" in exc_msg:
        return ErrorCategory.ADB_TIMEOUT
    if "adberror" in exc_name or "adb" in exc_msg:
        return ErrorCategory.ADB_COMMAND_FAIL
    if "template" in exc_msg and ("not found" in exc_msg or "load" in exc_msg or "miss" in exc_msg):
        return ErrorCategory.TEMPLATE_NOT_FOUND
    if "template" in exc_msg:
        return ErrorCategory.TEMPLATE_MISMATCH
    if "ocr" in exc_msg or "easyocr" in exc_msg:
        return ErrorCategory.OCR_FAIL
    if "screen" in exc_msg or "capture" in exc_msg or "frame" in exc_msg:
        return ErrorCategory.SCREEN_CAPTURE_FAIL
    if "connection" in exc_msg or "socket" in exc_msg or "network" in exc_msg:
        return ErrorCategory.NETWORK_ERROR
    if "config" in exc_msg or "json" in exc_msg:
        return ErrorCategory.CONFIG_ERROR
    if "file" in exc_msg or "io" in exc_name or "os" in exc_name:
        return ErrorCategory.FILE_ERROR
    return ErrorCategory.UNKNOWN


def classify_step_failure(step_type: str, error_msg: str = "") -> ErrorCategory:
    """Classify a step failure by step type and error message."""
    msg = error_msg.lower()
    if step_type in ("tap", "long_press", "swipe", "tap_point", "keyevent"):
        if "timeout" in msg:
            return ErrorCategory.ADB_TIMEOUT
        return ErrorCategory.ADB_COMMAND_FAIL
    if step_type == "check_image":
        if "template" in msg and ("not found" in msg or "load" in msg):
            return ErrorCategory.TEMPLATE_NOT_FOUND
        return ErrorCategory.TEMPLATE_MISMATCH
    if step_type == "ocr_region":
        return ErrorCategory.OCR_FAIL
    if step_type == "screenshot":
        return ErrorCategory.SCREEN_CAPTURE_FAIL
    if step_type in ("pull_file", "delete_file"):
        return ErrorCategory.FILE_ERROR
    if step_type in ("wifi", "force_stop", "launch", "adb_command"):
        return ErrorCategory.ADB_COMMAND_FAIL
    return ErrorCategory.UNKNOWN


class ErrorPolicyExecutor:
    """Executes a step with the appropriate error policy applied."""

    def __init__(self, config: ErrorPolicyConfig, stop_check: Optional[Callable[[], bool]] = None):
        self._config = config
        self._stop_check = stop_check or (lambda: False)

    def execute_with_policy(
        self,
        step: dict,
        step_fn: Callable[[dict], bool],
        error_handler: Optional[Callable[[ErrorCategory, int, float], None]] = None,
    ) -> bool:
        """Execute a step function with error policy applied.

        Returns True if the step succeeded (or was skipped), False if it should fail the workflow.
        """
        step_type = step.get("type", "unknown")
        step_on_fail = step.get("on_fail", None)

        attempt = 0
        delay = self._config.retry_delay

        while True:
            if self._stop_check():
                return False

            try:
                result = step_fn(step)
                if result:
                    return True
                # Step returned False (non-exception failure)
                category = classify_step_failure(step_type)
            except Exception as e:
                category = classify_error(e, step_type)
                logger.error("Step execution error [%s]: %s (category: %s)", step_type, e, category.value)

            policy = self._config.get_policy(category, step_on_fail)

            if error_handler:
                error_handler(category, attempt, delay)

            if policy in (ErrorPolicy.FAIL, ErrorPolicy.ABORT):
                logger.error("Error policy %s for step %s, category %s", policy.value, step_type, category.value)
                return False

            if policy == ErrorPolicy.SKIP:
                logger.warning("Skipping failed step %s (category: %s)", step_type, category.value)
                return True  # treat as success to continue workflow

            if policy == ErrorPolicy.ABORT:
                logger.error("Aborting execution due to step %s failure", step_type)
                return False

            # RETRY or BACKOFF
            attempt += 1
            if attempt > self._config.max_retries:
                logger.error("Max retries (%d) exceeded for step %s", self._config.max_retries, step_type)
                return False

            if policy == ErrorPolicy.BACKOFF:
                delay = min(delay * self._config.backoff_base, self._config.backoff_max)
                logger.info("Backing off %.1fs before retry %d/%d for %s", delay, attempt, self._config.max_retries, step_type)
            else:
                logger.info("Retrying %d/%d for %s (delay %.1fs)", attempt, self._config.max_retries, step_type, delay)

            time.sleep(delay)
