import sys
with open(r'D:\Github\PY\ui\main_window.py', 'rb') as f:
    raw = f.read()
lines = raw.split(b'\n')
for i in range(50, 60):
    line = lines[i]
    count = line.count(b'"')
    tail = line[-20:]
    print("Line %d: quotes=%d tail_hex=%s" % (i+1, count, tail.hex()))
