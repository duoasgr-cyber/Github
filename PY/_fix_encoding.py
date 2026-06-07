import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace garbled strings with proper Chinese
replacements = [
    # Window title
    ('\u5b95\u30e4\u7d94\u5a34\u4f3a\u7d2a\u6d88\u003f', '\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'),
    # NAV_ITEMS labels
    ('\u91d2\u9f58', '\u914d\u7f6e'),
    ('\u8bf9\u30e2\u7ba1\u30f3', '\u8bbe\u5907\u7ba1\u7406'),
    ('\u93c8\u2229\u76d1\u63a5', '\u8fd0\u884c\u76d1\u63a7'),
    ('\u5b2c\u8bd8', '\u6d4b\u8bd5'),
    # Settings dialog
    ('\u8bf9\u9898', '\u8bbe\u7f6e'),
    # Status labels
    ('\u8bbe\u5907: \u672a\u8fde\u63a5', '\u8bbe\u5907: \u672a\u8fde\u63a5'),
    ('\u8fde\u63a5: \u65ad\u5f00', '\u8fde\u63a5: \u65ad\u5f00'),
    ('\u8fde\u63a5: \u5df2\u8fde\u63a5', '\u8fde\u63a5: \u5df2\u8fde\u63a5'),
    # Error handling
    ('\u672a\u5904\u7406\u7684\u5f02\u5e38', '\u672a\u5904\u7406\u7684\u5f02\u5e38'),
    # Monitoring status
    ('\u8fd0\u884c\u4e2d', '\u8fd0\u884c\u4e2d'),
    ('\u505c\u6b62\u4e2d..', '\u505c\u6b62\u4e2d..'),
    ('\u5df2\u6682\u505c', '\u5df2\u6682\u505c'),
    ('\u5df2\u5b8c\u6210', '\u5df2\u5b8c\u6210'),
    # Log messages
    ('\u542f\u52a8\u76d1\u63a7: %s', '\u542f\u52a8\u76d1\u63a7: %s'),
    # Error dialogs
    ('\u65e0\u6cd5\u542f\u52a8', '\u65e0\u6cd5\u542f\u52a8'),
]

# Instead of individual replacements, let me find all f-strings and regular strings
# with garbled content and fix them by finding the pattern
# The issue is that the file has mixed encodings

# Let me try a different approach: read as bytes, fix the encoding issues
with open(filepath, 'rb') as f:
    raw = f.read()

# The file has some lines that are valid UTF-8 and some that are garbled
# Let me fix the specific broken lines

# Fix line 92: window title - find the pattern
# The title should be "三角洲自动抢购工具 v2.0"
title_old = b'\xe5\xb9\x95\xe3\x83\xa4\xe7\xb6\x94\xe5\xa8\xb4\xe4\xbd\xba\xe7\xb4\xaa\xe6\x9d\x88?'
title_new = '\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'.encode('utf-8') + b' v2.0'
raw = raw.replace(title_old + b' v2.0', title_new)

# Fix the f-string at line 219
# Find the broken QMessageBox.question line
# The issue is the garbled Chinese breaks the f-string
# Let me find it by looking for the QMessageBox.question pattern near line 219

lines = raw.split(b'\n')
fixed_lines = []
for i, line in enumerate(lines):
    # Check if this line has a QMessageBox with garbled text
    if b'QMessageBox.question' in line and b'f"' in line:
        # Replace the entire QMessageBox.question call
        # with proper Chinese
        fixed_line = (
            b'        if QMessageBox.question(self, "\u5173\u95ed\u4efb\u52a1", '
            b'f"\u786e\u5b9a\u5173\u95ed\u4efb\u52a1\u300a{title}\u300b\u5417\uff1f", '
            b'QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:'
        )
        fixed_lines.append(fixed_line.encode('utf-8'))
    elif b'"' in line and b'\xe5\xae\xb8' in line:
        # This line has garbled Chinese, try to fix common patterns
        # Replace known garbled sequences
        fixed = line
        fixed = fixed.replace(
            b'\xe5\xae\xb8\xe3\x83\xa4\xe7\xb6\x94\xe5\xa8\xb4\xe4\xbd\xba\xe7\xb4\xaa\xe6\x9d\x88?',
            '\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'.encode('utf-8')
        )
        fixed_lines.append(fixed)
    else:
        fixed_lines.append(line)

raw = b'\n'.join(fixed_lines)

with open(filepath, 'wb') as f:
    f.write(raw)

print("File fixed")

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    lines = content.split('\n')
    if e.lineno:
        print("Line: %s" % repr(lines[e.lineno-1]))
