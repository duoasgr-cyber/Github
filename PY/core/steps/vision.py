"""视觉识别类 step 处理器：check_image/ocr_region 及条件检查辅助方法"""
import os
import re
import logging
import cv2

logger = logging.getLogger(__name__)


class VisionMixin:
    """图像/OCR 识别类 step 与条件检查的混入。依赖主类的 _screen_capture/_ocr_engine/_config_manager/_variables/_last_check_result/_last_ocr_result/check_image_result/ocr_result。"""

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
