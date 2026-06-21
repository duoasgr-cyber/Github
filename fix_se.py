import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\components\step_editor.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

fixes = {
    42: '    "enabled": "\u542f\u7528",',
    57: '    "save_path": "\u4fdd\u5b58\u8def\u5f84",',
    58: '    "remote": "\u8fdc\u7a0b\u8def\u5f84",',
    59: '    "local": "\u672c\u5730\u8def\u5f84",',
    60: '    "path": "\u6587\u4ef6\u8def\u5f84",',
    61: '    "template": "\u6a21\u677f\u8def\u5f84",',
    62: '    "threshold": "\u9608\u503c",',
    64: '    "workflow": "\u5de5\u4f5c\u6d41",',
    66: '    "then_steps": "\u6ee1\u8db3\u6b65\u9aa4",',
    67: '    "else_steps": "\u4e0d\u6ee1\u8db3\u6b65\u9aa4",',
    68: '    "max_count": "\u6700\u5927\u6b21\u6570",',
    69: '    "steps": "\u6b65\u9aa4",',
    112: '        self._placeholder = QLabel("\u9009\u62e9\u6b65\u9aa4\u4ee5\u7f16\u8f91")',
}

changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        lines[idx] = replacement
        changed += 1

print("Changed " + str(changed) + " lines in step_editor.py")

new_content = '\n'.join(lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Saved")
