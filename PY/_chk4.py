import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check lines 390-410
for i in range(390, 415):
    if i < len(lines):
        print("%d: %s" % (i+1, repr(lines[i].rstrip())))
