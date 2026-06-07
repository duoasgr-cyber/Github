from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
text = p.read_text(encoding='utf-8')
needle = (
    "        center_splitter.setChildrenCollapsible(False)\n"
    "        self._center_splitter = center_splitter\n"
    "\n"
    "        self._log_panel = LogPanel()"
)
repl = (
    "        center_splitter.setChildrenCollapsible(False)\n"
    "        self._center_splitter = center_splitter\n"
    "\n"
    "        # Auto-hide screenshot when current step has no coordinates\n"
    "        if hasattr(self, '_update_screenshot_empty_state'):\n"
    "            self._update_screenshot_empty_state()\n"
    "\n"
    "        self._log_panel = LogPanel()"
)
if needle not in text:
    raise SystemExit('anchor not found')
p.write_text(text.replace(needle, repl, 1), encoding='utf-8')
print('inserted empty state update into _init_ui')
