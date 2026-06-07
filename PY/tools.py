from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()
for i in range(427,445):
    print(f'{i+1}: {lines[i]}')
