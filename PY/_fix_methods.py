import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the broken section from _on_stop_monitoring to set_connection_status
# First, let me find the boundaries

# Find "def _on_stop_monitoring" to "def set_connection_status"
import re

# Replace the entire broken section
old_section_start = '    def _on_stop_monitoring(self):'
old_section_end = '    def set_connection_status(self, connected: bool):'

start_idx = content.find(old_section_start)
end_idx = content.find(old_section_end)

if start_idx >= 0 and end_idx >= 0:
    # Get everything before the broken section
    before = content[:start_idx]
    # Get everything after (including set_connection_status)
    after = content[end_idx:]
    
    # Reconstruct the methods properly
    new_section = '''    def _on_stop_monitoring(self):
        self._step_executor.stop()
        self._panels["status_monitor"].update_status("\u505c\u6b62\u4e2d..", "#ffaa00")
        self._floating_widget.update_status("\u505c\u6b62\u4e2d..", "#ffaa00")

    def _on_pause_monitoring(self):
        self._step_executor.pause()
        self._panels["status_monitor"].update_status("\u5df2\u6682\u505c", "#ffaa00")
        self._floating_widget.update_status("\u5df2\u6682\u505c", "#ffaa00")

    def _on_resume_monitoring(self):
        self._step_executor.resume()
        self._panels["status_monitor"].update_status("\u8fd0\u884c\u4e2d", "#00ff88")
        self._floating_widget.update_status("\u8fd0\u884c\u4e2d", "#00ff88")

    def _on_workflow_worker_finished(self):
        self._panels["status_monitor"].update_status("\u5df2\u5b8c\u6210", "#a0a0a0")
        self._floating_widget.update_status("\u5df2\u5b8c\u6210", "#a0a0a0")

    def set_device_status(self, serial: str):
        if serial:
            self._device_label.setText(f"\u8bbe\u5907: {serial}")
        else:
            self._device_label.setText("\u8bbe\u5907: \u672a\u8fde\u63a5")

    '''
    
    content = before + new_section + after
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Section replaced")
else:
    print("Could not find section boundaries")
    print("Start: %d, End: %d" % (start_idx, end_idx))

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))
