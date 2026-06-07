import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix: set_connection_status is nested inside set_device_status
# Replace the broken section
old = '''        def set_connection_status(self, connected: bool):
        self._connection_label.setText("\u8fde\u63a5: \u5df2\u8fde\u63a5" if connected else "\u8fde\u63a5: \u65ad\u5f00")'''

new = '''
    def set_connection_status(self, connected: bool):
        self._connection_label.setText("\u8fde\u63a5: \u5df2\u8fde\u63a5" if connected else "\u8fde\u63a5: \u65ad\u5f00")'''

content = content.replace(old, new)

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
