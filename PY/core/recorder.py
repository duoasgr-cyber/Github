"""Shadow recorder for capturing user interactions as workflow steps.

Records ADB events (tap, swipe, keyevent) from the connected device and
generates a draft workflow that can be applied to the workflow editor.
"""
import logging
import time
import threading
from typing import Optional, List, Dict, Callable
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class RecorderEvent:
    """Represents a single recorded interaction event."""

    def __init__(self, event_type: str, timestamp: float, data: dict):
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data

    def to_step(self) -> dict:
        """Convert this event to a workflow step dict."""
        step = {"type": self.event_type, "comment": f"Recorded at {self.timestamp:.1f}"}
        step.update(self.data)
        return step

    def __repr__(self):
        return f"RecorderEvent({self.event_type}, {self.data})"


class Recorder(QObject):
    """Records user interactions from ADB and generates workflow step drafts.

    Signals:
        event_recorded: Emitted when a new event is captured
        recording_started: Emitted when recording begins
        recording_stopped: Emitted when recording ends
    """

    event_recorded = pyqtSignal(dict)
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()

    def __init__(self, adb_core=None, screen_capture=None, parent=None):
        super().__init__(parent)
        self._adb_core = adb_core
        self._screen_capture = screen_capture
        self._events: List[RecorderEvent] = []
        self._recording = False
        self._lock = threading.Lock()
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_flag = False

    def start_recording(self) -> bool:
        """Start recording interactions."""
        if self._recording:
            logger.warning("Already recording")
            return False

        with self._lock:
            self._events.clear()
            self._recording = True
            self._stop_flag = False

        self.recording_started.emit()
        logger.info("Recording started")

        # Start polling for getevent output in background
        self._poll_thread = threading.Thread(target=self._poll_getevent, daemon=True)
        self._poll_thread.start()
        return True

    def stop_recording(self) -> List[dict]:
        """Stop recording and return the captured steps as a list of dicts."""
        if not self._recording:
            return []

        self._stop_flag = True
        self._recording = False

        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)

        with self._lock:
            steps = [evt.to_step() for evt in self._events]

        self.recording_stopped.emit()
        logger.info("Recording stopped: %d events captured", len(steps))
        return steps

    def is_recording(self) -> bool:
        return self._recording

    def get_events(self) -> List[dict]:
        with self._lock:
            return [evt.to_step() for evt in self._events]

    def clear(self):
        with self._lock:
            self._events.clear()

    def add_manual_event(self, event_type: str, data: dict):
        """Manually add an event (e.g., from UI interactions)."""
        evt = RecorderEvent(event_type, time.time(), data)
        with self._lock:
            self._events.append(evt)
        self.event_recorded.emit(evt.to_step())

    def generate_workflow(self, name: str = "recorded", device_resolution: dict = None) -> dict:
        """Generate a workflow dict from recorded events."""
        with self._lock:
            steps = [evt.to_step() for evt in self._events]

        workflow = {
            "description": f"Recorded workflow with {len(steps)} steps",
            "device_resolution": device_resolution or {"width": 2400, "height": 1080},
            "steps": steps,
        }
        return workflow

    def _poll_getevent(self):
        """Poll getevent for touch/input events on the device."""
        if self._adb_core is None:
            logger.debug("No ADB core provided, skipping getevent polling")
            return

        device = self._adb_core.get_device()
        if not device:
            logger.debug("No device connected, skipping getevent polling")
            return

        try:
            import subprocess
            cmd = f"adb -s {device} shell getevent -lt"
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )

            touch_data = {}
            last_event_time = 0

            for line in iter(proc.stdout.readline, b""):
                if self._stop_flag:
                    proc.terminate()
                    break

                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                # Parse getevent -lt output
                # Format: [timestamp] /dev/input/eventX: type code value
                event = self._parse_getevent_line(decoded, touch_data)
                if event:
                    now = time.time()
                    # Debounce: don't record events too rapidly
                    if now - last_event_time > 0.3:
                        self.add_manual_event(event["type"], event["data"])
                    last_event_time = now

        except Exception as e:
            logger.debug("getevent polling ended: %s", e)

    def _parse_getevent_line(self, line: str, touch_data: dict) -> Optional[dict]:
        """Parse a single getevent line and return an event dict if complete."""
        # Simplified parser for common touch events
        try:
            # Extract the event part after the device path
            parts = line.split(":")
            if len(parts) < 2:
                return None

            event_part = parts[-1].strip()
            tokens = event_part.split()
            if len(tokens) < 3:
                return None

            event_type_str = tokens[0]  # e.g., 0003 (EV_ABS)
            event_code = tokens[1]      # e.g., 0035 (ABS_MT_POSITION_X)
            event_value = tokens[2]     # e.g., 00000abc

            try:
                code = int(event_code, 16)
                value = int(event_value, 16)
            except ValueError:
                return None

            # ABS_MT_POSITION_X = 0x35, ABS_MT_POSITION_Y = 0x36
            # SYN_REPORT = 0x00
            if code == 0x35:
                touch_data["x"] = value
            elif code == 0x36:
                touch_data["y"] = value
            elif code == 0x39:
                touch_data["tracking_id"] = value
                if value == 0xffffffff:
                    # Finger up
                    if "x" in touch_data and "y" in touch_data:
                        event = {
                            "type": "tap",
                            "data": {"x": touch_data["x"], "y": touch_data["y"], "wait_after": 1}
                        }
                        touch_data.clear()
                        return event
            elif code == 0x3a:
                touch_data["pressure"] = value

        except Exception:
            pass

        return None

    def export_steps_text(self) -> str:
        """Export recorded steps as human-readable text."""
        with self._lock:
            lines = []
            for i, evt in enumerate(self._events):
                step = evt.to_step()
                step_type = step.get("type", "unknown")
                comment = step.get("comment", "")
                line = f"{i + 1}. [{step_type}]"
                if step_type == "tap":
                    line += f" ({step.get('x', 0)}, {step.get('y', 0)})"
                elif step_type == "swipe":
                    line += f" ({step.get('x1', 0)},{step.get('y1', 0)}) -> ({step.get('x2', 0)},{step.get('y2', 0)})"
                elif step_type == "keyevent":
                    line += f" key={step.get('key', '')}"
                if comment:
                    line += f" -- {comment}"
                lines.append(line)
            return "\n".join(lines)
