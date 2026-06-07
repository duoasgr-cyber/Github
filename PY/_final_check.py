import sys, py_compile

files = [
    r'D:\Github\PY\ui\main_window.py',
    r'D:\Github\PY\ui\components\sidebar_widget.py',
    r'D:\Github\PY\ui\components\step_list_widget.py',
    r'D:\Github\PY\ui\components\float_widget.py',
    r'D:\Github\PY\ui\components\screenshot_picker.py',
    r'D:\Github\PY\ui\components\empty_state_widget.py',
    r'D:\Github\PY\ui\panels\workflow_panel.py',
    r'D:\Github\PY\ui\panels\log_panel.py',
    r'D:\Github\PY\ui\panels\status_panel.py',
    r'D:\Github\PY\ui\panels\config_panel.py',
    r'D:\Github\PY\ui\panels\device_panel.py',
    r'D:\Github\PY\ui\panels\test_panel.py',
]
all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print("OK: %s" % f.split("\\")[-1])
    except py_compile.PyCompileError as e:
        print("ERROR: %s: %s" % (f.split("\\")[-1], e))
        all_ok = False

if all_ok:
    print("\nAll files pass syntax check!")
else:
    print("\nSome files have errors!")

# Check garbled chars in main_window
import re
with open(r'D:\Github\PY\ui\main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()
garbled = re.findall(r'[\ue000-\uf8ff]', content)
print("Garbled chars in main_window.py: %d" % len(garbled))
