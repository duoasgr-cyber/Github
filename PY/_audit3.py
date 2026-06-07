import sys, ast, re, os

base = r'D:\Github\PY'

print("=" * 60)
print("2. SIGNAL / METHOD REFERENCE CHECK")
print("=" * 60)

# Read main_window.py and extract all self._xxx references
mw_path = os.path.join(base, 'ui', 'main_window.py')
with open(mw_path, 'r', encoding='utf-8') as f:
    mw = f.read()

# Check that all referenced attributes exist
# Find all self._xxx assignments
assigned = set()
for m in re.finditer(r'self\.(_[a-zA-Z_]+)\s*=', mw):
    assigned.add(m.group(1))

# Find all self._xxx usages (not assignments)
used = set()
for m in re.finditer(r'self\.(_[a-zA-Z_]+)(?!\s*=)', mw):
    used.add(m.group(1))

# Filter out method calls (self._xxx()) vs attributes
methods_in_mw = set()
for m in re.finditer(r'def\s+(_[a-zA-Z_]+)\s*\(', mw):
    methods_in_mw.add(m.group(1))

# Check: used attributes that are not assigned and not methods
missing = []
for u in sorted(used):
    if u.startswith('__'):
        continue
    if u in assigned:
        continue
    if u in methods_in_mw:
        continue
    # Check if it's a property access on sidebar
    if u in ('_device_bind', '_workflow_switcher', '_step_preview'):
        if 'self._sidebar.' + u.lstrip('_') in mw or 'self._sidebar.' + u in mw:
            continue
        if 'self._device_bind = self._sidebar.device_bind' in mw:
            continue
    missing.append(u)

if missing:
    print("  Potentially undefined attributes:")
    for m in missing:
        # Check if it's used as self._xxx.something (property)
        count = len(re.findall(r'self\.' + re.escape(m) + r'[\.\[]', mw))
        assign_count = len(re.findall(r'self\.' + re.escape(m) + r'\s*=', mw))
        print("    %-30s used=%d assigned=%d" % (m, count + len(re.findall(r'self\.' + re.escape(m) + r'(?!\s*=)(?!\.)', mw)), assign_count))
else:
    print("  All attributes properly assigned before use")

# Check signal connections reference existing methods
print("\n  Checking signal connections...")
connect_lines = [l.strip() for l in mw.split('\n') if '.connect(' in l]
issues = []
for line in connect_lines:
    m = re.search(r'\.connect\(self\.(_[a-zA-Z_]+)\)', line)
    if m:
        method = m.group(1)
        if method not in methods_in_mw:
            issues.append("  Signal connects to undefined method: %s" % method)
            issues.append("    in: %s" % line[:80])

if issues:
    for i in issues:
        print(i)
else:
    print("  All signal connections reference valid methods")

# Check imports
print("\n  Checking imports...")
import_lines = [l.strip() for l in mw.split('\n') if l.strip().startswith('from ') or l.strip().startswith('import ')]
for imp in import_lines:
    print("    %s" % imp)
