import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\panels\workflow_panel.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Remaining garbled lines (0-indexed)
fixes = {
    23: '    ("tap", "\u70b9\u51fb", {"type": "tap", "x": 0, "y": 0, "comment": "", "wait_after": 0}),',
    24: '    ("long_press", "\u957f\u6309", {"type": "long_press", "x": 0, "y": 0, "duration": 1000, "comment": "", "wait_after": 0}),',
    25: '    ("swipe", "\u6ed1\u52a8", {"type": "swipe", "x1": 0, "y1": 0, "x2": 0, "y2": 0, "duration": 300, "comment": ""}),',
    26: '    ("keyevent", "\u6309\u952e", {"type": "keyevent", "key": "4", "comment": ""}),',
    27: '    ("wait", "\u7b49\u5f85", {"type": "wait", "seconds": 1, "comment": ""}),',
    28: '    ("wifi", "WiFi\u63a7\u5236", {"type": "wifi", "action": "enable", "comment": "", "wait_after": 0}),',
    32: '    ("pull_file", "\u62c9\u53d6\u6587\u4ef6", {"type": "pull_file", "remote": "", "local": "", "comment": ""}),',
    33: '    ("delete_file", "\u5220\u9664\u6587\u4ef6", {"type": "delete_file", "path": "", "comment": ""}),',
    34: '    ("check_image", "\u56fe\u50cf\u5339\u914d", {"type": "check_image", "template": "", "threshold": 0.85, "comment": ""}),',
    35: '    ("ocr_region", "OCR\u8bc6\u522b", {"type": "ocr_region", "region": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "comment": ""}),',
    36: '    ("tap_point", "\u7cbe\u786e\u70b9\u51fb", {"type": "tap_point", "x": 0, "y": 0, "comment": "", "wait_after": 0}),',
    38: '    ("condition", "\u6761\u4ef6\u5224\u65ad", {"type": "condition", "check": {}, "then_steps": [], "else_steps": [], "comment": ""}),',
    40: '    ("input_text", "\u8f93\u5165\u6587\u672c", {"type": "input_text", "enabled": True, "display_name": "", "text": "", "comment": ""}),',
    41: '    ("variable", "\u53d8\u91cf\u5904\u7406", {"type": "variable", "enabled": True, "display_name": "", "var_name": "", "var_type": "string", "comment": ""}),',
    42: '    ("adb_command", "ADB\u547d\u4ee4", {"type": "adb_command", "enabled": True, "display_name": "", "adb_cmd": "", "assign_variable": "", "comment": ""}),',
    43: '    ("expression", "\u8868\u8fbe\u5f0f", {"type": "expression", "expression": "", "assign_variable": "", "comment": ""}),',
    71: '        btn_cancel = QPushButton("\u53d6\u6d88")',
    120: '        btn_new_wf = QPushButton("\u65b0\u5efa")',
    125: '        btn_rename_wf = QPushButton("\u91cd\u547d\u540d")',
    130: '        btn_delete_wf = QPushButton("\u5220\u9664")',
    158: '        btn_up = QPushButton("\u4e0a\u79fb")',
    163: '        btn_down = QPushButton("\u4e0b\u79fb")',
    167: '        btn_snippet = QPushButton("\u4ee3\u7801\u7247\u6bb5")',
    433: '            self, "\u91cd\u547d\u540d\u5de5\u4f5c\u6d41", "\u65b0\u540d\u79f0", text=old_name',
}

changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        lines[idx] = replacement
        changed += 1
        print("Fixed L" + str(idx+1))

print("\nTotal lines changed: " + str(changed))

new_content = '\n'.join(lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("File written successfully.")
