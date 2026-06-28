"""ADB 操作类 step 处理器：tap/long_press/swipe/keyevent/wait/wifi/force_stop/launch/screenshot/pull_file/delete_file/tap_point/input_text/adb_command"""
import logging
import cv2

logger = logging.getLogger(__name__)


class AdbOpsMixin:
    """ADB 与设备操作类 step 的混入。依赖主类的 _adb_core/_screen_capture/_scale_coord/_interruptible_sleep/_variables/_stop_requested。"""

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

    def _step_tap_point(self, step: dict) -> bool:
        x = step["x"]
        y = step["y"]
        result = self._adb_core.tap(x, y)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_input_text(self, step: dict) -> bool:
        text = step.get("text", "")
        return self._adb_core.input_text(text)

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
