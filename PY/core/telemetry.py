"""Telemetry and crash reporting system.

Collects runtime metrics locally with optional anonymous reporting.
Default: telemetry is DISABLED (opt-in via config.json -> telemetry.enabled).
"""
import json
import os
import logging
import time
import threading
import traceback
from datetime import datetime, timezone
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class TelemetryEvent:
    """A single telemetry event."""

    def __init__(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = time.time()
        self.utc_time = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "type": self.event_type,
            "timestamp": self.timestamp,
            "utc_time": self.utc_time,
            "data": self.data,
        }


class Telemetry:
    """Local telemetry collector with optional anonymous reporting.

    Tracks:
        - Workflow executions (start, complete, fail)
        - Step failures (by type and category)
        - Error recovery actions
        - Crash reports
        - Session duration and step counts
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, config_manager=None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._config_manager = config_manager
        self._events: List[TelemetryEvent] = []
        self._lock = threading.Lock()
        self._session_start = time.time()
        self._step_counts = defaultdict(int)
        self._failure_counts = defaultdict(int)
        self._recovery_counts = defaultdict(int)
        self._workflow_runs = 0
        self._workflow_completions = 0
        self._workflow_failures = 0
        self._crash_reports: List[dict] = []
        self._max_events = 1000

    @property
    def enabled(self) -> bool:
        if self._config_manager:
            return self._config_manager.get_config("telemetry.enabled", False)
        return False

    def record_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Record a telemetry event."""
        event = TelemetryEvent(event_type, data)
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

        if self.enabled:
            logger.debug("Telemetry event: %s", event_type)

    def record_workflow_start(self, workflow_name: str):
        self._workflow_runs += 1
        self.record_event("workflow_start", {"workflow": workflow_name})

    def record_workflow_complete(self, workflow_name: str, duration: float):
        self._workflow_completions += 1
        self.record_event("workflow_complete", {
            "workflow": workflow_name,
            "duration": duration,
        })

    def record_workflow_fail(self, workflow_name: str, error: str):
        self._workflow_failures += 1
        self.record_event("workflow_fail", {
            "workflow": workflow_name,
            "error": error,
        })

    def record_step_execution(self, step_type: str, success: bool, duration: float = 0):
        self._step_counts[step_type] += 1
        if not success:
            self._failure_counts[step_type] += 1
        self.record_event("step_execution", {
            "step_type": step_type,
            "success": success,
            "duration": duration,
        })

    def record_error_recovery(self, error_category: str, policy: str, success: bool):
        self._recovery_counts[error_category] += 1
        self.record_event("error_recovery", {
            "category": error_category,
            "policy": policy,
            "success": success,
        })

    def record_crash(self, exc_type: str, exc_value: str, tb_text: str):
        """Record a crash report."""
        report = {
            "exception_type": exc_type,
            "exception_value": exc_value,
            "traceback": tb_text[:2000],  # truncate
            "timestamp": time.time(),
        }
        with self._lock:
            self._crash_reports.append(report)
            if len(self._crash_reports) > 50:
                self._crash_reports = self._crash_reports[-50:]

        self.record_event("crash", {
            "exception_type": exc_type,
            "message": exc_value[:500],
        })
        logger.error("Crash recorded: %s: %s", exc_type, exc_value)

    def get_session_stats(self) -> dict:
        """Get current session statistics."""
        duration = time.time() - self._session_start
        return {
            "session_duration": duration,
            "workflow_runs": self._workflow_runs,
            "workflow_completions": self._workflow_completions,
            "workflow_failures": self._workflow_failures,
            "step_counts": dict(self._step_counts),
            "failure_counts": dict(self._failure_counts),
            "recovery_counts": dict(self._recovery_counts),
            "total_events": len(self._events),
            "crash_count": len(self._crash_reports),
        }

    def export_events(self, file_path: str) -> bool:
        """Export all events to a JSON file."""
        try:
            with self._lock:
                data = {
                    "session_stats": self.get_session_stats(),
                    "events": [e.to_dict() for e in self._events],
                    "crash_reports": self._crash_reports,
                }
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Telemetry exported to %s", file_path)
            return True
        except Exception as e:
            logger.error("Failed to export telemetry: %s", e)
            return False


    def report_to_server(self) -> bool:
        """Send telemetry payload to the configured endpoint.

        The endpoint URL is read from config key ``telemetry.endpoint``.
        Data is POSTed as JSON.  Returns True on success, False on any
        error (network, config, etc.).  Never raises.
        """
        if not self.enabled:
            return False

        endpoint = ""
        if self._config_manager:
            endpoint = self._config_manager.get_config("telemetry.endpoint", "")
        if not endpoint:
            logger.debug("No telemetry endpoint configured, skipping report")
            return False

        with self._lock:
            payload = {
                "session_stats": self.get_session_stats(),
                "events": [e.to_dict() for e in self._events[-200:]],
                "crash_reports": self._crash_reports[-10:],
            }

        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                logger.info("Telemetry reported to %s (HTTP %d)", endpoint, status)
                return 200 <= status < 300
        except urllib.error.URLError as e:
            logger.warning("Telemetry report failed: %s", e)
            return False
        except Exception as e:
            logger.warning("Telemetry report error: %s", e)
            return False

    def schedule_periodic_report(self, interval_seconds: int = 300):
        """Start a background thread that calls report_to_server periodically.

        Args:
            interval_seconds: Seconds between reports (default 300 = 5 min).
        """
        def _periodic():
            while True:
                time.sleep(interval_seconds)
                try:
                    self.report_to_server()
                except Exception as e:
                    logger.debug("定期遥测报告失败: %s", e)
        t = threading.Thread(target=_periodic, daemon=True, name="telemetry-report")
        t.start()
        logger.info("Telemetry periodic reporter started (every %ds)", interval_seconds)

    def clear(self):
        with self._lock:
            self._events.clear()
            self._crash_reports.clear()
            self._step_counts.clear()
            self._failure_counts.clear()
            self._recovery_counts.clear()
            self._workflow_runs = 0
            self._workflow_completions = 0
            self._workflow_failures = 0
            self._session_start = time.time()
