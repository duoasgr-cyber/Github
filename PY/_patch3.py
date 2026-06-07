import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Add sidebar step context menu connections after the existing sidebar connections
old = '        self._screenshot_picker.point_selected.connect(self._on_screenshot_point_selected)'
new = '''        self._screenshot_picker.point_selected.connect(self._on_screenshot_point_selected)
        self._sidebar.step_preview.step_copy_requested.connect(self._on_step_copy)
        self._sidebar.step_preview.step_delete_requested.connect(self._on_step_delete)
        self._sidebar.step_preview.step_toggle_enabled.connect(self._on_step_toggle_enabled)'''

content = content.replace(old, new)

# Add the new handler methods after _on_screenshot_point_selected
old2 = '    def _on_screenshot_point_selected(self, x: int, y: int):'
new2 = '''    def _on_step_copy(self, index: int):
        wf = self._panels["workflow_editor"]
        if hasattr(wf, "_step_list"):
            wf._step_list.setCurrentRow(index)
            wf.copy_step()

    def _on_step_delete(self, index: int):
        wf = self._panels["workflow_editor"]
        if hasattr(wf, "_step_list"):
            wf._step_list.setCurrentRow(index)
            wf.delete_step()

    def _on_step_toggle_enabled(self, index: int):
        wf = self._panels["workflow_editor"]
        if not hasattr(wf, "_current_workflow_name") or not wf._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(wf._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if index >= len(steps):
            return
        steps[index]["enabled"] = not steps[index].get("enabled", True)
        workflow["steps"] = steps
        self._config_manager.set_workflow(wf._current_workflow_name, workflow)
        wf.refresh_step_list()
        self._refresh_preview()

    def _on_screenshot_point_selected(self, x: int, y: int):'''

content = content.replace(old2, new2)

with open(filepath, 'w', encoding='utf-8-sig') as f:
    f.write(content)

print("main_window.py: step context menu signals connected")
