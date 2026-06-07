import sys, ast, re, os

base = r'D:\Github\PY'
wp_path = os.path.join(base, 'ui', 'panels', 'workflow_panel.py')
with open(wp_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Print lines 170-220 to understand the _setup_ui and _connect_signals
for i in range(165, 220):
    if i < len(lines):
        print("%3d: %s" % (i+1, lines[i].rstrip()))
