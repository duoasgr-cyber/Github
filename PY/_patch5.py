import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Add floating widget signal connections
old = '        self._tray_icon.activated.connect(self._on_tray_activated)'
new = '''        self._tray_icon.activated.connect(self._on_tray_activated)
        self._floating_widget.pause_requested.connect(self._on_pause_monitoring)
        self._floating_widget.stop_requested.connect(self._on_stop_monitoring)'''

content = content.replace(old, new)

with open(filepath, 'w', encoding='utf-8-sig') as f:
    f.write(content)

print("main_window.py: floating widget signals connected")
