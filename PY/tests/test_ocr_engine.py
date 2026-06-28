"""OCR 引擎单元测试。"""
import unittest
import unittest.mock
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import OcrEngine


def _fresh_engine():
    """创建新的引擎实例（绕过单例）。"""
    engine = OcrEngine.__new__(OcrEngine)
    engine._reader = None
    engine._initialized = False
    engine._initialized_flag = True
    return engine


class TestOcrInitialize(unittest.TestCase):
    def _mock_easyocr(self):
        """返回 sys.modules 补丁，防止加载真实 easyocr/torch。"""
        mock_easyocr = unittest.mock.MagicMock()
        return unittest.mock.patch.dict('sys.modules', {'easyocr': mock_easyocr, 'torch': unittest.mock.MagicMock()})

    def test_initialize_success(self):
        engine = _fresh_engine()
        with self._mock_easyocr() as modules:
            import easyocr as mock_easyocr
            mock_easyocr.Reader.return_value = unittest.mock.MagicMock()
            result = engine.initialize(gpu=False)
            self.assertTrue(result)
            self.assertTrue(engine.is_initialized())
            mock_easyocr.Reader.assert_called_once_with(['ch_sim', 'en'], gpu=False)

    def test_initialize_failure(self):
        engine = _fresh_engine()
        with self._mock_easyocr() as modules:
            import easyocr as mock_easyocr
            mock_easyocr.Reader.side_effect = ImportError("no module")
            result = engine.initialize()
            self.assertFalse(result)
            self.assertFalse(engine.is_initialized())

    def test_initialize_idempotent(self):
        engine = _fresh_engine()
        with self._mock_easyocr() as modules:
            import easyocr as mock_easyocr
            mock_easyocr.Reader.return_value = unittest.mock.MagicMock()
            engine.initialize()
            engine.initialize()
            mock_easyocr.Reader.assert_called_once()

    def test_initialize_with_progress_callback(self):
        engine = _fresh_engine()
        with self._mock_easyocr() as modules:
            import easyocr as mock_easyocr
            mock_easyocr.Reader.return_value = unittest.mock.MagicMock()
            cb = unittest.mock.MagicMock()
            engine.initialize(progress_callback=cb)
            cb.assert_any_call(0)
            cb.assert_any_call(50)
            cb.assert_any_call(100)


class TestOcrRecognize(unittest.TestCase):
    def test_recognize_not_initialized(self):
        engine = _fresh_engine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize(img), "")

    def test_recognize_basic(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [
            (None, "购买", 0.9),
            (None, "按钮", 0.8),
        ]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.recognize(img)
        self.assertIn("购买按钮", result)

    def test_recognize_with_region(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "text", 0.9)]
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        region = {"left": 10, "top": 20, "right": 50, "bottom": 60}
        engine.recognize(img, region)
        called_img = engine._reader.readtext.call_args[0][0]
        self.assertEqual(called_img.shape, (40, 40, 3))  # bottom-top, right-left

    def test_recognize_exception_returns_empty(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.side_effect = RuntimeError("GPU OOM")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize(img), "")


class TestOcrRecognizePrice(unittest.TestCase):
    def test_recognize_price_valid(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "120000", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize_price(img), 120000)

    def test_recognize_price_with_comma(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "1,200,000", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize_price(img), 1200000)

    def test_recognize_price_too_short_returns_sentinel(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "12", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize_price(img), 100_000_000_000_000)

    def test_recognize_price_not_initialized(self):
        engine = _fresh_engine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize_price(img), 100_000_000_000_000)

    def test_recognize_price_trailing_8_correction(self):
        """末尾 '8' 应被修正为 '0'（游戏 OCR 特殊处理）。"""
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "120008", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(engine.recognize_price(img), 120000)


class TestOcrRecognizeButton(unittest.TestCase):
    def test_recognize_button_chinese(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "购买", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.recognize_button(img)
        self.assertEqual(result, ("chinese", "购买"))

    def test_recognize_button_number(self):
        engine = _fresh_engine()
        engine._initialized = True
        engine._reader = unittest.mock.MagicMock()
        engine._reader.readtext.return_value = [(None, "123456", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.recognize_button(img)
        self.assertEqual(result, ("number", "123456"))


class TestCropRegion(unittest.TestCase):
    def test_crop_no_region(self):
        engine = _fresh_engine()
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        result = engine._crop_region(img, None)
        self.assertEqual(result.shape, (100, 200, 3))

    def test_crop_with_region(self):
        engine = _fresh_engine()
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        region = {"left": 10, "top": 20, "right": 50, "bottom": 60}
        result = engine._crop_region(img, region)
        self.assertEqual(result.shape, (40, 40, 3))


if __name__ == "__main__":
    unittest.main()
