import logging
import random
import re
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

_INJECTION_PATTERN = re.compile(r"[;\|`$(){}[\]]")

# 全局最大跳转次数，防止死循环
_MAX_JUMPS = 1000


class StepExecutor(AdbOpsMixin, VisionMixin, FlowControlMixin,
                   VarsMixin, ScalingMixin, DispatchMixin, QObject):
    step_started = pyqtSignal(int, str)
    step_completed = pyqtSignal(int, str)
    step_failed = pyqtSignal(int, str, str)
    step_result_updated = pyqtSignal(int, dict)  # 新增：步骤结果更新信号
    workflow_completed = pyqtSignal(str)
    workflow_failed = pyqtSignal(str, str)
    workflow_paused = pyqtSignal()
    workflow_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)

    def __init__(self, config_manager, adb_core, screen_capture, ocr_engine,
                 device_manager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._adb_core = adb_core
        self._screen_capture = screen_capture
        self._ocr_engine = ocr_engine
        self._device_manager = device_manager
        self._paused = False
        self._stopped = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始为非暂停状态
        self._lock = threading.Lock()
        self._variables: dict = {}
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

    def execute_step(self, workflow_name: str, step_index: int):
        """Execute a single step from a workflow."""
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
        try:
            self._execute_single_step(step, step_index)
            self.step_completed.emit(step_index, step_type)
        except Exception as e:
            self.step_failed.emit(step_index, step_type, str(e))

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
        # 构建跳转标签映射表
        self._jump_labels = self._build_jump_labels(steps)
        self._jump_counters: dict = {}
        self._total_jumps = 0

        i = start_step
        while i < total_steps:
            if self._stop_requested:
                self._structured_log(logging.INFO, "Workflow stopped: %s", workflow_name)
                self.workflow_stopped.emit()
                return False
            # 使用 Event 替代 busy-wait，暂停时阻塞等待恢复信号
            while self._paused:
                self._pause_event.clear()
                self._pause_event.wait()  # 阻塞直到 resume() 调用 set()
                if self._stop_requested:
                    self.workflow_stopped.emit()
                    return False
            self.progress_updated.emit(i + 1, total_steps)
            self.execute_step(workflow_name, i)

            # 跳转处理
            step = steps[i]
            jump_to = step.get("jump_to", "")
            if jump_to:
                jump_result = self._handle_jump(step, i, steps)
                if jump_result == "jumped":
                    i = self._jump_labels.get(jump_to, i + 1)
                    continue
                elif jump_result == "error":
                    return False
                # "continue" = 不跳转，继续下一步

            i += 1

        self.workflow_completed.emit(workflow_name)
        return True

    # ---- 跳转机制 ----

    @staticmethod
    def _build_jump_labels(steps: list) -> dict:
        """扫描步骤，构建 jump_labels 映射表：label -> step_index。"""
        labels = {}
        for i, step in enumerate(steps):
            label = step.get("jump_label", "")
            if label:
                labels[label] = i
            elif step.get("is_jump_target", False):
                # 标记为跳入点但没有标签，自动生成
                label = StepExecutor._generate_label(set(labels.keys()))
                step["jump_label"] = label
                labels[label] = i
        return labels

    @staticmethod
    def _generate_label(existing: set) -> str:
        """生成唯一的跳转标签，格式 #XXXX（4位十六进制大写）。"""
        for _ in range(100):
            label = f"#{random.randint(0, 0xFFFF):04X}"
            if label not in existing:
                return label
        raise RuntimeError("Failed to generate unique jump label after 100 attempts")

    def _handle_jump(self, step: dict, current_index: int, steps: list) -> str:
        """处理步骤跳转。返回 'jumped' / 'continue' / 'error'。"""
        jump_to = step.get("jump_to", "")
        if not jump_to:
            return "continue"

        # 检查跳转目标是否存在
        if jump_to not in self._jump_labels:
            self._structured_log(logging.ERROR, "Jump target not found: %s", jump_to)
            return "continue"  # 目标不存在则继续执行

        # 条件跳转：评估条件
        jump_condition = step.get("jump_condition")
        if jump_condition:
            try:
                condition_result = self._evaluate_condition(jump_condition)
            except Exception as e:
                self._structured_log(logging.ERROR, "Jump condition eval error: %s", e)
                return "continue"
            if not condition_result:
                return "continue"  # 条件不满足，继续下一步

        # 循环回跳：检查次数限制
        jump_count = step.get("jump_count", 0)
        if jump_count > 0:
            current_count = self._jump_counters.get(jump_to, 0)
            if current_count >= jump_count:
                return "continue"  # 已达最大次数，不再跳转
            self._jump_counters[jump_to] = current_count + 1

        # 全局防死循环保护
        self._total_jumps += 1
        if self._total_jumps > _MAX_JUMPS:
            error_msg = f"Max jump limit ({_MAX_JUMPS}) exceeded"
            self._structured_log(logging.ERROR, error_msg)
            self.workflow_failed.emit(self._current_workflow, error_msg)
            return "error"

        self._structured_log(logging.INFO, "Jumping from step %d to %s (index %d)",
                             current_index, jump_to, self._jump_labels[jump_to])
        return "jumped"

    def _interruptible_sleep(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_requested:
                return
            sleep_time = min(0.1, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
