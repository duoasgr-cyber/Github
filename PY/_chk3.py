import sys
with open(r'D:\Github\PY\ui\main_window.py', 'rb') as f:
    raw = f.read()
lines = raw.split(b'\n')
# Check lines around 396
for i in range(392, 405):
    print("Line %d: %s" % (i+1, lines[i]))
