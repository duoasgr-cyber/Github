import logging
import threading
import re
import numpy as np

logger = logging.getLogger(__name__)


class OcrEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized_flag'):
            return
        self._reader = None
        self._initialized = False
        self._initialized_flag = True

    def initialize(self, gpu: bool = False, progress_callback=None) -> bool:
        if self._initialized:
            logger.debug("OCR already initialized, skipping")
            return True
        try:
            if progress_callback:
                progress_callback(0)
            logger.debug("Starting OCR initialization, gpu=%s", gpu)
            import easyocr
            if progress_callback:
                progress_callback(50)
            self._reader = easyocr.Reader(['ch_sim', 'en'], gpu=gpu)
            self._initialized = True
            if progress_callback:
                progress_callback(100)
            logger.debug("OCR initialization complete")
            return True
        except Exception as e:
            logger.error("OCR initialization failed: %s", e)
            self._reader = None
            self._initialized = False
            logger.warning("OCR unavailable: running in degraded mode, recognition features disabled")
            return False

    def is_initialized(self) -> bool:
        return self._initialized

    def recognize(self, image: np.ndarray, region: dict = None) -> str:
        if not self._initialized or self._reader is None:
            logger.warning("OCR not initialized when recognize was called")
            return ""
        try:
            cropped = self._crop_region(image, region)
            results = self._reader.readtext(cropped)
            text = "".join([item[1] for item in results])
            logger.debug("OCR recognize result: %s", text)
            return text
        except Exception as e:
            logger.error("OCR recognize error: %s", e)
            return ""

    def recognize_detailed(self, image: np.ndarray, region: dict = None) -> list:
        """返回详细的 OCR 识别结果，包含每个识别区域的文本和置信度。

        Returns:
            list of dict, 每个元素包含:
                - text: str, 识别的文本片段
                - confidence: float, 置信度 (0-1)
                - bbox: list, 边界框 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        if not self._initialized or self._reader is None:
            logger.warning("OCR not initialized when recognize_detailed was called")
            return []
        try:
            cropped = self._crop_region(image, region)
            results = self._reader.readtext(cropped)
            detailed = []
            for bbox, text, confidence in results:
                detailed.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox,
                })
            logger.debug("OCR recognize_detailed result: %d items", len(detailed))
            return detailed
        except Exception as e:
            logger.error("OCR recognize_detailed error: %s", e)
            return []

    def recognize_price(self, image: np.ndarray, region: dict = None) -> int:
        if not self._initialized or self._reader is None:
            logger.warning("OCR not initialized when recognize_price was called")
            return 100000000000000
        try:
            cropped = self._crop_region(image, region)
            results = self._reader.readtext(cropped)
            text = "".join([item[1] for item in results])
            logger.debug("OCR recognize_price raw result: %s", text)
            cleaned = re.sub(r'[^\d,]', '', text)
            cleaned = cleaned.replace(',', '')
            # Game-specific: OCR often misreads trailing '0' as '8'
            # This correction only applies to valid price-like numbers
            if cleaned and cleaned[-1] == '8' and len(cleaned) >= 4:
                cleaned = cleaned[:-1] + '0'
            if len(cleaned) < 6:
                logger.debug("Price too short (%d digits), returning default", len(cleaned))
                return 100000000000000
            result = int(cleaned)
            logger.debug("OCR recognize_price result: %d", result)
            return result
        except Exception as e:
            logger.error("OCR recognize_price error: %s", e)
            return 100000000000000

    def recognize_button(self, image: np.ndarray, region: dict = None) -> tuple:
        if not self._initialized or self._reader is None:
            logger.warning("OCR not initialized when recognize_button was called")
            return ("unknown", "")
        try:
            cropped = self._crop_region(image, region)
            results = self._reader.readtext(cropped)
            text = "".join([item[1] for item in results])
            logger.debug("OCR recognize_button result: %s", text)
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
            if chinese_pattern.search(text):
                return ("chinese", text)
            digit_count = sum(1 for c in text if c.isdigit())
            if digit_count > len(text) / 2 and len(text) > 0:
                return ("number", text)
            return ("unknown", text)
        except Exception as e:
            logger.error("OCR recognize_button error: %s", e)
            return ("unknown", "")

    def _crop_region(self, image: np.ndarray, region: dict = None) -> np.ndarray:
        if region is None:
            return image
        left = region.get("left", 0)
        top = region.get("top", 0)
        right = region.get("right", image.shape[1])
        bottom = region.get("bottom", image.shape[0])
        return image[top:bottom, left:right]


_engine = OcrEngine()


def initialize(gpu: bool = False, progress_callback=None) -> bool:
    return _engine.initialize(gpu=gpu, progress_callback=progress_callback)


def recognize(image: np.ndarray, region: dict = None) -> str:
    return _engine.recognize(image, region=region)


def recognize_price(image: np.ndarray, region: dict = None) -> int:
    return _engine.recognize_price(image, region=region)


def recognize_button(image: np.ndarray, region: dict = None) -> tuple:
    return _engine.recognize_button(image, region=region)


def is_initialized() -> bool:
    return _engine.is_initialized()
