import logging
import os
import time
import threading
import re
import cv2
import numpy as np
from typing import Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, QThread

from core.error_policy import (
    ErrorPolicyConfig, ErrorPolicyExecutor, ErrorCategory,
    classify_error, classify_step_failure, ErrorPolicy
)
from core.expression_eval import step_expression

logger = logging.getLogger(__name__)


class StepExecutor(QObject):
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
        extra = {
            "workflow": self._current_workflow or "",
            "step_index": self._current_step_index,
            "device": self._device_manager.get_current_device() or "",
        }
        device_str = extra["device"]
        wf_str = extra["workflow"]
        idx_str = str(extra["step_index"]) if extra["step_index"] >= 0 else "-"
        prefix = f"[wf={wf_str} step={idx_str} dev={device_str}] "
        logger.log(level, prefix + msg, *args)

    def execute_workflow(self, workflow_name: str, start_step: int = 0) -> bool:
        if self._running and self._workflow_depth == 0:
            logger.warning("Workflow already running, ignoring new request")
            return False

        # Reload error policy each run
        self._load_error_policy()

        workflow = self._config_manager.get_workflow(workflow_name)
        if not workflow:
            error_msg = f"Workflow does not exist: {workflow_name}"
            logger.error(error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            return False

        self._workflow_depth += 1
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

        if not steps:
            self._structured_log(logging.WARNING, "Workflow is empty: %s", workflow_name)
            self._restore_context(saved_workflow, saved_step_index, saved_scale_x, saved_scale_y)
            self._workflow_depth -= 1
            if self._workflow_depth == 0:
                self._running = False
            self.workflow_completed.emit(workflow_name)
            return True

        self.workflow_started.emit(workflow_name)
        self._structured_log(logging.INFO, "Starting workflow: %s (%d steps, from step %d)",
                             workflow_name, total_steps, start_step)

        result = self._run_steps(steps, workflow_name, start_step, total_steps)

        self._restore_context(saved_workflow, saved_step_index, saved_scale_x, saved_scale_y)
        self._workflow_depth -= 1

        if self._workflow_depth == 0:
            self._running = False

        return result

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

    def _check_resolution_mismatch(self, workflow: dict):
        """Check if workflow device_resolution matches actual device resolution."""
        coord_cfg = self._config_manager.get_config("coordinate", {})
        warn_on_mismatch = coord_cfg.get("warn_on_mismatch", True)
        auto_scale = coord_cfg.get("auto_scale", False)

        if not warn_on_mismatch and auto_scale:
            return

        wf_res = workflow.get("device_resolution")
        if not wf_res:
            return

        actual = self._device_manager.get_device_resolution()
        if not actual:
            return

        dev_w, dev_h = actual
        wf_w, wf_h = wf_res.get("width", 0), wf_res.get("height", 0)

        if wf_w <= 0 or wf_h <= 0:
            return

        if dev_w != wf_w or dev_h != wf_h:
            msg = (f"Resolution mismatch: workflow expects {wf_w}x{wf_h}, "
                   f"device is {dev_w}x{dev_h}. "
                   f"{'Auto-scaling enabled.' if auto_scale else 'Coordinates will NOT be scaled!'}")
            logger.warning(msg)
            self.resolution_mismatch.emit(msg)

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

    def _handle_on_fail_retry(self, step: dict, step_index: int, step_type: str) -> bool:
        self._structured_log(logging.INFO, "Step %d (%s) retrying after failure", step_index + 1, step_type)
        while not self._stop_requested:
            time.sleep(0.5)
            if self._stop_requested:
                break
            success = self._execute_single_step(step)
            if success:
                return True
        self.step_failed.emit(step_index, step_type, "Retry interrupted by stop")
        self.workflow_stopped.emit()
        return False

    def _handle_on_fail_recover(self, step: dict, step_index: int,
                                step_type: str, workflow_name: str) -> bool:
        recover_workflow = step.get("recover_workflow", "")
        if not recover_workflow:
            error_msg = f"Step {step_index + 1} ({step_type}) failed, no recover_workflow specified"
            self.step_failed.emit(step_index, step_type, error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            self._structured_log(logging.ERROR, error_msg)
            return False

        self._structured_log(logging.INFO, "Executing recovery workflow: %s", recover_workflow)
        self.execute_workflow(recover_workflow)

        if self._stop_requested:
            self.workflow_stopped.emit()
            return False

        success = self._execute_single_step(step)
        if not success:
            error_msg = f"Step {step_index + 1} ({step_type}) still failed after recovery"
            self.step_failed.emit(step_index, step_type, error_msg)
            self.workflow_failed.emit(workflow_name, error_msg)
            self._structured_log(logging.ERROR, error_msg)
            return False

        return True

    def _calculate_scaling(self, workflow: dict) -> None:
        device_resolution = workflow.get("device_resolution", None)
        if not device_resolution:
            self._scale_x = 1.0
            self._scale_y = 1.0
            return

        base_width = device_resolution.get("width", 0)
        base_height = device_resolution.get("height", 0)

        if base_width <= 0 or base_height <= 0:
            self._scale_x = 1.0
            self._scale_y = 1.0
            return

        current_resolution = self._device_manager.get_device_resolution()
        if not current_resolution:
            self._scale_x = 1.0
            self._scale_y = 1.0
            return

        device_width, device_height = current_resolution
        coord_cfg = self._config_manager.get_config("coordinate", {})
        auto_scale = coord_cfg.get("auto_scale", False)

        if device_width == base_width and device_height == base_height:
            self._scale_x = 1.0
            self._scale_y = 1.0
            return

        if auto_scale:
            self._scale_x = device_width / base_width
            self._scale_y = device_height / base_height
            self._structured_log(logging.INFO,
                                 "Coordinate scaling: %.4f x %.4f (base: %dx%d, device: %dx%d)",
                                 self._scale_x, self._scale_y,
                                 base_width, base_height, device_width, device_height)
        else:
            self._scale_x = 1.0
            self._scale_y = 1.0

    def _scale_coord(self, x: int, y: int) -> Tuple[int, int]:
        return int(round(x * self._scale_x)), int(round(y * self._scale_y))

    def _execute_with_policy(self, step: dict) -> bool:
        """Execute a step with error policy applied."""
        if self._error_executor:
            def _step_fn(s):
                return self._execute_single_step(s)
            return self._error_executor.execute_with_policy(step, _step_fn)
        else:
            return self._execute_single_step(step)

    def _execute_single_step(self, step: dict) -> bool:
        step_type = step.get("type", "")

        handler = {
            "tap": self._step_tap,
            "long_press": self._step_long_press,
            "swipe": self._step_swipe,
            "keyevent": self._step_keyevent,
            "wait": self._step_wait,
            "wifi": self._step_wifi,
            "force_stop": self._step_force_stop,
            "launch": self._step_launch,
            "screenshot": self._step_screenshot,
            "pull_file": self._step_pull_file,
            "delete_file": self._step_delete_file,
            "check_image": self._step_check_image,
            "ocr_region": self._step_ocr_region,
            "tap_point": self._step_tap_point,
            "call_workflow": self._step_call_workflow,
            "condition": self._step_condition,
            "loop": self._step_loop,
            "input_text": self._step_input_text,
            "variable": self._step_variable,
            "adb_command": self._step_adb_command,
            "expression": self._step_expression,
        }.get(step_type)

        if handler is None:
            logger.error("Unknown step type: %s", step_type)
            return False

        try:
            return handler(step)
        except Exception as e:
            logger.error("Step execution exception: %s - %s", step_type, e)
            return False

    def _step_tap(self, step: dict) -> bool:
        x, y = self._scale_coord(step["x"], step["y"])
        result = self._adb_core.tap(x, y)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_long_press(self, step: dict) -> bool:
        x, y = self._scale_coord(step["x"], step["y"])
        duration = step.get("duration", 1000)
        result = self._adb_core.long_press(x, y, duration)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_swipe(self, step: dict) -> bool:
        x1, y1 = self._scale_coord(step["x1"], step["y1"])
        x2, y2 = self._scale_coord(step["x2"], step["y2"])
        duration = step.get("duration", 300)
        return self._adb_core.swipe(x1, y1, x2, y2, duration)

    def _step_keyevent(self, step: dict) -> bool:
        key = step["key"]
        return self._adb_core.keyevent(key)

    def _step_wait(self, step: dict) -> bool:
        seconds = step.get("seconds", 0)
        self._interruptible_sleep(seconds)
        return not self._stop_requested

    def _step_wifi(self, step: dict) -> bool:
        action = step.get("action", "enable")
        if action == "enable":
            result = self._adb_core.wifi_enable()
        else:
            result = self._adb_core.wifi_disable()
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_force_stop(self, step: dict) -> bool:
        package = step["package"]
        result = self._adb_core.force_stop(package)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_launch(self, step: dict) -> bool:
        package = step["package"]
        result = self._adb_core.launch(package)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_screenshot(self, step: dict) -> bool:
        save_path = step.get("save_path", "")
        if not save_path:
            logger.error("screenshot step missing save_path")
            return False
        frame = self._screen_capture.get_current_frame()
        if frame is None:
            logger.error("Failed to get current frame")
            return False
        return cv2.imwrite(save_path, frame)

    def _step_pull_file(self, step: dict) -> bool:
        remote = step["remote"]
        local = step["local"]
        return self._adb_core.pull_file(remote, local)

    def _step_delete_file(self, step: dict) -> bool:
        path = step["path"]
        return self._adb_core.delete_file(path)

    def _step_check_image(self, step: dict) -> bool:
        template_path = step.get("template", "")
        threshold = step.get("threshold", 0.85)

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            logger.error("Failed to get current frame")
            self._last_check_result = False
            self.check_image_result.emit(False)
            return False

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            logger.error("Failed to load template: %s", template_path)
            self._last_check_result = False
            self.check_image_result.emit(False)
            return False

        if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
            logger.error("Template larger than frame: template %s, frame %s",
                         template.shape[:2], frame.shape[:2])
            self._last_check_result = False
            self.check_image_result.emit(False)
            return False

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        found = max_val >= threshold
        self._last_check_result = found
        self.check_image_result.emit(found)
        logger.info("Image match result: %.4f >= %.4f = %s", max_val, threshold, found)

        assign_var = step.get("assign_variable", "")
        if assign_var:
            self._variables[assign_var] = found
        return True

    def _step_ocr_region(self, step: dict) -> bool:
        region = step.get("region", None)

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            logger.error("Failed to get current frame")
            self._last_ocr_result = ""
            self.ocr_result.emit("")
            return False

        text = self._ocr_engine.recognize(frame, region)
        self._last_ocr_result = text
        self.ocr_result.emit(text)
        logger.info("OCR result: %s", text)

        assign_var = step.get("assign_variable", "")
        if assign_var:
            self._variables[assign_var] = text
        return True

    def _step_tap_point(self, step: dict) -> bool:
        x = step["x"]
        y = step["y"]
        result = self._adb_core.tap(x, y)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_call_workflow(self, step: dict) -> bool:
        workflow_name = step.get("workflow", "")
        if not workflow_name:
            logger.error("call_workflow step missing workflow name")
            return False
        logger.info("Calling sub-workflow: %s", workflow_name)
        return self.execute_workflow(workflow_name)

    def _step_condition(self, step: dict) -> bool:
        check = step.get("check", {})
        condition_result = self._evaluate_condition(check)
        logger.info("Condition result: %s", condition_result)

        branch = "then" if condition_result else "else"
        mode = step.get("{}_mode".format(branch), "embedded")

        if mode == "workflow":
            wf_name = step.get("{}_workflow".format(branch), "")
            if not wf_name:
                logger.warning("Condition %s_workflow is empty, skipping", branch)
                return True
            logger.info("Condition %s: calling workflow %s", branch, wf_name)
            return self.execute_workflow(wf_name)

        steps = step.get("{}_steps".format(branch), [])
        for sub_step in steps:
            if self._stop_requested:
                return False
            success = self._execute_single_step(sub_step)
            if not success:
                return False

        return True

    def _step_loop(self, step: dict) -> bool:
        max_count = step.get("max_count", 0)
        condition = step.get("condition", None)
        steps = step.get("steps", [])
        iteration = 0

        while True:
            if self._stop_requested:
                return False

            if max_count and max_count > 0 and iteration >= max_count:
                logger.info("Loop reached max count: %d", max_count)
                break

            if condition is not None:
                if not self._evaluate_condition(condition):
                    logger.info("Loop condition not met, exiting (iteration %d)", iteration)
                    break

            for sub_step in steps:
                if self._stop_requested:
                    return False
                success = self._execute_single_step(sub_step)
                if not success:
                    return False

            iteration += 1

        logger.info("Loop completed: %d iterations", iteration)
        return True

    def _step_input_text(self, step: dict) -> bool:
        text = step.get("text", "")
        return self._adb_core.input_text(text)

    def _step_variable(self, step: dict) -> bool:
        var_name = step.get("var_name", "")
        var_type = step.get("var_type", "string")
        var_value = step.get("var_value", "")
        if not var_name:
            logger.error("variable step missing var_name")
            return False
        try:
            if var_type == "bool":
                self._variables[var_name] = str(var_value).lower() in ("true", "1", "yes")
            elif var_type == "int":
                self._variables[var_name] = int(var_value)
            else:
                self._variables[var_name] = str(var_value)
            logger.info("Variable set: %s = %s (%s)", var_name, self._variables[var_name], var_type)
            return True
        except (ValueError, TypeError) as e:
            logger.error("Variable assignment failed: %s", e)
            return False

    def _step_adb_command(self, step: dict) -> bool:
        cmd = step.get("adb_cmd", "")
        if not cmd:
            logger.error("adb_command step missing adb_cmd")
            return False
        try:
            result = self._adb_core.shell(cmd)
            assign_var = step.get("assign_variable", "")
            if assign_var:
                self._variables[assign_var] = str(result) if result else ""
                logger.info("ADB result stored: %s = %s", assign_var, self._variables[assign_var])
            logger.info("ADB command: %s -> %s", cmd, result)
            return True
        except Exception as e:
            logger.error("ADB command failed: %s", e)
            return False

    def _step_expression(self, step: dict) -> bool:
        """Execute an expression step using the safe evaluator."""
        return step_expression(step, self._variables)

    def _evaluate_condition(self, check: dict) -> bool:
        check_type = check.get("type", "")

        if check_type == "image_found":
            return self._check_image_found(check)
        elif check_type == "image_not_found":
            return not self._check_image_found(check)
        elif check_type == "ocr_contains":
            return self._check_ocr_contains(check)
        elif check_type == "ocr_not_contains":
            return not self._check_ocr_contains(check)
        elif check_type == "ocr_less_than":
            return self._check_ocr_less_than(check)
        elif check_type == "ocr_greater_than":
            return self._check_ocr_greater_than(check)
        else:
            logger.error("Unknown condition type: %s", check_type)
            return False

    def _check_image_found(self, check: dict) -> bool:
        template_name = check.get("template", "")
        threshold = check.get("threshold", 0.85)

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return False

        template_dir = self._config_manager.get_config("recognition.template_dir", "tp")
        if os.path.isabs(template_name):
            template_path = template_name
        else:
            template_path = os.path.join(template_dir, template_name)

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            logger.error("Failed to load template: %s", template_path)
            return False

        if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
            logger.error("Template larger than frame")
            return False

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        found = max_val >= threshold
        self._last_check_result = found
        return found

    def _check_ocr_contains(self, check: dict) -> bool:
        region = check.get("region", None)
        text = check.get("text", "")

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return False

        ocr_text = self._ocr_engine.recognize(frame, region)
        self._last_ocr_result = ocr_text
        return text in ocr_text

    def _check_ocr_less_than(self, check: dict) -> bool:
        region = check.get("region", None)
        value = check.get("value", 0)

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return False

        ocr_text = self._ocr_engine.recognize(frame, region)
        self._last_ocr_result = ocr_text

        try:
            cleaned = re.sub(r'[^\d.]', '', ocr_text)
            if not cleaned:
                return False
            ocr_value = float(cleaned)
            return ocr_value < value
        except (ValueError, TypeError):
            logger.error("OCR result cannot convert to number: %s", ocr_text)
            return False

    def _check_ocr_greater_than(self, check: dict) -> bool:
        region = check.get("region", None)
        value = check.get("value", 0)

        frame = self._screen_capture.get_current_frame()
        if frame is None:
            return False

        ocr_text = self._ocr_engine.recognize(frame, region)
        self._last_ocr_result = ocr_text

        try:
            cleaned = re.sub(r'[^\d.]', '', ocr_text)
            if not cleaned:
                return False
            ocr_value = float(cleaned)
            return ocr_value > value
        except (ValueError, TypeError):
            logger.error("OCR result cannot convert to number: %s", ocr_text)
            return False

    def get_variable(self, name: str, default=None):
        return self._variables.get(name, default)

    def set_variable(self, name: str, value) -> None:
        self._variables[name] = value

    def clear_variables(self) -> None:
        self._variables.clear()

    def _interruptible_sleep(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_requested:
                return
            sleep_time = min(0.1, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
