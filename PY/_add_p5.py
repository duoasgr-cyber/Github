import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import for EmptyStateWidget and LoadingOverlay
old_import = 'from ui.components.screenshot_picker import ScreenshotPicker'
new_import = '''from ui.components.screenshot_picker import ScreenshotPicker
from ui.components.empty_state_widget import EmptyStateWidget, LoadingOverlay'''
content = content.replace(old_import, new_import)

# 2. Add empty state overlay for screenshot picker and loading overlay after its creation
old_ss = '        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture)'
new_ss = '''        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture)

        # empty state for screenshot area
        self._ss_empty = EmptyStateWidget(
            icon="\U0001f4f7",
            message="\u6682\u65e0\u622a\u56fe",
            hint="\u9009\u62e9\u5750\u6807\u6b65\u9aa4\u540e\u81ea\u52a8\u622a\u5c4f"
        )
        self._ss_empty.setParent(self._screenshot_picker)
        self._ss_empty.hide()

        # loading overlay
        self._loading_overlay = LoadingOverlay(parent=self)'''
content = content.replace(old_ss, new_ss)

# 3. Add _on_step_selected enhancement: show/hide screenshot empty state
old_step_sel = '''    def _on_step_selected(self, row: int):
        self._task_state.update_task(self._task_bar.current_task_id(), selected_step_index=max(0, row))
        self._save_task_snapshot()
        self._screenshot_picker.capture_and_display()'''

new_step_sel = '''    def _on_step_selected(self, row: int):
        self._task_state.update_task(self._task_bar.current_task_id(), selected_step_index=max(0, row))
        self._save_task_snapshot()
        self._screenshot_picker.capture_and_display()
        self._update_screenshot_empty_state()'''
content = content.replace(old_step_sel, new_step_sel)

# 4. Add _update_screenshot_empty_state method after _on_step_toggle_enabled
old_toggle_end = '''        wf.refresh_step_list()
        self._refresh_preview()

    def _on_screenshot_point_selected'''

new_toggle_end = '''        wf.refresh_step_list()
        self._refresh_preview()

    def _update_screenshot_empty_state(self):
        wf = self._panels["workflow_editor"]
        if not hasattr(wf, "_step_list"):
            return
        row = wf._step_list.currentRow()
        if row < 0:
            self._ss_empty.show()
            return
        steps = []
        if hasattr(wf, "_current_workflow_name") and wf._current_workflow_name:
            data = self._config_manager.get_workflow(wf._current_workflow_name)
            if data:
                steps = data.get("steps", [])
        if row < len(steps):
            step = steps[row]
            coord_types = {"tap", "long_press", "swipe", "tap_point"}
            if step.get("type", "") in coord_types:
                self._ss_empty.hide()
            else:
                self._ss_empty.set_state(
                    icon="\u274c",
                    message="\u5f53\u524d\u6b65\u9aa4\u65e0\u5750\u6807",
                    hint="\u9009\u62e9\u70b9\u51fb/\u6ed1\u52a8\u7c7b\u578b\u6b65\u9aa4"
                )
                self._ss_empty.show()
        else:
            self._ss_empty.show()

    def _on_screenshot_point_selected'''

content = content.replace(old_toggle_end, new_toggle_end)

# 5. Add resizeEvent to handle overlay sizing
old_close = '    def closeEvent(self, event):'
new_close = '''    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_ss_empty') and self._screenshot_picker:
            self._ss_empty.resize(self._screenshot_picker.size())
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.resize(self.size())

    def closeEvent(self, event):'''
content = content.replace(old_close, new_close)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))

import re
garbled = re.findall(r'[\ue000-\uf8ff]', content)
print("Garbled chars: %d" % len(garbled))
