from pathlib import Path
p = Path(r'D:\Github\PY\ui\panels\workflow_panel.py')
text = p.read_text(encoding='utf-8')
needle = '        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture, parent=self)\n        right_layout.addWidget(self._screenshot_picker, stretch=2)'
repl = '        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture, parent=self)\n        self._screenshot_picker.setMinimumWidth(240)\n        right_layout.addWidget(self._screenshot_picker, stretch=2)'
if needle not in text:
    raise SystemExit('needle not found')
p.write_text(text.replace(needle, repl, 1), encoding='utf-8')
print('patched workflow_panel.py')
