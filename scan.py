import os
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

py_dir = r'D:\Github\PY'
issues = []
for root, dirs, files in os.walk(py_dir):
    for f in files:
        if f.endswith('.py') and not f.startswith('_'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    for i, line in enumerate(fh, 1):
                        if re.search(r'[\ue000-\uf8ff]', line):
                            issues.append(path + ':' + str(i) + ': PUA')
                        if re.search(r'[\u30a0-\u30ff]', line):
                            issues.append(path + ':' + str(i) + ': KATAKANA')
            except:
                pass

for issue in issues:
    print(issue)
print('Total issues: ' + str(len(issues)))
