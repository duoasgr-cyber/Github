from pathlib import Path
p = Path(r'D:\Github\PY\ui\resources\style.qss')
lines = p.read_text(encoding='utf-8').splitlines()
start = None
end = None
for i, line in enumerate(lines):
    if line.strip() == 'QPushButton {' and start is None:
        start = i
    if start is not None and line.strip() == '}':
        end = i
        break
if start is None or end is None:
    raise SystemExit(f'QPushButton block not found: start={start} end={end}')

replacement = [
    'QPushButton {',
    '    background-color: #21262d;',
    '    border: 1px solid #30363d;',
    '    border-radius: 6px;',
    '    padding: 6px 14px;',
    '    color: #e6edf3;',
    '    font-size: 14px;',
    '    min-width: 72px;',
    '    letter-spacing: 0.2px;',
    '}',
]

new_lines = lines[:start] + replacement + lines[end+1:]
p.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'patched QPushButton style lines {start+1}-{end+1}')
