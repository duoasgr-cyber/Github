import sys, os

base = r'D:\Github\PY'
mw_path = os.path.join(base, 'ui', 'main_window.py')
with open(mw_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Pass screen_capture to WorkflowPanel instead of None
content = content.replace(
    '"workflow_editor": WorkflowPanel(self._config_manager, None),',
    '"workflow_editor": WorkflowPanel(self._config_manager, self._screen_capture),'
)

# Fix 2: The main window's _on_screenshot_point_selected should also update
# the WorkflowPanel's internal screenshot picker coords (redundant but safe)
# Actually the current code already does this via wf_panel._step_editor.update_coord_fields

# Fix 3: The _update_screenshot_empty_state accesses wf._step_list
# but WorkflowPanel has self._step_list (its own internal list, not the sidebar's)
# The sidebar's step_preview is a separate StepListWidget.
# The _update_screenshot_empty_state should check the sidebar's step_preview count
# Let me verify the current logic is correct

# Fix 4: The _on_step_copy/_on_step_delete/_on_step_toggle_enabled methods
# access wf._step_list and wf._current_workflow_name - these are WorkflowPanel internals
# which is correct since we want to operate on the workflow editor's step list

with open(mw_path, 'w', encoding='utf-8') as f:
    f.write(content)

import ast
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))

# Verify the fix
if 'WorkflowPanel(self._config_manager, self._screen_capture)' in content:
    print("Fix 1 applied: screen_capture passed to WorkflowPanel")
else:
    print("Fix 1 FAILED!")
