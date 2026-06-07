from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
text = p.read_text(encoding='utf-8')
needle = '            self._main_splitter.setSizes([620, 180])\n    def _apply_active_task(self):'
repl = '            self._main_splitter.setSizes([620, 180])\n        self._save_ui_state()\n\n    def _apply_active_task(self):'
if needle not in text:
    raise SystemExit('toggle block not found')
p.write_text(text.replace(needle, repl, 1), encoding='utf-8')
print('added _save_ui_state() after _toggle_log_panel')
