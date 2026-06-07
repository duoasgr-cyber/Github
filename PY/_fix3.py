import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the misplaced lines: remove lines 397 and 399 from _connect_signals
# and put them back in _setup_exception_handler

# Remove the two misplaced lines from _connect_signals
old_connect = '''        tray_menu = self._tray_icon.contextMenu()
            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)
        actions[0].triggered.connect(self._on_tray_show)
                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)
        actions[3].triggered.connect(self._on_tray_quit)'''

new_connect = '''        tray_menu = self._tray_icon.contextMenu()
        actions = tray_menu.actions()
        actions[0].triggered.connect(self._on_tray_show)
        actions[1].triggered.connect(self._on_tray_hide)
        actions[3].triggered.connect(self._on_tray_quit)'''

content = content.replace(old_connect, new_connect)

# Now fix the _setup_exception_handler method - check if it's broken
# Find it and replace
old_handler = '''    def _setup_exception_handler(self):
        original_excepthook = sys.excepthook

        def exception_hook(exc_type, exc_value, exc_tb):
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))'''

new_handler = '''    def _setup_exception_handler(self):
        original_excepthook = sys.excepthook

        def exception_hook(exc_type, exc_value, exc_tb):
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)
            try:
                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)
            except Exception:
                pass'''

content = content.replace(old_handler, new_handler)

# Also remove duplicate "actions = tray_menu.actions()" if it exists
# and the duplicate action lines
content = content.replace(
    '''        tray_menu = self._tray_icon.contextMenu()
        actions = tray_menu.actions()
        actions[0].triggered.connect(self._on_tray_show)
        actions[1].triggered.connect(self._on_tray_hide)
        actions[3].triggered.connect(self._on_tray_quit)
        actions = tray_menu.actions()
        actions[0].triggered.connect(self._on_tray_show)
        actions[1].triggered.connect(self._on_tray_hide)
        actions[3].triggered.connect(self._on_tray_quit)''',
    '''        tray_menu = self._tray_icon.contextMenu()
        actions = tray_menu.actions()
        actions[0].triggered.connect(self._on_tray_show)
        actions[1].triggered.connect(self._on_tray_hide)
        actions[3].triggered.connect(self._on_tray_quit)'''
)

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
