import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix window title (line 93)
content = content.replace(
    'self.setWindowTitle("\u6d9a\u590e\u879c\u52dd\u514b\u57c8?\u5be6\u0452v2.0")',
    'self.setWindowTitle("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'
)
content = content.replace(
    'self.setWindowTitle("\u6d9a\u590e\u879c\u52dd\u514b\u57c8',
    'self.setWindowTitle("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'
)

# 2. Fix _init_status_bar - restore addPermanentWidget calls and fix connection label
old_status = '''    def _init_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._device_label = QLabel("\u8bbe\u5907: \u672a\u8fde\u63a5")
        self._connection_label = QLabel("\u8fde\u63a5: \u65ad\u5f00")
        self._ocr_label = QLabel("OCR: \u672a\u52a0\u8f7d")

        for label in (self._device_label, self._connection_label, self._ocr_label):
            label.setFont(QFont("Microsoft YaHei", 10))
        self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'''

new_status = '''    def _init_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._device_label = QLabel("\u8bbe\u5907: \u672a\u8fde\u63a5")
        self._connection_label = QLabel("\u8fde\u63a5: \u65ad\u5f00")
        self._ocr_label = QLabel("OCR: \u672a\u52a0\u8f7d")

        for label in (self._device_label, self._connection_label, self._ocr_label):
            label.setFont(QFont("Microsoft YaHei", 10))
            status_bar.addPermanentWidget(label)'''

content = content.replace(old_status, new_status)

# 3. Fix _init_tray tooltip (line 363)
content = content.replace(
    'self._tray_icon.setToolTip("\u6d9a\u590e\u879c\u52dd\u514b\u57c8',
    'self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'
)

# 4. Fix _setup_exception_handler - remove duplicate garbled block
old_handler_body = '''            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)
            try:
                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)
            except Exception:
                pass
            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)
            try:
                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)
            except Exception:
                pass'''

new_handler_body = '''            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)
            try:
                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)
            except Exception:
                pass'''

content = content.replace(old_handler_body, new_handler_body)

# 5. Fix _on_start_monitoring garbled strings
content = content.replace(
    'logging.warning("\u94fe\u20ac\u9009\u5b57\u5de5\u4f5c\u6d41\uff0c无法启动\u76d1\u63a7")',
    'logging.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7")'
)
content = content.replace(
    'logging.warning("\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d")',
    'logging.warning("\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d")'
)
content = content.replace(
    'logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)',
    'logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)'
)

# 6. Fix the broken bottom section - rewrite from set_connection_status to end
# Find "def set_connection_status" and replace everything after it to the end
idx = content.find('    def set_connection_status(self, connected: bool):')
if idx >= 0:
    before = content[:idx]
    new_bottom = '''    def set_connection_status(self, connected: bool):
        self._connection_label.setText("\u8fde\u63a5: \u5df2\u8fde\u63a5" if connected else "\u8fde\u63a5: \u65ad\u5f00")

    def _on_step_started(self, index: int, step_type: str):
        logging.info("\u6b65\u9aa4 %d \u5f00\u59cb %s", index + 1, step_type)

    def _on_workflow_completed(self, name: str):
        logging.info("\u5de5\u4f5c\u6d41\u5b8c\u6210 %s", name)

    def _on_workflow_failed(self, name: str, error: str):
        logging.error("\u5de5\u4f5c\u6d41\u5931\u8d25 %s - %s", name, error)

    def _on_workflow_stopped(self):
        logging.info("\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62")

    def closeEvent(self, event):
        self._save_task_snapshot()
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

    def _shutdown(self):
        try:
            self._step_executor.stop()
        except Exception:
            pass
'''
    content = before + new_bottom

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))

# Check for remaining garbled chars
import re
garbled = re.findall(r'[\ue000-\uf8ff]', content)
if garbled:
    print("Garbled chars remaining: %d" % len(garbled))
    for i, line in enumerate(content.split('\n')):
        for c in line:
            if '\ue000' <= c <= '\uf8ff':
                print("  Line %d: U+%04X in %s" % (i+1, ord(c), line[:60]))
                break
else:
    print("No garbled chars remaining!")
