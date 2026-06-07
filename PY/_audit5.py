import sys, ast, re, os

base = r'D:\Github\PY'

print("=" * 60)
print("4. SIDEBAR WIDGET INTERNAL CHECK")
print("=" * 60)

sw_path = os.path.join(base, 'ui', 'components', 'sidebar_widget.py')
with open(sw_path, 'r', encoding='utf-8') as f:
    sw = f.read()

sw_tree = ast.parse(sw)
sw_methods = set()
for node in ast.walk(sw_tree):
    if isinstance(node, ast.FunctionDef):
        sw_methods.add(node.name)

# Check internal method calls
for line in sw.split('\n'):
    m = re.search(r'self\.([a-zA-Z_]+)\(', line)
    if m:
        method = m.group(1)
        if method.startswith('_') and method not in sw_methods and method != '__init__':
            if method not in ('_device_bind', '_workflow_switcher', '_step_preview'):
                print("  Potentially missing internal method: %s" % method)

# Check that sidebar connects to child signals properly
print("\n  Sidebar _connect_signals:")
connect_section = False
for line in sw.split('\n'):
    if '_connect_signals' in line:
        connect_section = True
    if connect_section:
        if '.connect(' in line:
            print("    %s" % line.strip())
        if line.strip() and not line.strip().startswith('#') and 'def ' in line and '_connect_signals' not in line:
            break

print("\n" + "=" * 60)
print("5. STEP LIST WIDGET CHECK")
print("=" * 60)

sl_path = os.path.join(base, 'ui', 'components', 'step_list_widget.py')
with open(sl_path, 'r', encoding='utf-8') as f:
    sl = f.read()

sl_tree = ast.parse(sl)
sl_methods = set()
for node in ast.walk(sl_tree):
    if isinstance(node, ast.FunctionDef):
        sl_methods.add(node.name)

# Check signals defined
signals = re.findall(r'(\w+)\s*=\s*pyqtSignal', sl)
print("  Signals: %s" % ', '.join(signals))

# Check context menu handler references
for line in sl.split('\n'):
    if 'self.step_' in line and 'emit' in line:
        print("  Emit: %s" % line.strip())

print("\n" + "=" * 60)
print("6. FLOAT WIDGET CHECK")
print("=" * 60)

fw_path = os.path.join(base, 'ui', 'components', 'float_widget.py')
with open(fw_path, 'r', encoding='utf-8') as f:
    fw = f.read()

fw_tree = ast.parse(fw)
signals = re.findall(r'(\w+)\s*=\s*pyqtSignal', fw)
print("  Signals: %s" % ', '.join(signals))

# Check pause/stop button signals
for line in fw.split('\n'):
    if 'clicked.connect' in line:
        print("  Button: %s" % line.strip())

print("\n" + "=" * 60)
print("7. EMPTY STATE WIDGET CHECK")
print("=" * 60)

es_path = os.path.join(base, 'ui', 'components', 'empty_state_widget.py')
with open(es_path, 'r', encoding='utf-8') as f:
    es = f.read()

es_tree = ast.parse(es)
classes = []
for node in ast.walk(es_tree):
    if isinstance(node, ast.ClassDef):
        classes.append(node.name)
print("  Classes: %s" % ', '.join(classes))

for cls_name in classes:
    for node in ast.walk(es_tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            print("  %s methods: %s" % (cls_name, ', '.join(methods)))
