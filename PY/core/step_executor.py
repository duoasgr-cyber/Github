import logging
import time
import threading
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from core.error_policy import (
    ErrorPolicyConfig, ErrorPolicyExecutor
)
from core.steps.adb_ops import AdbOpsMixin
from core.steps.vision import VisionMixin
from core.steps.flow_control import FlowControlMixin
from core.steps.vars import VarsMixin
from core.steps.scaling import ScalingMixin
from core.steps.dispatch import DispatchMixin

logger = logging.getLogger(__name__)


class StepExecutor(AdbOpsMixin, VisionMixin, FlowControlMixin,
                   VarsMixin, ScalingMixin, DispatchMixin, QObject):
    step_started = pyqtSignal(int, str)
    step_completed = pyqtSignal(int, str)
    step_failed = pyqtSignal(int, str, str)
    workflow_started = pyqtSignal(str)
    workflow_completed = pyqtSignal(str)
    workflow_failed = pyqtSignal(str, str)
    workflow_paused = pyqtSignal()
    workflow_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)
    check_image_result = pyqtSignal(bool)
    ocr_result = pyqtSignal(str)
    resolution_mismatch = pyqtSignal(str)

    def __init__(self, config_manager, adb_core, screen_capture, ocr_engine, device_manager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._adb_core = adb_core
        self._screen_capture = screen_capture
        self._ocr_engine = ocr_engine
        self._device_manager = device_manager
        self._running = False
        self._paused = False
        self._stop_requested = False
        self._current_workflow: Optional[str] = None
        self._current_step_index: int = -1
        self._last_check_result: bool = False
        self._last_ocr_result: str = ""
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._workflow_depth: int = 0
        self._workflow_call_stack: list = []
        self._variables: dict = {}
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._error_policy_config: Optional[ErrorPolicyConfig] = None
        self._error_executor: Optional[ErrorPolicyExecutor] = None
        self._load_error_policy()

    def _load_error_policy(self):
        policy_dict = self._config_manager.get_config("execution.policy", {})
        self._error_policy_config = ErrorPolicyConfig(policy_dict)
        self._error_executor = ErrorPolicyExecutor(
            self._error_policy_config,
            stop_check=lambda: self._stop_requested
        )

    def _structured_log(self, level: int, msg: str, *args):
        """Log with structured context fields."""
        device_str = self._device_manager.get_current_device() or ""
        wf_str = self._current_workflow or ""
        idx_str = str(self._current_step_index) if self._current_step_index >= 0 else "-"
        prefix = f"[wf={wf_str} step={idx_str} dev={device_str}] "
        logger.log(level, prefix + msg, *args)

    def execute_workflow(self, workflow_name: str, start_step: int = 0) -> bool:
        if self._running and self._workflow_depth == 0:
            logger.warning("Workflow already running, ignoring new request")
            return False

        self._load_error_policy()

        workflow = self._config_manager.get_workflow(workflow_name)
        if not workflow:
            error_msg = f"Workflow does not exist: {workflow_name}"
            logger.error(error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            return False

        max_depth = int(self._config_manager.get_config("execution.max_call_depth", 8))
        if self._workflow_depth >= max_depth:
            error_msg = (f"Max call depth ({max_depth}) exceeded for workflow "
                         f"'{workflow_name}' (current depth={self._workflow_depth})")
            logger.error(error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            return False
        if workflow_name in self._workflow_call_stack:
            chain = " -> ".join(self._workflow_call_stack + [workflow_name])
            error_msg = f"Workflow cycle detected: {chain}"
            logger.error(error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            return False

        self._workflow_depth += 1
        self._workflow_call_stack.append(workflow_name)
        saved_workflow = self._current_workflow
        saved_step_index = self._current_step_index
        saved_scale_x = self._scale_x
        saved_scale_y = self._scale_y

        if self._workflow_depth == 1:
            self._running = True
            self._paused = False
            self._stop_requested = False
            self._pause_event.set()

        self._current_workflow = workflow_name
        self._current_step_index = -1
        self._check_resolution_mismatch(workflow)
        self._calculate_scaling(workflow)

        steps = workflow.get("steps", [])
        total_steps = len(steps)

        try:
            if not steps:
                self._structured_log(logging.WARNING, "Workflow is empty: %s", workflow_name)
                self.workflow_completed.emit(workflow_name)
                return True

            self.workflow_started.emit(workflow_name)
            self._structured_log(logging.INFO, "Starting workflow: %s (%d steps, from step %d)",
                                 workflow_name, total_steps, start_step)

            return self._run_steps(steps, workflow_name, start_step, total_steps)
        finally:
            self._restore_context(saved_workflow, saved_step_index,
                                  saved_scale_x, saved_scale_y)
            self._workflow_depth -= 1
            self._workflow_call_stack.pop()
            if self._workflow_depth == 0:
                self._running = False

    def execute_step(self, workflow_name: str, step_index: int) -> bool:
        workflow = self._config_manager.get_workflow(workflow_name)
        if not workflow:
            logger.error("Workflow does not exist: %s", workflow_name)
            return False

        steps = workflow.get("steps", [])
        if step_index < 0 or step_index >= len(steps):
            logger.error("Step index out of bounds: %d (total %d)", step_index, len(steps))
            return False

        self._current_workflow = workflow_name
        self._current_step_index = step_index
        self._calculate_scaling(workflow)

        step = steps[step_index]
        step_type = step.get("type", "unknown")

        self.step_started.emit(step_index, step_type)
        self._structured_log(logging.INFO, "Executing single step: %d - %s", step_index, step_type)

        success = self._execute_single_step(step)

        if success:
            self.step_completed.emit(step_index, step_type)
            self._structured_log(logging.INFO, "Single step completed: %d - %s", step_index, step_type)
        else:
            self.step_failed.emit(step_index, step_type, "Step execution failed")
            self._structured_log(logging.ERROR, "Single step failed: %d - %s", step_index, step_type)

        return success

    def pause(self) -> None:
        if self._running and not self._paused:
            self._paused = True
            logger.info("Workflow pause requested")

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self._pause_event.set()
            logger.info("Workflow resume requested")

    def stop(self) -> None:
        if self._running:
            self._stop_requested = True
            if self._paused:
                self._paused = False
                self._pause_event.set()
            logger.info("Workflow stop requested")

    def is_running(self) -> bool:
        return self._running

    def is_paused(self) -> bool:
        return self._paused

    def _restore_context(self, workflow: Optional[str], step_index: int,
                         scale_x: float, scale_y: float) -> None:
        self._current_workflow = workflow
        self._current_step_index = step_index
        self._scale_x = scale_x
        self._scale_y = scale_y

    def _run_steps(self, steps: list, workflow_name: str,
                   start_step: int, total_steps: int) -> bool:
        for i in range(start_step, total_steps):
            if self._stop_requested:
                self._structured_log(logging.INFO, "Workflow stopped: %s", workflow_name)
                self.workflow_stopped.emit()
                return False

            self._current_step_index = i
            self.progress_updated.emit(i + 1, total_steps)

            step = steps[i]
            step_type = step.get("type", "unknown")
            comment = step.get("comment", "")
            enabled = step.get("enabled", True)

            if not enabled:
                self._structured_log(logging.INFO, "Skipping disabled step %d/%d: %s",
                                     i + 1, total_steps, step_type)
                self.step_started.emit(i, step_type)
                self.step_completed.emit(i, step_type)
                continue

            self.step_started.emit(i, step_type)
            self._structured_log(logging.INFO, "Executing step %d/%d: %s %s",
                                 i + 1, total_steps, step_type,
                                 f"({comment})" if comment else "")

            start_time = time.time()
            success = self._execute_with_policy(step)
            duration = time.time() - start_time

            if not success:
                on_fail = step.get("on_fail", "stop")

                if on_fail == "retry":
                    success = self._handle_on_fail_retry(step, i, step_type)
                    if not success:
                        return False
                elif on_fail == "recover":
                    success = self._handle_on_fail_recover(step, i, step_type, workflow_name)
                    if not success:
                        return False
                elif on_fail == "skip":
                    self.step_failed.emit(i, step_type, "Step failed, skipped")
                    self._structured_log(logging.WARNING, "Step %d (%s) failed, skipped", i + 1, step_type)
                    continue
                else:
                    error_msg = f"Step {i + 1} ({step_type}) failed"
                    self.step_failed.emit(i, step_type, error_msg)
                    self.workflow_failed.emit(workflow_name, error_msg)
                    self._structured_log(logging.ERROR, error_msg)
                    return False

            self.step_completed.emit(i, step_type)
            self._structured_log(logging.INFO, "Step %d completed: %s (%.2fs)", i + 1, step_type, duration)

            if self._paused:
                self._structured_log(logging.INFO, "Workflow paused: %s", workflow_name)
                self.workflow_paused.emit()
                self._pause_event.clear()
                self._pause_event.wait()
                if self._stop_requested:
                    self._structured_log(logging.INFO, "Stop requested during pause: %s", workflow_name)
                    self.workflow_stopped.emit()
                    return False
                self._paused = False
                self._structured_log(logging.INFO, "Workflow resumed: %s", workflow_name)

        self.workflow_completed.emit(workflow_name)
        self._structured_log(logging.INFO, "Workflow completed: %s", workflow_name)
        return True

    def _interruptible_sleep(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_requested:
                return
            sleep_time = min(0.1, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
