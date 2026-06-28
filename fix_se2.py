import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\components\step_editor.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

fixes = {
    70: '    "text": "\u6587\u672c",',
    71: '    "var_name": "\u53d8\u91cf\u540d",',
    72: '    "var_type": "\u53d8\u91cf\u7c7b\u578b",',
    73: '    "var_value": "\u53d8\u91cf\u503c",',
    74: '    "adb_cmd": "ADB\u547d\u4ee4",',
    75: '    "assign_variable": "\u7ed3\u679c\u5b58\u5165\u53d8\u91cf",',
}

changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        lines[idx] = replacement
        changed += 1

print("Changed " + str(changed) + " lines")

new_content = '\n'.join(lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Saved")
