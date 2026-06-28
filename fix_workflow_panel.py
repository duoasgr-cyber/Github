import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\panels\workflow_panel.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Build replacement map based on contextual analysis
# Each garbled string maps to its correct Chinese based on the UI context
fixes = {
    29: '    ("force_stop", "\u5f3a\u5236\u505c\u6b62", {"type": "force_stop", "package": "", "comment": "", "wait_after": 0}),',
    30: '    ("launch", "\u542f\u52a8\u5e94\u7528", {"type": "launch", "package": "", "comment": "", "wait_after": 0}),',
    31: '    ("screenshot", "\u622a\u56fe", {"type": "screenshot", "save_path": "", "comment": ""}),',
    37: '    ("call_workflow", "\u8c03\u7528\u5de5\u4f5c\u6d41", {"type": "call_workflow", "workflow": "", "comment": ""}),',
    39: '    ("loop", "\u5faa\u73af", {"type": "loop", "max_count": 10, "condition": {}, "steps": [], "comment": ""}),',
    52: '        self.setWindowTitle("\u9009\u62e9\u6b65\u9aa4\u7c7b\u578b")',
    70: '        btn_ok = QPushButton("\u786e\u5b9a")',
    143: '        btn_add = QPushButton("\u6dfb\u52a0\u6b65\u9aa4")',
    148: '        btn_delete = QPushButton("\u5220\u9664\u6b65\u9aa4")',
    153: '        btn_copy = QPushButton("\u590d\u5236\u6b65\u9aa4")',
    309: '            self, "\u5220\u9664\u6b65\u9aa4", "\u786e\u5b9a\u8981\u5220\u9664\u9009\u4e2d\u7684\u6b65\u9aa4\u5417\uff1f",',
    409: '        name, ok = QInputDialog.getText(self, "\u65b0\u5efa\u5de5\u4f5c\u6d41", "\u5de5\u4f5c\u6d41\u540d\u79f0")',
    415: '            QMessageBox.warning(self, "\u63d0\u793a", f"\u5de5\u4f5c\u6d41\'{name}\' \u5df2\u5b58\u5728")',
    442: '            QMessageBox.warning(self, "\u63d0\u793a", f"\u5de5\u4f5c\u6d41\'{new_name}\' \u5df2\u5b58\u5728")',
    457: '            "\u5220\u9664\u5de5\u4f5c\u6d41",',
    458: '            f"\u786e\u5b9a\u8981\u5220\u9664\u5de5\u4f5c\u6d41 \'{self._current_workflow_name}\' \u5417\uff1f",',
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
