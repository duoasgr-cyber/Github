import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the garbled NAV_ITEMS with proper Chinese
# Find the NAV_ITEMS block and replace it
old_nav = '''    NAV_ITEMS = [
        ("\u5b95\u30e4\u7d94\u5a34\u4f3a\u7d2a\u6d88?", "workflow_editor"),
        ("\u91d2\u9f58", "configuration"),
        ("\u8bf9\u30e2\u7ba1\u30f3", "device_management"),
        ("\u93c8\u2229\u76d1\u63a5", "status_monitor"),
        ("\u5b2c\u8bd8", "test"),
    ]'''

# Instead, let me use regex to find and replace the NAV_ITEMS block
import re

# Find lines between NAV_ITEMS = [ and ]
pattern = r'(    NAV_ITEMS = \[).*?(\n    \])'
replacement = '''    NAV_ITEMS = [
        ("\u5de5\u4f5c\u6d41\u7f16\u8f91", "workflow_editor"),
        ("\u914d\u7f6e", "configuration"),
        ("\u8bbe\u5907\u7ba1\u7406", "device_management"),
        ("\u8fd0\u884c\u76d1\u63a7", "status_monitor"),
        ("\u6d4b\u8bd5", "test"),
    ]'''

# Use bytes to be safe
with open(filepath, 'rb') as f:
    raw = f.read()

# Find NAV_ITEMS = [ ... ] pattern in raw bytes
start_marker = b'NAV_ITEMS = ['
end_marker = b']'

start_idx = raw.find(start_marker)
if start_idx < 0:
    print("NAV_ITEMS not found")
    sys.exit(1)

# Find the matching ]
bracket_count = 0
i = start_idx + len(start_marker) - 1  # point to the [
end_idx = -1
while i < len(raw):
    if raw[i] == ord('['):
        bracket_count += 1
    elif raw[i] == ord(']'):
        bracket_count -= 1
        if bracket_count == 0:
            end_idx = i + 1
            break
    i += 1

if end_idx < 0:
    print("Could not find matching ]")
    sys.exit(1)

print("Found NAV_ITEMS at bytes %d-%d" % (start_idx, end_idx))
print("Original: %s" % raw[start_idx:end_idx])

new_nav = b'''NAV_ITEMS = [
        ("\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xe7\xbc\x96\xe8\xbe\x91", "workflow_editor"),
        ("\xe9\x85\x8d\xe7\xbd\xae", "configuration"),
        ("\xe8\xae\xbe\xe5\xa4\x87\xe7\xae\xa1\xe7\x90\x86", "device_management"),
        ("\xe8\xbf\x90\xe8\xa1\x8c\xe7\x9b\x91\xe6\x8e\xa7", "status_monitor"),
        ("\xe6\xb5\x8b\xe8\xaf\x95", "test"),
    ]'''

raw = raw[:start_idx] + new_nav + raw[end_idx:]

with open(filepath, 'wb') as f:
    f.write(raw)

print("NAV_ITEMS fixed")

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
