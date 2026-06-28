"""Step 分发表与策略执行 Mixin。"""
import logging


class DispatchMixin:
    """按 step.type 把请求路由到对应 _step_* 方法。"""

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
            logging.getLogger(__name__).error("Unknown step type: %s", step_type)
            return False

        try:
            return handler(step)
        except Exception as e:
            logging.getLogger(__name__).error("Step execution exception: %s - %s", step_type, e)
            return False
