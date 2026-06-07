import os

base = r'D:\Github\PY'
bom_files = [
    os.path.join(base, 'ui', 'components', 'sidebar_widget.py'),
    os.path.join(base, 'ui', 'components', 'float_widget.py'),
    os.path.join(base, 'ui', 'components', 'empty_state_widget.py'),
    os.path.join(base, 'ui', 'panels', 'log_panel.py'),
    os.path.join(base, 'ui', 'panels', 'device_panel.py'),
    os.path.join(base, 'ui', 'main_window.py'),
    os.path.join(base, 'ui', 'components', 'step_list_widget.py'),
]

for path in bom_files:
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:3] == b'\xef\xbb\xbf':
        with open(path, 'wb') as f:
            f.write(raw[3:])
        print("BOM removed: %s" % os.path.basename(path))
    else:
        print("No BOM: %s" % os.path.basename(path))
