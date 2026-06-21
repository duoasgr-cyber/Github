import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'D:\Github\PY\ui\main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

old_line = lines[128]
print('Before:', repr(old_line))

new_line = '        self._screen_capture.error_occurred.connect(lambda msg: logging.error("\u6295\u5c4f\u9519\u8bef: %s", msg))\n'
lines[128] = new_line

with open(r'D:\Github\PY\ui\main_window.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed')
