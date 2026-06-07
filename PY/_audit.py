import sys, ast, re, os

base = r'D:\Github\PY'
files = {
    'main_window': os.path.join(base, 'ui', 'main_window.py'),
    'sidebar_widget': os.path.join(base, 'ui', 'components', 'sidebar_widget.py'),
    'step_list_widget': os.path.join(base, 'ui', 'components', 'step_list_widget.py'),
    'float_widget': os.path.join(base, 'ui', 'components', 'float_widget.py'),
    'empty_state_widget': os.path.join(base, 'ui', 'components', 'empty_state_widget.py'),
    'screenshot_picker': os.path.join(base, 'ui', 'components', 'screenshot_picker.py'),
    'workflow_panel': os.path.join(base, 'ui', 'panels', 'workflow_panel.py'),
    'log_panel': os.path.join(base, 'ui', 'panels', 'log_panel.py'),
    'status_panel': os.path.join(base, 'ui', 'panels', 'status_panel.py'),
    'config_panel': os.path.join(base, 'ui', 'panels', 'config_panel.py'),
    'device_panel': os.path.join(base, 'ui', 'panels', 'device_panel.py'),
    'test_panel': os.path.join(base, 'ui', 'panels', 'test_panel.py'),
    'style.qss': os.path.join(base, 'ui', 'resources', 'style.qss'),
}

print("=" * 60)
print("1. SYNTAX CHECK")
print("=" * 60)
all_ok = True
for name, path in files.items():
    if path.endswith('.qss'):
        continue
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        garbled = len(re.findall(r'[\ue000-\uf8ff]', content))
        status = "OK" if garbled == 0 else "OK (garbled=%d)" % garbled
        print("  %-20s %s" % (name, status))
    except SyntaxError as e:
        print("  %-20s SYNTAX ERROR line %d: %s" % (name, e.lineno, e.msg))
        all_ok = False
    except Exception as e:
        print("  %-20s ERROR: %s" % (name, e))
        all_ok = False

if all_ok:
    print("\n  All syntax checks passed!")
else:
    print("\n  Some files have errors!")
