import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

# Fix the remaining 3 broken lines
# Line 497: missing closing quote after "..
raw = raw.replace(
    b'\xe5\x81\x9c\xe6\xad\xa2\xe4\xb8\xad.., "#ffaa00")',
    '\u505c\u6b62\u4e2d..".encode("utf-8") + b', "#ffaa00")'
)

# Actually let me just do it properly
# The issue is the Chinese text doesn't have a closing quote before the comma

# Fix: "停止中.., -> "停止中..",
raw = raw.replace(
    b'"\\xe5\\x81\\x9c\\xe6\\xad\\xa2\\xe4\\xb8\\xad..,',
    b'"'
)

# Let me try a simpler approach - just fix the specific byte sequences
fixes = [
    (b'"\\xe5\\x81\\x9c\\xe6\\xad\\xa2\\xe4\\xb8\\xad.., "#ffaa00")',
     b'"\\xe5\\x81\\x9c\\xe6\\xad\\xa2\\xe4\\xb8\\xad..", "#ffaa00")'),
]

# Actually the bytes are already decoded. Let me look at the raw bytes more carefully
with open(filepath, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')

# Fix line 496 (0-indexed)
line497 = lines[496]
print("Line 497 hex:", line497.hex())

# The line has: "停止中.., but should be: "停止中..",
# The issue is the closing quote is missing

# Fix: add closing quote before the comma
lines[496] = line497.replace(b'\xe4\xb8\xad.., "#ffaa00")', b'\xe4\xb8\xad..", "#ffaa00")')

# Fix line 500
line501 = lines[500]
print("Line 501 hex:", line501.hex())
lines[500] = line501.replace(b'\xe4\xb8\xad, "#00ff88")', b'\xe4\xb8\xad", "#00ff88")')

# Fix line 504
line505 = lines[504]
print("Line 505 hex:", line505.hex())
lines[504] = line505.replace(b'\xe6\x88\x90?, "#a0a0a0")', b'\xe6\x88\x90", "#a0a0a0")')

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
