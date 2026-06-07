import sys
with open(r'D:\Github\PY\ui\main_window.py', 'rb') as f:
    raw = f.read()
lines = raw.split(b'\n')
broken = []
for i, line in enumerate(lines):
    qc = line.count(b'"')
    if qc % 2 != 0:
        broken.append((i, line[:80]))
        print("Line %d (%d quotes): %s" % (i+1, qc, line[:80]))
print("Total broken: %d" % len(broken))
