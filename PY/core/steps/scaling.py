"""坐标缩放与分辨率匹配 Mixin。"""
import logging
from typing import Tuple


class ScalingMixin:
    """处理 device_resolution 与实际设备分辨率之间的缩放计算。"""

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
            logging.getLogger(__name__).warning(msg)
            self.resolution_mismatch.emit(msg)

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
