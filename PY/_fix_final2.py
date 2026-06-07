import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')

# Fix line 496 (0-indexed): "停止中.., -> "停止中..",
lines[496] = lines[496].replace(
    b'\xe4\xb8\xad..,',
    b'\xe4\xb8\xad..",'
)

# Fix line 500: "运行中, -> "运行中",
lines[500] = lines[500].replace(
    b'\xe4\xb8\xad,',
    b'\xe4\xb8\xad",'
)

# Fix line 504: "已完成?, -> "已完成",
lines[504] = lines[504].replace(
    b'\xe6\x88\x90?,',
    b'\xe6\x88\x90",'
)

raw = b'\n'.join(lines)
with open(filepath, 'wb') as f:
    f.write(raw)

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))
