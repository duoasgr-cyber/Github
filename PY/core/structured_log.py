"""Structured logging with export capability.

Adds structured context fields (workflow, step_index, device, task_id)
and JSON/CSV log export support.
"""
import logging
import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional


class StructuredFormatter(logging.Formatter):
    """Formatter that adds structured fields to log records."""

    def format(self, record):
        # Add default structured fields if not present
        if not hasattr(record, 'workflow'):
            record.workflow = ''
        if not hasattr(record, 'step_index'):
            record.step_index = -1
        if not hasattr(record, 'device'):
            record.device = ''
        if not hasattr(record, 'task_id'):
            record.task_id = ''

        return super().format(record)


class LogCollector:
    """Collects log entries with structured fields for export."""

    def __init__(self, max_entries: int = 5000):
        self._entries: List[Dict[str, Any]] = []
        self._max_entries = max_entries

    def add_entry(self, record: logging.LogRecord):
        """Add a log record to the collection."""
        entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "workflow": getattr(record, 'workflow', ''),
            "step_index": getattr(record, 'step_index', -1),
            "device": getattr(record, 'device', ''),
            "task_id": getattr(record, 'task_id', ''),
        }
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def get_entries(self, level: Optional[str] = None,
                    workflow: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get filtered log entries."""
        entries = self._entries
        if level:
            entries = [e for e in entries if e["level"] == level]
        if workflow:
            entries = [e for e in entries if e["workflow"] == workflow]
        return entries

    def export_json(self, file_path: str) -> bool:
        """Export all collected entries to JSON Lines format."""
        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                for entry in self._entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def export_csv(self, file_path: str) -> bool:
        """Export all collected entries to CSV format."""
        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            if not self._entries:
                return True
            fields = ["timestamp", "level", "logger", "message",
                       "workflow", "step_index", "device", "task_id"]
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self._entries)
            return True
        except Exception:
            return False

    def clear(self):
        self._entries.clear()

    @property
    def count(self) -> int:
        return len(self._entries)


# Global log collector instance
_log_collector = LogCollector()


def get_log_collector() -> LogCollector:
    return _log_collector


class CollectingLogHandler(logging.Handler):
    """Log handler that sends records to the LogCollector."""

    def emit(self, record):
        try:
            _log_collector.add_entry(record)
        except Exception:
            self.handleError(record)
