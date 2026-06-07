from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()
needle = '        self._init_status_bar()'
idx = lines.index(needle)

insert = [
    '',
    '        # Restore persisted UI state (sidebar & splitters) if available',
    '        try:',
    '            if os.path.exists(ui_state_path):',
    '                with open(ui_state_path, "r", encoding="utf-8") as f:',
    '                    ui_state = __import__("json").load(f)',
    '                self._center_splitter.setSizes(ui_state.get("center_splitter_sizes", self._center_splitter.sizes()))',
    '                self._main_splitter.setSizes(ui_state.get("main_splitter_sizes", self._main_splitter.sizes()))',
    '        except Exception:',
    '            pass',
    '',
    '    def _save_ui_state(self):',
    '        try:',
    '            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
    '            ui_state_path = os.path.join(base_dir, "config", "ui_state.json")',
    '            data = {}',
    '            if os.path.exists(ui_state_path):',
    '                with open(ui_state_path, "r", encoding="utf-8") as f:',
    '                    data = __import__("json").load(f)',
    '            data.update({',
    '                "sidebar_collapsed": bool(getattr(self._sidebar, "is_collapsed", lambda: False)()),',
    '                "center_splitter_sizes": self._center_splitter.sizes(),',
    '                "main_splitter_sizes": self._main_splitter.sizes(),',
    '            })',
    '            os.makedirs(os.path.dirname(ui_state_path), exist_ok=True)',
    '            tmp = ui_state_path + ".tmp"',
    '            with open(tmp, "w", encoding="utf-8") as f:',
    '                __import__("json").dump(data, f, ensure_ascii=False, indent=2)',
    '            os.replace(tmp, ui_state_path)',
    '        except Exception:',
    '            pass',
]

new_lines = lines[:idx] + insert + lines[idx:]
p.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'inserted after line {idx}')
