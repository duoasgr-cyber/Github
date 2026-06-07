import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find all lines with garbled chars
lines = content.split('\n')
for i, line in enumerate(lines):
    has_garbled = False
    for c in line:
        if '\ue000' <= c <= '\uf8ff':
            has_garbled = True
            break
    if has_garbled:
        # Write the line number and raw bytes
        with open(r'D:\Github\PY\_garbled_lines.txt', 'a', encoding='utf-8') as gf:
            gf.write("Line %d: %s\n" % (i+1, line.strip()))

# Now fix them by replacing the garbled strings directly
# The window title pattern
content = content.replace('\u6d9a\u590e\u879c', '\u4e09\u89d2\u6d32')
content = content.replace('\u52dd\u514b\u57c8', '\u81ea\u52a8')
content = content.replace('\u5be6\u0452', '\u62a2\u8d2d\u5de5\u5177')

# Fix connection label
content = content.replace('\u8fde\u63a5: \u65ad\u5f00', '\u8fde\u63a5: \u65ad\u5f00')

# Check what's left
lines = content.split('\n')
garbled_lines = []
for i, line in enumerate(lines):
    for c in line:
        if '\ue000' <= c <= '\uf8ff':
            garbled_lines.append((i+1, line.strip()[:80]))
            break

if garbled_lines:
    with open(r'D:\Github\PY\_garbled_lines.txt', 'a', encoding='utf-8') as gf:
        gf.write("\nRemaining:\n")
        for ln, text in garbled_lines:
            gf.write("  Line %d: %s\n" % (ln, text))
    print("Remaining garbled lines: %d" % len(garbled_lines))
else:
    print("All clean!")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
