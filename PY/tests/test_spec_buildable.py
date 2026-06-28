"""静态检查 app.spec 可构建性：入口文件、datas 路径必须存在。

不调用 PyInstaller（太重），只做静态存在性断言。
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "app.spec")


def _parse_analysis_args(spec_text: str):
    """从 app.spec 文本中提取 Analysis([...]) 的第一个列表参数（入口）和 datas 列表。"""
    entry_match = re.search(r"Analysis\(\s*\[([^\]]+)\]", spec_text)
    entries = []
    if entry_match:
        for m in re.finditer(r"'([^']+)'", entry_match.group(1)):
            entries.append(m.group(1))

    datas_match = re.search(r"datas\s*=\s*\[([^\]]+)\]", spec_text, re.DOTALL)
    datas = []
    if datas_match:
        for m in re.finditer(r"\(\s*'([^']+)'", datas_match.group(1)):
            datas.append(m.group(1))
    return entries, datas


class TestSpecBuildable(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(SPEC_PATH), f"app.spec missing at {SPEC_PATH}")
        with open(SPEC_PATH, "r", encoding="utf-8") as f:
            self.spec_text = f.read()

    def test_entry_file_exists(self):
        entries, _ = _parse_analysis_args(self.spec_text)
        self.assertTrue(entries, "No entry script found in Analysis([...])")
        for entry in entries:
            self.assertTrue(os.path.exists(os.path.join(ROOT, entry)),
                            f"Entry file missing: {entry}")

    def test_datas_paths_exist(self):
        _, datas = _parse_analysis_args(self.spec_text)
        self.assertTrue(datas, "datas list is empty or unparsed")
        for d in datas:
            self.assertTrue(os.path.exists(os.path.join(ROOT, d)),
                            f"datas path missing: {d}")

    def test_entry_is_main_not_app(self):
        """P0 修复：app.spec 的入口应为 main.py（曾错写为 app.py）。"""
        entries, _ = _parse_analysis_args(self.spec_text)
        self.assertIn("main.py", entries)
        self.assertNotIn("app.py", entries)


if __name__ == "__main__":
    unittest.main()
