from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
text = p.read_text(encoding='utf-8')
needle = '        self._save_ui_state()\n        self._init_status_bar()'
repl = '        self._init_status_bar()'
if needle not in text:
    raise SystemExit('target pair not found')
p.write_text(text.replace(needle, repl, 1), encoding='utf-8')
print('repaired init_status_bar placement')
