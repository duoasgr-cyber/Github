import sys, ast, re, os

base = r'D:\Github\PY'
mw_path = os.path.join(base, 'ui', 'main_window.py')
with open(mw_path, 'r', encoding='utf-8') as f:
    mw = f.read()

# AST-based method extraction
tree = ast.parse(mw)
methods = set()
assigned_attrs = set()

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        methods.add(node.name)
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            assigned_attrs.add(node.attr)

print("=" * 60)
print("2. METHOD CHECK")
print("=" * 60)

# Check signal connections
print("\n  Signal connection targets:")
for line in mw.split('\n'):
    m = re.search(r'\.connect\(self\.([a-zA-Z_]+)\)', line)
    if m:
        method = m.group(1)
        exists = method in methods
        status = "OK" if exists else "MISSING!"
        if not exists:
            print("    %-30s %s" % (method, status))
        else:
            pass  # only print issues

# Check all methods referenced in connect() calls
print("\n  All .connect(self.xxx) targets:")
for line in mw.split('\n'):
    for m in re.finditer(r'\.connect\(self\.([a-zA-Z_]+)\)', line):
        method = m.group(1)
        exists = method in methods
        print("    %-30s %s" % (method, "OK" if exists else "MISSING!"))

print("\n  Methods defined in MainWindow:")
for m in sorted(methods):
    if m.startswith('_') or m in ('keyPressEvent', 'closeEvent', 'resizeEvent'):
        print("    %s" % m)

# Check that sidebar_widget exports what main_window expects
print("\n" + "=" * 60)
print("3. SIDEBAR WIDGET INTERFACE CHECK")
print("=" * 60)
sw_path = os.path.join(base, 'ui', 'components', 'sidebar_widget.py')
with open(sw_path, 'r', encoding='utf-8') as f:
    sw = f.read()

sw_tree = ast.parse(sw)
sw_methods = set()
sw_props = set()
for node in ast.walk(sw_tree):
    if isinstance(node, ast.FunctionDef):
        sw_methods.add(node.name)
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == 'property':
                sw_props.add(node.name)

# Check what main_window accesses on sidebar
for m in re.finditer(r'self\._sidebar\.([a-zA-Z_]+)', mw):
    attr = m.group(1)
    exists = attr in sw_methods or attr in sw_props
    if not exists:
        # Check if it's a signal
        if attr in ('workflow_changed', 'manage_requested', 'device_selected', 
                     'rename_requested', 'step_clicked', 'step_order_changed',
                     'device_bind', 'workflow_switcher', 'step_preview'):
            print("  sidebar.%-25s signal/property" % attr)
        else:
            print("  sidebar.%-25s MISSING!" % attr)

# Check sidebar signals
sidebar_signals = re.findall(r'pyqtSignal\(\)', sw) + re.findall(r'pyqtSignal\(([^)]+)\)', sw)
print("\n  Sidebar signals defined: %d" % len(re.findall(r'pyqtSignal', sw)))

# Check main_window references to sidebar signals
mw_refs = set()
for m in re.finditer(r'self\._sidebar\.([a-zA-Z_]+)\.connect', mw):
    mw_refs.add(m.group(1))
print("  Sidebar signals used in main_window: %s" % ', '.join(sorted(mw_refs)))

# Check sidebar properties used in main_window
for m in re.finditer(r'self\._sidebar\.([a-zA-Z_]+)(?!\.connect)', mw):
    attr = m.group(1)
    if attr not in ('device_bind', 'workflow_switcher', 'step_preview', 'toggle', 'setFixedWidth', 'is_collapsed'):
        print("  sidebar.%-25s used" % attr)
