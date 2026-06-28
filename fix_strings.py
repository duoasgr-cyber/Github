import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'D:\Github\PY\ui\main_window.py', 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8')

# Find all quoted strings containing Chinese or PUA chars
strings = re.findall(r'"([^"]{2,})"', text)
for s in strings:
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in s)
    has_pua = any(0xe000 <= ord(c) <= 0xf8ff for c in s)
    if has_cjk or has_pua:
        try:
            fixed_bytes = s.encode('gb18030')
            fixed = fixed_bytes.decode('utf-8')
            print('FIXABLE: "' + s + '" -> "' + fixed + '"')
        except Exception as e:
            cps = [hex(ord(c)) for c in s]
            print('UNFIXABLE: "' + s + '" codepoints=' + str(cps) + ' error=' + str(e))
