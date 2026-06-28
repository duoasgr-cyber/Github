import logging

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.step_executor import StepExecutor

logger = logging.getLogger(__name__)


class _ScriptWorker(QThread):
    """后台线程执行工作流，桥接 StepExecutor 信号到主线程。"""

    step_started = pyqtSignal(int, str)
    step_completed = pyqtSignal(int, str)
    step_failed = pyqtSignal(int, str, str)
    workflow_completed = pyqtSignal(str)
    workflow_failed = pyqtSignal(str, str)
    workflow_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)
    finished_signal = pyqtSignal()

    def __init__(self, step_executor: StepExecutor, workflow_name: str,
                 start_index: int = 0, parent=None):
        super().__init__(parent)
        self._step_executor = step_executor
        self._workflow_name = workflow_name
        self._start_index = start_index

    def run(self):
        se = self._step_executor
        se.step_started.connect(self.step_started.emit)
        se.step_completed.connect(self.step_completed.emit)
        se.step_failed.connect(self.step_failed.emit)
        se.workflow_completed.connect(self.workflow_completed.emit)
        se.workflow_failed.connect(self.workflow_failed.emit)
        se.workflow_stopped.connect(self.workflow_stopped.emit)
        se.progress_updated.connect(self.progress_updated.emit)

        try:
            se.execute_workflow(self._workflow_name, self._start_index)
        except Exception as e:
            logger.error("ScriptRunner 执行异常: %s", e)
            self.workflow_failed.emit(self._workflow_name, str(e))

        se.step_started.disconnect(self.step_started.emit)
        se.step_completed.disconnect(self.step_completed.emit)
        se.step_failed.disconnect(self.step_failed.emit)
        se.workflow_completed.disconnect(self.workflow_completed.emit)
        se.workflow_failed.disconnect(self.workflow_failed.emit)
        se.workflow_stopped.disconnect(self.workflow_stopped.emit)
        se.progress_updated.disconnect(self.progress_updated.emit)

        self.finished_signal.emit()


class ScriptRunner(QObject):
    """可复用的脚本执行服务，支持从头/从指定步骤启动、停止。"""

    run_started = pyqtSignal(str, int)
    run_finished = pyqtSignal()
    step_started = pyqtSignal(int, str)
    step_completed = pyqtSignal(int, str)
    step_failed = pyqtSignal(int, str, str)
    workflow_completed = pyqtSignal(str)
    workflow_failed = pyqtSignal(str, str)
    workflow_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)

    def __init__(self, step_executor: StepExecutor, parent=None):
        super().__init__(parent)
        self._step_executor = step_executor
        self._worker = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def run_from(self, workflow_name: str, start_index: int):
        """从指定步骤开始执行工作流。"""
        if self.is_running:
            logger.warning("ScriptRunner: 已有任务在运行，忽略 run_from 请求")
            return
        self._start_worker(workflow_name, start_index)

    def run_full(self, workflow_name: str):
        """从第一步开始执行整个工作流。"""
        if self.is_running:
            logger.warning("ScriptRunner: 已有任务在运行，忽略 run_full 请求")
            return
        self._start_worker(workflow_name, 0)

    def stop(self):
        """请求停止当前执行。"""
        if not self.is_running:
            return
        self._step_executor.stop()

    def _start_worker(self, workflow_name: str, start_index: int):
        self._worker = _ScriptWorker(
            self._step_executor, workflow_name, start_index, parent=self
        )
        self._worker.step_started.connect(self.step_started.emit)
        self._worker.step_completed.connect(self.step_completed.emit)
        self._worker.step_failed.connect(self.step_failed.emit)
        self._worker.workflow_completed.connect(self.workflow_completed.emit)
        self._worker.workflow_failed.connect(self.workflow_failed.emit)
        self._worker.workflow_stopped.connect(self.workflow_stopped.emit)
        self._worker.progress_updated.connect(self.progress_updated.emit)
        self._worker.finished_signal.connect(self._on_worker_finished)

        self.run_started.emit(workflow_name, start_index)
        self._worker.start()

    def _on_worker_finished(self):
        if self._worker is not None:
            self._worker.step_started.disconnect(self.step_started.emit)
            self._worker.step_completed.disconnect(self.step_completed.emit)
            self._worker.step_failed.disconnect(self.step_failed.emit)
            self._worker.workflow_completed.disconnect(self.workflow_completed.emit)
            self._worker.workflow_failed.disconnect(self.workflow_failed.emit)
            self._worker.workflow_stopped.disconnect(self.workflow_stopped.emit)
            self._worker.progress_updated.disconnect(self.progress_updated.emit)
            self._worker.finished_signal.disconnect(self._on_worker_finished)
            self._worker = None

        self.run_finished.emit()
