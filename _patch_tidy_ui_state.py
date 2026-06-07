from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()

targets = [
    '        self._save_task_snapshot()',
    '        self._save_ui_state()',
]

# Remove only exact adjacent pair occurrence(s)
out = []
i = 0
while i < len(lines):
    if i + 1 < len(lines) and lines[i] == targets[0] and lines[i + 1] == targets[1]:
        out.append(lines[i])  # keep task snapshot save
        i += 2
    else:
        out.append(lines[i])
        i += 1

p.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('removed redundant _save_ui_state() after _save_task_snapshot()')
