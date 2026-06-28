import logging

logger = logging.getLogger(__name__)


class Telemetry:
    """Telemetry reporting (stub)."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        pass

    def record_crash(self, exc_type: str, exc_value: str, traceback_text: str):
        logger.debug("Telemetry: crash recorded - %s: %s", exc_type, exc_value)

    def record_event(self, event_name: str, data: dict = None):
        logger.debug("Telemetry: event recorded - %s", event_name)
