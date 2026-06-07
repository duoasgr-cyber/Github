from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()

needle = '        self._save_task_snapshot()'
idx = lines.index(needle)
insert = ['        self._save_ui_state()']
new_lines = lines[:idx+1] + insert + lines[idx+1:]
p.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'inserted after line {idx+1}')
