import logging

logger = logging.getLogger(__name__)


class Recorder:
    """Operation recorder for creating workflows from user actions."""

    def __init__(self):
        self._recording = False
        self._steps = []

    def start_recording(self):
        self._recording = True
        self._steps = []
        logger.info("Recording started")

    def stop_recording(self) -> list:
        self._recording = False
        logger.info("Recording stopped, %d steps captured", len(self._steps))
        return self._steps

    def is_recording(self) -> bool:
        return self._recording

    def record_step(self, step: dict):
        if self._recording:
            self._steps.append(step)
