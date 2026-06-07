import sys

filepath = r'D:\Github\PY\ui\components\step_list_widget.py'
with open(filepath, 'r', encoding='utf-8-sig') as f:
    content = f.read()

old_refresh = """    def _refresh_display(self):
        self.blockSignals(True)
        self.clear()
        if not self._raw_steps:
            self.blockSignals(False)
            return"""

new_refresh = """    def _refresh_display(self):
        self.blockSignals(True)
        self.clear()
        if not self._raw_steps:
            empty = QListWidgetItem("\\u200b  \\u6682\\u65e0\\u6b65\\u9aa4\\u2014\\u2014\\u70b9\\u51fb\\u201c\\u6dfb\\u52a0\\u6b65\\u9aa4\\u201d\\u5f00\\u59cb\\u7f16\\u8f91")
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            empty.setForeground(QColor("#484f58"))
            f = empty.font()
            f.setItalic(True)
            empty.setFont(f)
            self.addItem(empty)
            self.blockSignals(False)
            return"""

content = content.replace(old_refresh, new_refresh)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

# Remove BOM if present
with open(filepath, 'rb') as f:
    raw = f.read()
if raw[:3] == b'\xef\xbb\xbf':
    raw = raw[3:]
    with open(filepath, 'wb') as f:
        f.write(raw)

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content2 = f.read()
try:
    ast.parse(content2)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content2.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))
