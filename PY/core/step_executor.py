import re
import logging
import threading
import time
import base64
import cv2
import numpy as np
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

_INJECTION_PATTERN = re.compile(r"[;\|`$(){}[\]]")


class StepExecutor(QObject):
    """Execute workflow steps via ADB commands."""

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
        self._last_check_result: bool = False
        self._last_ocr_result: str = ""

    def execute_step(self, workflow_name: str, step_index: int):
        """Execute a single step from a workflow."""
        workflow = self._config_manager.get_workflow(workflow_name)
        if not workflow:
            self.workflow_failed.emit(workflow_name, f"Workflow '{workflow_name}' not found")
            return
        steps = workflow.get("steps", [])
        if step_index >= len(steps):
            self.step_failed.emit(step_index, "unknown", "Step index out of range")
            return
        step = steps[step_index]
        step_type = step.get("type", "unknown")
        self.step_started.emit(step_index, step_type)
        try:
            self._execute_single_step(step, step_index)
            self.step_completed.emit(step_index, step_type)
        except Exception as e:
            self.step_failed.emit(step_index, step_type, str(e))

    def execute_workflow(self, workflow_name: str, start_index: int = 0):
        """Execute an entire workflow starting from the given step index."""
        workflow = self._config_manager.get_workflow(workflow_name)
        if not workflow:
            self.workflow_failed.emit(workflow_name, f"Workflow '{workflow_name}' not found")
            return
        steps = workflow.get("steps", [])
        total = len(steps)
        for i in range(start_index, total):
            if self._stopped:
                self.workflow_stopped.emit()
                return
            # 使用 Event 替代 busy-wait，暂停时阻塞等待恢复信号
            while self._paused:
                self._pause_event.clear()
                self._pause_event.wait()  # 阻塞直到 resume() 调用 set()
                if self._stopped:
                    self.workflow_stopped.emit()
                    return
            self.progress_updated.emit(i + 1, total)
            self.execute_step(workflow_name, i)
        self.workflow_completed.emit(workflow_name)

    def _execute_single_step(self, step: dict, step_index: int = -1):
        """Execute a single step dict."""
        step_type = step.get("type", "")
        enabled = step.get("enabled", True)
        if not enabled:
            return True

        handler = {
            "check_image": self._step_check_image,
            "ocr_region": self._step_ocr_region,
            "tap": self._step_tap,
            "swipe": self._step_swipe,
            "keyevent": self._step_keyevent,
            "wait": self._step_wait,
            "input_text": self._step_input_text,
            "force_stop": self._step_force_stop,
            "launch": self._step_launch,
            "screenshot": self._step_screenshot,
            "variable": self._step_variable,
            "condition": self._step_condition,
            "loop": self._step_loop,
            "wifi": self._step_wifi,
            "adb_command": self._step_adb_command,
            "expression": self._step_expression,
        }.get(step_type)

        if handler is None:
            logger.warning("未知步骤类型: %s", step_type)
            return False

        try:
            if step_type in ("check_image", "ocr_region"):
                result = handler(step, step_index)
            else:
                result = handler(step)
        except Exception as e:
            logger.error("步骤执行异常 [%s]: %s", step_type, e)
            return False

        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)

        return result

    # ---- 坐标缩放 ----

    def _update_scale(self):
        """根据设备分辨率更新缩放比例。"""
        res = self._device_manager.get_device_resolution()
        if res and res[0] and res[1]:
            self._scale_x = res[0] / 1080
            self._scale_y = res[1] / 1920

    def _scale_coords(self, x, y):
        return int(x * self._scale_x), int(y * self._scale_y)

    def _interruptible_sleep(self, seconds):
        """可中断的睡眠，在 stop/pause 时提前退出。"""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._stopped:
                return
            time.sleep(min(0.1, deadline - time.monotonic()))

    # ---- 步骤处理方法 ----

    def _step_tap(self, step: dict) -> bool:
        x, y = self._scale_coords(step.get("x", 0), step.get("y", 0))
        result = self._adb_core.tap(x, y)
        wait_after = step.get("wait_after", 0)
        if wait_after > 0:
            self._interruptible_sleep(wait_after)
        return result

    def _step_swipe(self, step: dict) -> bool:
        x1, y1 = self._scale_coords(step.get("x1", 0), step.get("y1", 0))
        x2, y2 = self._scale_coords(step.get("x2", 0), step.get("y2", 0))
        duration = step.get("duration", 300)
        return self._adb_core.swipe(x1, y1, x2, y2, duration)

    def _step_keyevent(self, step: dict) -> bool:
        key = step.get("key", "")
        if not key or not re.match(r'^[A-Za-z0-9_]+$', key):
            logger.warning("非法按键事件: %s", key)
            return False
        return self._adb_core.keyevent(key)

    def _step_wait(self, step: dict) -> bool:
        seconds = step.get("seconds", 1)
        self._interruptible_sleep(seconds)
        return True

    def _step_input_text(self, step: dict) -> bool:
        text = step.get("text", "")
        return self._adb_core.input_text(text)

    def _step_force_stop(self, step: dict) -> bool:
        package = step.get("package", "")
        if not package or not re.match(r'^[a-zA-Z][a-zA-Z0-9_.]*$', package):
            logger.warning("非法包名: %s", package)
            return False
        return self._adb_core.force_stop(package)

    def _step_launch(self, step: dict) -> bool:
        package = step.get("package", "")
        if not package or not re.match(r'^[a-zA-Z][a-zA-Z0-9_.]*$', package):
            logger.warning("非法包名: %s", package)
            return False
        return self._adb_core.launch(package)

    def _step_screenshot(self, step: dict) -> bool:
        frame = self._screen_capture.get_current_frame() if self._screen_capture else None
        if frame is None:
            return False
        save_path = step.get("save_path", "")
        if not save_path:
            return False
        return cv2.imwrite(save_path, frame)

    def _step_variable(self, step: dict) -> bool:
        var_name = step.get("var_name", "")
        var_type = step.get("var_type", "string")
        var_value = step.get("var_value", "")
        if not var_name:
            return False
        if var_type == "int":
            self._variables[var_name] = int(var_value)
        elif var_type == "float":
            self._variables[var_name] = float(var_value)
        elif var_type == "bool":
            self._variables[var_name] = var_value.lower() in ("true", "1", "yes")
        else:
            self._variables[var_name] = str(var_value)
        return True

    def _step_condition(self, step: dict) -> bool:
        check = step.get("check", {})
        result = self._evaluate_condition(check)
        steps = step.get("then_steps" if result else "else_steps", [])
        for s in steps:
            if self._stopped:
                return False
            self._execute_single_step(s)
        return True

    def _step_loop(self, step: dict) -> bool:
        max_count = step.get("max_count", -1)
        condition = step.get("condition")
        steps = step.get("steps", [])
        count = 0
        while True:
            if self._stopped:
                return False
            if 0 <= max_count <= count:
                break
            if condition and not self._evaluate_condition(condition):
                break
            for s in steps:
                if self._stopped:
                    return False
                self._execute_single_step(s)
            count += 1
        return True

    def _step_wifi(self, step: dict) -> bool:
        action = step.get("action", "")
        if action == "enable":
            return self._adb_core.wifi_enable()
        elif action == "disable":
            return self._adb_core.wifi_disable()
        logger.warning("未知 wifi 动作: %s", action)
        return False

    def _step_adb_command(self, step: dict) -> bool:
        cmd = step.get("adb_cmd", "")
        if not cmd or len(cmd) > 200:
            logger.warning("ADB 命令为空或过长")
            return False
        if re.search(r'[;&|`$]', cmd):
            logger.warning("ADB 命令包含危险字符: %s", cmd)
            return False
        self._adb_core.shell(cmd)
        return True

    def _step_expression(self, step: dict) -> bool:
        from core.expression_eval import evaluate_expression
        expr = step.get("expression", "")
        if not expr:
            return False
        try:
            result = evaluate_expression(expr, self._variables)
            assign_to = step.get("assign_variable")
            if assign_to:
                self._variables[assign_to] = result
            return True
        except ValueError:
            return False

    def _evaluate_condition(self, check: dict) -> bool:
        """评估条件检查。"""
        check_type = check.get("type", "")
        if check_type == "check_image":
            return self._step_check_image(check)
        elif check_type == "ocr_region":
            text = self._step_ocr_region(check)
            expected = check.get("expected_text", "")
            return text == expected if expected else bool(text)
        elif check_type == "variable":
            var_name = check.get("var_name", "")
            return bool(self._variables.get(var_name))
        return False
    
    def _step_check_image(self, step: dict, step_index: int = -1) -> bool:
        """执行图像匹配步骤并保存结果"""
        try:
            # 获取当前帧
            frame = self._screen_capture.get_current_frame()
            if frame is None:
                raise Exception("获取屏幕帧失败")
            
            # 加载模板
            template_name = step.get("template", "")
            if not template_name:
                raise Exception("模板文件名为空")
            
            template = self._load_template(template_name)
            threshold = step.get("threshold", 0.85)
            
            # 执行匹配
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            # 匹配位置（可能为 None）
            match_x = int(max_loc[0]) if max_loc else 0
            match_y = int(max_loc[1]) if max_loc else 0

            # 构建结果数据
            execution_result = {
                "status": "success" if max_val >= threshold else "fail",
                "confidence": float(max_val),
                "match_location": {"x": match_x, "y": match_y},
                "timestamp": int(time.time()),
                "error_message": ""
            }
            
            # 构建预览数据
            preview = {
                "template_image": self._image_to_base64(template),
                "match_region": {
                    "x": match_x,
                    "y": match_y,
                    "w": template.shape[1],
                    "h": template.shape[0]
                },
                "screenshot_thumbnail": self._create_thumbnail(frame)
            }
            
            # 更新步骤数据
            step["execution_result"] = execution_result
            step["preview"] = preview
            
            # 发送信号
            if step_index >= 0:
                self.step_result_updated.emit(step_index, {
                    "execution_result": execution_result,
                    "preview": preview
                })
            
            logger.info("图像匹配完成: template=%s, confidence=%.2f, threshold=%.2f, result=%s", 
                       template_name, max_val, threshold, "成功" if max_val >= threshold else "失败")
            
            self._last_check_result = max_val >= threshold
            return max_val >= threshold
            
        except Exception as e:
            execution_result = {
                "status": "fail",
                "confidence": 0,
                "match_location": None,
                "timestamp": int(time.time()),
                "error_message": str(e)
            }
            step["execution_result"] = execution_result
            
            if step_index >= 0:
                self.step_result_updated.emit(step_index, {
                    "execution_result": execution_result
                })
            
            logger.error("图像匹配失败: %s", e)
            raise
    
    def _step_ocr_region(self, step: dict, step_index: int = -1) -> str:
        """执行 OCR 识别步骤并保存结果"""
        try:
            # 获取当前帧
            frame = self._screen_capture.get_current_frame()
            if frame is None:
                raise Exception("获取屏幕帧失败")

            # 获取区域
            region = step.get("region", {})
            left = region.get("left", 0)
            top = region.get("top", 0)
            right = region.get("right", 0)
            bottom = region.get("bottom", 0)

            # 裁剪区域
            roi = frame[top:bottom, left:right]

            if roi.size == 0:
                raise Exception("OCR 裁剪区域为空")

            # 执行 OCR（获取详细结果含逐字置信度）
            text = self._ocr_engine.recognize(roi)
            ocr_details = self._ocr_engine.recognize_detailed(roi)

            # 构建结果数据
            execution_result = {
                "status": "success",
                "recognized_text": text,
                "confidence": (sum(d.get("confidence", 0) for d in ocr_details) / len(ocr_details)) if ocr_details and len(ocr_details) > 0 else 0,
                "ocr_details": ocr_details,
                "timestamp": int(time.time()),
                "error_message": ""
            }
            
            # 构建预览数据
            preview = {
                "region_image": self._image_to_base64(roi),
                "highlighted_text": self._highlight_text_in_image(frame, region, text),
                "screenshot_thumbnail": self._create_thumbnail(frame)
            }
            
            # 更新步骤数据
            step["execution_result"] = execution_result
            step["preview"] = preview
            
            # 发送信号
            if step_index >= 0:
                self.step_result_updated.emit(step_index, {
                    "execution_result": execution_result,
                    "preview": preview
                })
            
            logger.info("OCR识别完成: region=(%d,%d,%d,%d), text='%s'", 
                       left, top, right, bottom, text)
            
            self._last_ocr_result = text
            assign_variable = step.get("assign_variable")
            if assign_variable:
                self._variables[assign_variable] = text
            return text
            
        except Exception as e:
            execution_result = {
                "status": "fail",
                "recognized_text": "",
                "confidence": 0,
                "timestamp": int(time.time()),
                "error_message": str(e)
            }
            step["execution_result"] = execution_result
            
            if step_index >= 0:
                self.step_result_updated.emit(step_index, {
                    "execution_result": execution_result
                })
            
            logger.error("OCR识别失败: %s", e)
            raise
    
    def _load_template(self, template_name: str) -> np.ndarray:
        """加载模板图像"""
        template_dir = self._config_manager.get_config("recognition.template_dir", "tp")
        template_path = f"{template_dir}/{template_name}"
        
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            raise Exception(f"加载模板图片失败: {template_path}")
        
        return template
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """将图像转换为 base64 字符串"""
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    def _create_thumbnail(self, frame: np.ndarray, size=(100, 100)) -> str:
        """创建缩略图"""
        thumbnail = cv2.resize(frame, size)
        return self._image_to_base64(thumbnail)
    
    def _highlight_text_in_image(self, frame: np.ndarray, region: dict, text: str) -> str:
        """在图像中高亮显示识别的文本"""
        # 创建副本
        highlighted = frame.copy()
        
        # 绘制矩形
        left = region.get("left", 0)
        top = region.get("top", 0)
        right = region.get("right", 0)
        bottom = region.get("bottom", 0)
        
        cv2.rectangle(highlighted, (left, top), (right, bottom), (0, 255, 0), 2)
        
        # 添加文本
        cv2.putText(highlighted, text, (left, top - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return self._image_to_base64(highlighted)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
        self._pause_event.set()  # 唤醒暂停等待的线程

    def stop(self):
        self._stopped = True
        self._paused = False
        self._pause_event.set()  # 唤醒暂停等待的线程，使其能退出

    def is_paused(self) -> bool:
        return self._paused

    def get_current_frame(self):
        """公开接口：获取当前屏幕帧。"""
        if self._screen_capture is None:
            return None
        return self._screen_capture.get_current_frame()
