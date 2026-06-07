import sys, re

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all lines with syntax issues caused by garbled encoding
# The pattern is: Chinese text that contains ? (0x3f) inside a string literal
# which breaks the quote matching

# Strategy: find all string literals that contain the garbled pattern
# and replace them with proper Chinese

# Known garbled patterns and their correct replacements
fixes = {
    # Status bar labels
    'QLabel("\u8bf9\u30e2: \u672a\u8fde\u63a5")': 'QLabel("\u8bbe\u5907: \u672a\u8fde\u63a5")',
    'QLabel("\u8fde\u63a5: \u65ad\u5f00")': 'QLabel("\u8fde\u63a5: \u65ad\u5f00")',
    'QLabel("OCR: \u672a\u52a0\u8f7d")': 'QLabel("OCR: \u672a\u52a0\u8f7d")',
    # Connection status
    '"\u8fde\u63a5: \u5df2\u8fde\u63a5"': '"\u8fde\u63a5: \u5df2\u8fde\u63a5"',
    '"\u8fde\u63a5: \u65ad\u5f00"': '"\u8fde\u63a5: \u65ad\u5f00"',
    # Settings dialog
    '\u8bf9\u9898': '\u8bbe\u7f6e',
    # Tray
    '\u9650\u51fa': '\u9000\u51fa',
    # Monitoring
    '"\u8fd0\u884c\u4e2d"': '"\u8fd0\u884c\u4e2d"',
    '"\u505c\u6b62\u4e2d.."': '"\u505c\u6b62\u4e2d.."',
    '"\u5df2\u6682\u505c"': '"\u5df2\u6682\u505c"',
    '"\u5df2\u5b8c\u6210"': '"\u5df2\u5b8c\u6210"',
    # Log messages
    '\u6b65\u9aa4 %d \u5f00\u59cb %s': '\u6b65\u9aa4 %d \u5f00\u59cb %s',
    '\u5de5\u4f5c\u6d41\u5b8c\u6210 %s': '\u5de5\u4f5c\u6d41\u5b8c\u6210 %s',
    '\u5de5\u4f5c\u6d41\u5931\u8d25 %s - %s': '\u5de5\u4f5c\u6d41\u5931\u8d25 %s - %s',
    '\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62': '\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62',
    '\u542f\u52a8\u76d1\u63a7: %s': '\u542f\u52a8\u76d1\u63a7: %s',
    # Error messages
    '\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7': '\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7',
    '\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d': '\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d',
    '\u672a\u5904\u7406\u7684\u5f02\u5e38': '\u672a\u5904\u7406\u7684\u5f02\u5e38',
}

# Actually, the issue is more fundamental. The garbled text contains '?' (0x3f)
# which breaks Python string parsing. Let me use a different approach:
# Read as bytes, fix the broken lines

with open(filepath, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')

# Map of line patterns to their proper replacements
line_fixes = {}

for i, line in enumerate(lines):
    # Check for lines with odd number of quotes (broken strings)
    quote_count = line.count(b'"') + line.count(b"'")
    if quote_count % 2 != 0 and (b'QLabel' in line or b'setText' in line or b'logging' in line or b'QMessageBox' in line):
        # This line has a broken string literal
        print("Broken line %d: %s" % (i+1, line[:80]))

# Let me just do a brute-force fix: replace known broken lines by their line number
# based on the current file state

# First, let me identify all broken lines
broken = []
for i, line in enumerate(lines):
    qc = line.count(b'"')
    if qc % 2 != 0:
        broken.append(i)
        print("Line %d has %d quotes: %s" % (i+1, qc, line[:60]))

print("Total broken lines: %d" % len(broken))
