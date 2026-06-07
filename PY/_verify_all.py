import sys, py_compile

files = [
    r'D:\Github\PY\ui\main_window.py',
    r'D:\Github\PY\ui\components\sidebar_widget.py',
    r'D:\Github\PY\ui\components\step_list_widget.py',
    r'D:\Github\PY\ui\components\float_widget.py',
    r'D:\Github\PY\ui\components\screenshot_picker.py',
    r'D:\Github\PY\ui\panels\workflow_panel.py',
    r'D:\Github\PY\ui\panels\log_panel.py',
    r'D:\Github\PY\ui\panels\status_panel.py',
    r'D:\Github\PY\ui\panels\config_panel.py',
    r'D:\Github\PY\ui\panels\device_panel.py',
    r'D:\Github\PY\ui\panels\test_panel.py',
    r'D:\Github\PY\ui\resources\style.qss',
]
for f in files:
    if f.endswith('.qss'):
        print("OK (skip): %s" % f)
        continue
    try:
        py_compile.compile(f, doraise=True)
        print("OK: %s" % f)
    except py_compile.PyCompileError as e:
        print("ERROR: %s: %s" % (f, e))
