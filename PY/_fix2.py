import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

# Fix the QMessageBox.question f-string at line 219
lines = raw.split(b'\n')
fixed_lines = []
for i, line in enumerate(lines):
    if b'QMessageBox.question' in line and b'f"' in line:
        # Replace with properly encoded Chinese
        new_line = '        if QMessageBox.question(self, "\u5173\u95ed\u4efb\u52a1", f"\u786e\u5b9a\u5173\u95ed\u4efb\u52a1\u300a{title}\u300b\u5417\uff1f", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:'.encode('utf-8')
        fixed_lines.append(new_line)
    else:
        fixed_lines.append(line)

raw = b'\n'.join(fixed_lines)
with open(filepath, 'wb') as f:
    f.write(raw)

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    lines = content.split('\n')
    if e.lineno and e.lineno <= len(lines):
        print("Line: %s" % repr(lines[e.lineno-1]))
