"""投屏录制：把投屏窗口中的交互录制为工作流步骤（事件驱动）。

由 MirrorWidget 的 interaction_started/ended 信号驱动，按下→抬起为一组手势：
  - 按下点 ≈ 抬起点（位移 < 阈值）→ tap 步骤
  - 有位移 → swipe 步骤（含 duration，单位毫秒）
操作间等待自动写入上一步的 wait_after（单位秒），类似按键精灵的录制。

坐标约定：步骤坐标为 **设备物理分辨率**（与 screenshot_picker 的
_img_to_device 一致，基准 base_resolution，默认 2400×1080），
由 step_executor._scale_coord 在回放时按当前设备分辨率缩放，支持跨设备回放。

字段单位（与 step_executor 对齐）：
  - tap.wait_after / swipe.wait_after：秒
  - swipe.duration：毫秒
"""
import logging
import math
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# tap 判定阈值：设备短边的 0.5%（按 base_resolution 归一化，跨设备通用）
_TAP_THRESHOLD_PCT = 0.005
# 噪点过滤：按下到抬起时长小于此值视为误触，忽略（秒）
_NOISE_MIN_DURATION = 0.008


class StepRecorder(QObject):
    """事件驱动的步骤录制器。

    接收 MirrorWidget 的交互信号，把手势分类为 tap/swipe 步骤，
    并记录操作间等待。坐标为设备物理坐标系。

    Signals:
        event_recorded(dict): 录制到一个新步骤时发出（实时预览用）
        recording_started(): 录制开始
        recording_stopped(list): 录制停止，参数为步骤列表
    """

    event_recorded = pyqtSignal(dict)
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording: bool = False
        self._steps: List[dict] = []
        self._press_point: Optional[Tuple[int, int, float]] = None  # (x, y, ts)
        self._last_end_time: float = 0.0  # 上一步抬起的绝对时间戳
        self._step_counter: int = 1
        self._base_resolution: Tuple[int, int] = (2400, 1080)

    # ---- 配置 ----
    def set_base_resolution(self, width: int, height: int) -> None:
        """设置设备物理分辨率，用于计算 tap 判定阈值。"""
        self._base_resolution = (int(width), int(height))

    # ---- 录制控制 ----
    def start_recording(self) -> bool:
        if self._recording:
            logger.warning("录制已在进行中")
            return False
        self._steps.clear()
        self._press_point = None
        self._last_end_time = 0.0
        self._step_counter = 1
        self._recording = True
        self.recording_started.emit()
        logger.info("开始录制")
        return True

    def stop_recording(self) -> List[dict]:
        if not self._recording:
            return []
        self._recording = False
        self._press_point = None
        # 最后一步的 wait_after 无下一步承接，保持默认 0（尾部等待丢弃）
        steps = list(self._steps)
        self.recording_stopped.emit(steps)
        logger.info("停止录制：共 %d 步", len(steps))
        return steps

    def is_recording(self) -> bool:
        return self._recording

    def get_steps(self) -> List[dict]:
        return list(self._steps)

    def clear(self) -> None:
        self._steps.clear()
        self._press_point = None
        self._last_end_time = 0.0
        self._step_counter = 1

    # ---- 交互信号槽（由 MirrorWidget 连接）----
    def on_interaction_started(self, x: int, y: int, ts: float) -> None:
        """按下：记录起点与时间。"""
        if not self._recording:
            return
        self._press_point = (x, y, ts)

    def on_interaction_ended(self, x: int, y: int, ts: float) -> None:
        """抬起：分类手势并生成步骤，记录操作间等待。"""
        if not self._recording or self._press_point is None:
            return
        px, py, pts = self._press_point
        self._press_point = None

        duration = ts - pts
        # 噪点过滤：极短且无意义的按下抬起
        if duration < _NOISE_MIN_DURATION:
            logger.debug("忽略噪点操作 (duration=%.4fs)", duration)
            return

        dist = math.hypot(x - px, y - py)
        threshold = self._tap_threshold()

        if dist < threshold:
            step = {
                "type": "tap",
                "x": int(px),
                "y": int(py),
                "comment": f"录制 #{self._step_counter}",
                "wait_after": 0,
            }
        else:
            step = {
                "type": "swipe",
                "x1": int(px),
                "y1": int(py),
                "x2": int(x),
                "y2": int(y),
                "duration": int(round(duration * 1000)),  # 秒 → 毫秒
                "comment": f"录制 #{self._step_counter}",
                "wait_after": 0,
            }

        # 操作间等待：写入上一步 wait_after = 本次按下时间 - 上次抬起时间
        if self._steps and self._last_end_time > 0:
            gap = max(0.0, pts - self._last_end_time)
            self._steps[-1]["wait_after"] = round(gap, 3)

        self._steps.append(step)
        self._last_end_time = ts
        self._step_counter += 1
        self.event_recorded.emit(dict(step))
        logger.info("录制步骤 #%d: %s", self._step_counter - 1, step["type"])

    def _tap_threshold(self) -> float:
        bw, bh = self._base_resolution
        return min(bw, bh) * _TAP_THRESHOLD_PCT


# 兼容旧引用（原 Recorder 为 getevent 轮询死模块，已重构为事件驱动）
Recorder = StepRecorder
