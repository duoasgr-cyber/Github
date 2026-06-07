import sys
with open(r'D:\Github\PY\ui\main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(510, 520):
    if i < len(lines):
        print("%d: %s" % (i+1, repr(lines[i].rstrip())))
