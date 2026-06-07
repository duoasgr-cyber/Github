from pathlib import Path
p = Path(r'D:\Github\PY\ui\main_window.py')
lines = p.read_text(encoding='utf-8').splitlines()

start = None
end = None
for i, line in enumerate(lines):
    if '        editor_splitter = QSplitter(Qt.Horizontal)' in line and start is None:
        start = i
    if '        self._main_splitter = main_splitter' in line and start is not None:
        end = i
        break

if start is None or end is None:
    raise SystemExit(f'anchors not found: start={start} end={end}')

replacement = [
    "        # Center split: stacked editors (left) + screenshot picker (right)",
    "        center_splitter = QSplitter(Qt.Horizontal)",
    "        center_splitter.addWidget(self._stacked)",
    "        center_splitter.addWidget(self._screenshot_picker)",
    "        center_splitter.setStretchFactor(0, 3)",
    "        center_splitter.setStretchFactor(1, 2)",
    "        center_splitter.setChildrenCollapsible(False)",
    "        self._center_splitter = center_splitter",
    "",
    "        self._log_panel = LogPanel()",
    "",
    "        # Main split: center area (top) + log panel (bottom)",
    "        main_splitter = QSplitter(Qt.Vertical)",
    "        main_splitter.addWidget(center_splitter)",
    "        main_splitter.addWidget(self._log_panel)",
    "        main_splitter.setStretchFactor(0, 5)",
    "        main_splitter.setStretchFactor(1, 1)",
    "        main_splitter.setSizes([620, 180])",
    "        main_splitter.setChildrenCollapsible(False)",
    "        self._main_splitter = main_splitter",
]

new_lines = lines[:start] + replacement + lines[end+1:]
p.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'patched lines {start+1}-{end+1} -> {start+1}-{start+len(replacement)}')
