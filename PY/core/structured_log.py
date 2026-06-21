import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def write_structured_log(event_type: str, data: dict = None):
    """Write a structured log entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "data": data or {},
    }
    logger.info("Structured log: %s", json.dumps(entry, ensure_ascii=False))
