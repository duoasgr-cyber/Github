import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

lines_raw = raw.split(b'\n')
garbled_line_nums = [92, 347, 362, 434, 436, 474, 486]

lines_raw[92] = '        self.setWindowTitle("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'.encode('utf-8')
lines_raw[347] = '        self._connection_label = QLabel("\u8fde\u63a5: \u65ad\u5f00")'.encode('utf-8')
lines_raw[362] = '        self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'.encode('utf-8')
lines_raw[434] = '            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)'.encode('utf-8')
lines_raw[436] = '                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)'.encode('utf-8')
lines_raw[474] = '            logging.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7")'.encode('utf-8')
lines_raw[486] = '        logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)'.encode('utf-8')

raw = b'\n'.join(lines_raw)
with open(filepath, 'wb') as f:
    f.write(raw)

import re, ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
garbled = re.findall(r'[\ue000-\uf8ff]', content)
print("Garbled chars remaining: %d" % len(garbled))
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
