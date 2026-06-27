"""验证 logger.RotatingFileHandler 按大小滚动产生 .1 备份。"""
import os
import sys
import tempfile
import logging
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import setup_logging


class TestLogRotation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="log_rot_")
        self._log_path = os.path.join(self._tmp, "rot.log")
        # 清理可能残留的 handler，避免相互干扰
        root = logging.getLogger()
        self._saved_handlers = root.handlers[:]
        root.handlers.clear()

    def tearDown(self):
        root = logging.getLogger()
        root.handlers.clear()
        for h in self._saved_handlers:
            root.addHandler(h)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_rotation_creates_backup(self):
        # max_log_size_mb=0.001 → 约 1KB
        setup_logging(log_file=self._log_path, level="DEBUG", max_log_size_mb=0.001)
        logger = logging.getLogger("rotation_test")

        # 写入明显超过 1KB 的日志
        line = "x" * 200
        for _ in range(20):
            logger.info(line)

        # 强制 flush 所有 handler
        for h in logging.getLogger().handlers:
            h.flush()

        backup = self._log_path + ".1"
        self.assertTrue(os.path.exists(backup),
                        f"Expected rotated backup at {backup}, dir contents: {os.listdir(self._tmp)}")


if __name__ == "__main__":
    unittest.main()
