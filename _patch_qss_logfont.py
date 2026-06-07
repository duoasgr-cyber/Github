from pathlib import Path
p = Path(r'D:\Github\PY\ui\resources\style.qss')
lines = p.read_text(encoding='utf-8').splitlines()

def ensure_rule(block_start_keyword, rule_lines):
    for i, line in enumerate(lines):
        if line.strip().startswith(block_start_keyword):
            return lines, False
    # append at end
    return lines + [''] + rule_lines, True

rules = [
    ['QPlainTextEdit {', '    font-family: Consolas, "Microsoft YaHei", monospace;', '    font-size: 12px;', '}', ''],
]

changed_any = False
for rule in rules:
    lines, changed = ensure_rule(rule[0], rule)
    changed_any = changed_any or changed

if changed_any:
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('appended QPlainTextEdit rule')
else:
    print('QPlainTextEdit rule already exists')
