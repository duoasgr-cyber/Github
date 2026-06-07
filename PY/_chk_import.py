import sys

filepath = r'D:\Github\PY\ui\components\step_list_widget.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# QColor is already imported in the file header
if 'QColor' in content.split('from PyQt5')[1] if 'from PyQt5' in content else '':
    print("QColor already imported")
else:
    # Check the import line
    if 'from PyQt5.QtGui import QFont, QColor' in content:
        print("QColor already imported")
    elif 'from PyQt5.QtGui import QFont' in content:
        content = content.replace(
            'from PyQt5.QtGui import QFont',
            'from PyQt5.QtGui import QFont, QColor'
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Added QColor import")
    else:
        print("Could not find import line")
