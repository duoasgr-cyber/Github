import sys
with open(r'D:\Github\PY\ui\main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(215, 225):
    print("%d: %s" % (i+1, repr(lines[i].rstrip())))
