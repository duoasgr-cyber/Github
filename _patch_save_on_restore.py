from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()
needle = '        self._init_status_bar()'
idx = lines.index(needle)
insert = ['        self._save_ui_state()']
new_lines = lines[:idx] + insert + lines[idx:]
p.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'inserted before line {idx+1}')
