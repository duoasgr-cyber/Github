from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
text = p.read_text(encoding='utf-8')
needle = '        self._save_task_snapshot()\n\n    def _setup_exception_handler(self):'
repl = '        self._save_task_snapshot()\n        self._save_ui_state()\n\n    def _setup_exception_handler(self):'
if needle not in text:
    raise SystemExit('target block not found')
p.write_text(text.replace(needle, repl, 1), encoding='utf-8')
print('added _save_ui_state() after workflow_saved')
