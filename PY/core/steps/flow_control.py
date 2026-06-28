"""流程控制类 step 处理器：call_workflow/condition/loop 及条件评估、失败恢复"""
import time
import logging

logger = logging.getLogger(__name__)


class FlowControlMixin:
    """流程控制与失败恢复的混入。依赖主类的 execute_workflow/_execute_single_step/_evaluate_condition/_stop_requested/_step_executor 信号等。"""

    def _step_call_workflow(self, step: dict) -> bool:
        workflow_name = step.get("workflow", "")
        if not workflow_name:
            logger.error("call_workflow step missing workflow name")
            return False
        logger.info("Calling sub-workflow: %s (depth=%d, stack=%s)",
                    workflow_name, self._workflow_depth + 1, self._workflow_call_stack)
        return self.execute_workflow(workflow_name)

    def _step_condition(self, step: dict) -> bool:
        check = step.get("check", {})
        then_steps = step.get("then_steps", [])
        else_steps = step.get("else_steps", [])

        condition_result = self._evaluate_condition(check)
        logger.info("Condition result: %s", condition_result)

        steps_to_execute = then_steps if condition_result else else_steps
        for sub_step in steps_to_execute:
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
