import sys, ast, re, os

base = r'D:\Github\PY'

print("=" * 60)
print("8. WORKFLOW PANEL COMPATIBILITY CHECK")
print("=" * 60)

wp_path = os.path.join(base, 'ui', 'panels', 'workflow_panel.py')
with open(wp_path, 'r', encoding='utf-8') as f:
    wp = f.read()

# Check: WorkflowPanel now receives screen_capture=None
# The ScreenshotPicker was extracted. Does WP still reference it?
ss_refs = re.findall(r'self\._screenshot_picker', wp)
print("  WorkflowPanel still references _screenshot_picker: %d times" % len(ss_refs))
if ss_refs:
    # Check if it still creates one
    if 'ScreenshotPicker(' in wp:
        print("  WARNING: WorkflowPanel still creates ScreenshotPicker internally!")
    else:
        print("  OK: WorkflowPanel references _screenshot_picker but does not create it")
        # This means the references will fail at runtime!

# Check what methods reference _screenshot_picker
for i, line in enumerate(wp.split('\n')):
    if '_screenshot_picker' in line:
        print("    Line %d: %s" % (i+1, line.strip()))

print("\n" + "=" * 60)
print("9. MAIN WINDOW -> WORKFLOW PANEL COMPAT CHECK")
print("=" * 60)

mw_path = os.path.join(base, 'ui', 'main_window.py')
with open(mw_path, 'r', encoding='utf-8') as f:
    mw = f.read()

# Check how WorkflowPanel is instantiated
for line in mw.split('\n'):
    if 'WorkflowPanel(' in line:
        print("  WP instantiation: %s" % line.strip())

# Check if main_window accesses wf._step_editor (used in _on_screenshot_point_selected)
for line in mw.split('\n'):
    if 'wf_panel._step_editor' in line or 'wf._step_editor' in line:
        print("  MW accesses: %s" % line.strip())

print("\n" + "=" * 60)
print("10. CORE MODULES NOT MODIFIED CHECK")
print("=" * 60)

core_files = [
    'core/adb_core.py',
    'core/config_manager.py', 
    'core/device_manager.py',
    'core/logger.py',
    'core/ocr_engine.py',
    'core/screen_capture.py',
    'core/step_executor.py',
    'core/task_state_manager.py',
    'core/workflow_engine.py',
]

for cf in core_files:
    path = os.path.join(base, cf)
    if os.path.exists(path):
        print("  OK (exists): %s" % cf)
    else:
        print("  MISSING: %s" % cf)
