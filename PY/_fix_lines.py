import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

# Replace specific garbled byte sequences
replacements = [
    # Window title: 涓夎娲茶嚜鍔ㄦ姠璐伐鍏?v2.0 -> 三角洲自动抢购工具 v2.0
    (b'\xe6\xb6\x8a\xe5\xa4\x8e\xe8\x87\x9c\xe5\x93\xb2\xe5\x8f\xad\xe7\x8e\x93\xe4\xba\x91\xe5\x88\xa4? v2.0',
     '\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0'.encode('utf-8')),
    # Connection label: 杩炴帴: 鏂紑 -> 连接: 断开
    (b'\xe6\xb8\xa1\xe6\x89\xb4: \xe9\x8f\x82 v2.0',
     '\u8fde\u63a5: \u65ad\u5f00'.encode('utf-8')),
]

# Let me just find the exact bytes for each garbled line
lines_raw = raw.split(b'\n')
garbled_line_nums = [92, 347, 362, 434, 436, 474, 486]  # 0-indexed

for ln in garbled_line_nums:
    if ln < len(lines_raw):
        line = lines_raw[ln]
        # Decode for display
        try:
            decoded = line.decode('utf-8')
        except:
            decoded = repr(line)
        print("Line %d: %s" % (ln+1, decoded[:80]))

# The issue is these strings have mixed encoding. Let me replace them line by line.
# Line 92: window title
lines_raw[92] = '        self.setWindowTitle("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'.encode('utf-8')
# Line 347: connection label
lines_raw[347] = '        self._connection_label = QLabel("\u8fde\u63a5: \u65ad\u5f00")'.encode('utf-8')
# Line 362: tray tooltip
lines_raw[362] = '        self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'.encode('utf-8')
# Line 434: exception handler
lines_raw[434] = '            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)'.encode('utf-8')
# Line 436: exception handler
lines_raw[436] = '                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)'.encode('utf-8')
# Line 474: warning
lines_raw[474] = '            logging.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7")'.encode('utf-8')
# Line 486: info
lines_raw[486] = '        logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)'.encode('utf-8')

raw = b'\n'.join(lines_raw)
with open(filepath, 'wb') as f:
    f.write(raw)

# Verify
import re
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
garbled = re.findall(r'[\ue000-\uf8ff]', content)
print("Garbled chars remaining: %d" % len(garbled))

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
