"""扫描源码确认无 UTF-8↔GBK 乱码残留。

P0 阶段集中修复了 core/ 与 ui/ 下大量 mojibake，本用例作为回归门，
防止后续编辑再次引入乱码字符。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 这些字符在正常简体中文技术文档中极少出现，但在 UTF-8↔GBK 反向解码的
# 乱码中频繁出现（来自本项目历史 P0 修复记录）。任一出现即判失败。
MOJIBAKE_MARKERS = set(
    "鍚鐢閫杩涓鏈鐨鐧鐩鐗鎺鏀鏁鏄绔姝纭鍛鍑鍒浣浼鐣鍙鍦鍨鏈"
    "鐢鏈鏈鏈鏈鏀鏀鏀鏀鐩鐩鐩鐩鐨鐨鐨鐨鐧鐧鐧鐧鏈鏈鏈鏈"
    "鍙鍨鏈鐢鏈鐨鐩鐧鐗鏀鏁鏄鏈鐧鐩鐗鏀鏁鏄鐧鐩鐗鏀鏁鏄"
    "绗笁纭畝鍛戒护鍑嗗浣跨敤浼氬憳姝ラ鍒犻櫎鐣欐剰閫夋嫨"
)


def _iter_source_files():
    for sub in ("core", os.path.join("ui")):
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


class TestNoMojibake(unittest.TestCase):
    def test_no_mojibake_markers_in_source(self):
        offenders = []
        for path in _iter_source_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                offenders.append((path, "encoding error (not valid UTF-8)"))
                continue
            found = sorted(c for c in MOJIBAKE_MARKERS if c in text)
            if found:
                rel = os.path.relpath(path, ROOT)
                offenders.append((rel, "contains markers: " + "".join(found)))
        self.assertFalse(offenders,
                         "Mojibake markers found:\n" +
                         "\n".join(f"  {p}: {detail}" for p, detail in offenders))


if __name__ == "__main__":
    unittest.main()
