import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\main_window.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Build replacement map: garbled -> correct
# Based on the 31 garbled lines identified and contextual analysis
replacements = [
    # NAV_ITEMS (lines 109-113)
    ('\u5bb8\u30e4\u7d94\u5a34\u4f7a\u7d2a\u6748', '工作流编辑'),  # 工作流编辑
    ('\u91c7\u5007\u5c42', '配置'),  # 配置
    ('\u8ba9\u60e7\ue62c\u7ba1\u7406', '设备管理'),  # 设备管理
    ('\u6d69\u612f\ue511\u76d1\u63a7', '运行监控'),  # 运行监控
    ('\u5a10\u8bd8\u8bd5', '测试'),  # 测试
    
    # setWindowTitle (line 151)
    ('\u6d93\u590e\ue757\u5a32\u8336\u569c\u9354\u3126\u59e0\u7490\ue15e\u4f10\u934f?v2.0', '三角洲自动化抢购工具 v2.0'),
    
    # Empty state widgets (lines 196-198)
    ('\u998d\u64b2', '📷'),
    ('\u93c3\ue04b\u6d57', '暂无截图'),
    # line 198 hint - will handle separately due to truncation
    
    # Settings dialog (line 306)
    ('\u8ba9\u7f6e', '设置'),
    
    # Configuration tab (line 310) 
    ('\u91c7\u5007\u5c42', '配置'),
    
    # Device management tab (line 311)
    ('\u8ba9\u60e7\ue62c\u7ba1\u7406', '设备管理'),
    
    # Close task dialog (line 328)
    ('\u950f\u62bd\u4efb\u52a1', '关闭任务'),
    
    # Tray icon (lines 508-510)
    ('\u93c4\u524b\u311a\u6d93\u8d64\u7d65\u9359', '显示主窗口'),
    ('\u95c5\u612f\u68cc\u6d93\u8364\u7365\u9359', '隐藏主窗口'),
    ('\u9009\u51fa', '退出'),
]

# This approach of doing string replacement on garbled text is fragile.
# Let me instead do line-by-line replacement based on line numbers.
print("Switching to line-by-line approach...")

lines = content.split('\n')
print(f"Total lines: {len(lines)}")

# Print specific lines we need to fix to verify
target_lines = [108,109,110,111,112,113,150,195,196,197,198,305,309,310,311,327,408,409,410,411,487,488,489,503,507,508,509,571,573,576,578,612,616,619,624,626,628,632,633,637,638,642,643,646,647,651,653,657,660,663,666,669]
for ln in target_lines:
    if ln < len(lines):
        print(f"L{ln+1}: {lines[ln].rstrip()}")
