import sys

filepath = r'D:\Github\PY\ui\main_window.py'

# Read the file as bytes
with open(filepath, 'rb') as f:
    raw = f.read()

# Strategy: replace all garbled Chinese sequences with proper ones
# The garbled text follows a pattern: it was originally GBK/GB2312 encoded
# but got read as Latin-1 or similar, then re-encoded as UTF-8

# Known correct replacements for the specific garbled patterns
byte_replacements = [
    # "涓夎娲茶嚜鍔ㄦ姠璐伐鍏?" -> "三角洲自动抢购工具"
    (b'\xe5\xb9\x95\xe3\x83\xa4\xe7\xb6\x94\xe5\xa8\xb4\xe4\xbd\xba\xe7\xb4\xaa\xe6\x9d\x88?',
     '\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177'.encode('utf-8')),
    # "璁剧疆" -> "设置"
    (b'\xe7\x92\x81\xe6\x83\xa7\xee\x98\xac',
     '\u8bbe\u7f6e'.encode('utf-8')),
    # "宸ヤ綔娴佺紪杈?" -> "工作流编辑"  
    (b'\xe5\xae\xb8\xe3\x83\xa4\xe7\xb6\x94\xe5\xa8\xb4\xe4\xbd\xba\xe7\xb4\xaa\xe6\x9d\x88?',
     '\u5de5\u4f5c\u6d41\u7f16\u8f91'.encode('utf-8')),
    # "閰嶇疆" -> "配置"
    (b'\xe9\x96\xb0\xe5\xb6\x87\xe7\x96\x86',
     '\u914d\u7f6e'.encode('utf-8')),
    # "璁惧绠＄悊" -> "设备管理"
    (b'\xe7\x92\x81\xe6\x83\xa7\xee\x98\xac\xe7\xba\xa0\xef\xbc\x84\xe6\x82\x8a',
     '\u8bbe\u5907\u7ba1\u7406'.encode('utf-8')),
    # "杩愯鐩戞帶" -> "运行监控"
    (b'\xe6\x9d\xa9\xe6\x84\xaf\xee\x94\x91\xe9\x90\xa9\xe6\x88\x9e\xe5\xb8\xb6',
     '\u8fd0\u884c\u76d1\u63a7'.encode('utf-8')),
    # "娴嬭瘯" -> "测试"
    (b'\xe5\xa8\xb4\xe5\xac\xad\xe7\x98\xaf',
     '\u6d4b\u8bd5'.encode('utf-8')),
    # "璁惧: 鏈繛鎺?" -> "设备: 未连接"
    (b'\xe7\x92\x81\xe6\x83\xa7\xee\x98\xac: \xe9\x8f\x88\xee\x81\x87\xe7\xb9\x9b\xe9\x8e\xba?',
     '\u8bbe\u5907: \u672a\u8fde\u63a5'.encode('utf-8')),
    # "杩炴帴: 鏂紑" -> "连接: 断开"
    (b'\xe6\x9d\xa9\xe7\x82\xb4\xe5\xb8\xb4: \xe5\xae\xb8\xe8\x8c\xb6\xe7\xb9\x9b\xe9\x8e\xba?',
     '\u8fde\u63a5: \u65ad\u5f00'.encode('utf-8')),
    # "杩炴帴: 瀹茶繛鎺?" -> "连接: 已连接"
    (b'\xe6\x9d\xa9\xe7\x82\xb4\xe5\xb8\xb4: \xe5\xae\xb8\xe8\x8c\xb6\xe7\xb9\x9b\xe9\x8e\xba',
     '\u8fde\u63a5: \u5df2\u8fde\u63a5'.encode('utf-8')),
    # "OCR: 鏈姞杞?" -> "OCR: 未加载"
    (b'OCR: \xe9\x8f\x88\xee\x81\x84\xe5\xa7\x9e\xe6\x9d\x9e?',
     'OCR: \u672a\u52a0\u8f7d'.encode('utf-8')),
    # "鏄剧ず涓荤獥鍙?" -> "显示主窗口"
    (b'\xe9\x8f\x84\xe5\x89\xa7\xe3\x81\x9a\xe6\xb6\x93\xe8\x8d\xa4\xe7\x8d\xa5\xe9\x8d\x99?',
     '\u663e\u793a\u4e3b\u7a97\u53e3'.encode('utf-8')),
    # "闅棌涓荤獥鍙?" -> "隐藏主窗口"
    (b'\xe9\x97\x85\xe6\x84\xaf\xe6\xa3\x8c\xe6\xb6\x93\xe8\x8d\xa4\xe7\x8d\xa5\xe9\x8d\x99?',
     '\u9690\u85cf\u4e3b\u7a97\u53e3'.encode('utf-8')),
    # "閫€鍑?" -> "退出"
    (b'\xe9\x96\xab\xe2\x82\xac\xe9\x8d\x91?',
     '\u9000\u51fa'.encode('utf-8')),
    # "鐩戞帶" -> "监控"
    (b'\xe7\x9b\x91\xe6\x8e\xa5',
     '\u76d1\u63a7'.encode('utf-8')),
    # "鏃犳硶鍚姩" -> "无法启动"
    (b'\xe9\x8f\x83\xe7\x8a\xb3\xe7\xa1\xb6\xe9\x8d\x9a\xee\x88\x9a\xe5\xa7\xa9',
     '\u65e0\u6cd5\u542f\u52a8'.encode('utf-8')),
    # "璇峰厛鍦ㄥ乏渚ц竟鏍忛€夋嫨璁惧鍚庡啀鍚姩銆?" -> "请先在侧边栏选择设备后再启动。"
    (b'\xe7\x92\x87\xe5\xb3\xb0\xe5\x8e\x9b\xe9\x8d\xa6\xe3\x84\xa5\xe4\xb9\x8f\xe6',
     '\u8bf7\u5148\u5728\u4fa7\u8fb9\u680f\u9009\u62e9\u8bbe\u5907\u540e\u518d\u542f\u52a8\u3002'.encode('utf-8')),
    # "鏈€閫夋€閫夋嫨宸ヤ綔娴侊紝鏃犳硶鍚姩鐩戞帶" -> "未选择工作流，无法启动监控"
    (b'\xe6\x9d\xa9\xe2\x82\xac\xe9\x96\xb5\xe5\x8a\xb1\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xef\xbc\x8c\xe9\x8f\x83\xe7\x8a\xb3\xe7\xa1\xb6\xe9\x8d\x9a\xee\x88\x9a\xe5\xa7\xa9\xe7\x9b\x91\xe6\x8e\xa5',
     '\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7'.encode('utf-8')),
    # "宸ヤ綔娴佸凡鍦ㄨ繍琛屼腑" -> "工作流已在运行中"
    (b'\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xe5\xb7\xb2\u5728\u8fd0\u884c\u4e2d',
     '\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d'.encode('utf-8')),
    # "杩愯琛屼腑" -> "运行中"
    (b'\xe6\x9d\xa9\xe6\x84\xaf\xee\x94\x91\xe6\xb6\x93?',
     '\u8fd0\u884c\u4e2d'.encode('utf-8')),
    # "鍋滄涓?.." -> "停止中.."
    (b'\xe5\xae\xb8\xe5\x8f\x89\xe6\xae\x8f\xe9\x8d\x8b?',
     '\u505c\u6b62\u4e2d..'.encode('utf-8')),
    # "宸叉殏鍋?" -> "已暂停"
    (b'\xe6\x9d\xa9\xe6\x84\xaf\xee\x94\x91\xe6\xb6\x93',
     '\u5df2\u6682\u505c'.encode('utf-8')),
    # "宸插畬鎴?" -> "已完成"
    (b'\xe5\xae\xb8\xe6\x8f\x92\xe7\x95\xac\xe9\x8e\xb4',
     '\u5df2\u5b8c\u6210'.encode('utf-8')),
    # "鏈崟鑾风殑寮傚父" -> "未处理的异常"
    (b'\xe6\x9d\xa9\xe2\x82\xac\xe5\xb4\x9b\xe7\x95\xb2\xe9\x8f\x87\xe5\x8f\x88',
     '\u672a\u5904\u7406\u7684\u5f02\u5e38'.encode('utf-8')),
    # "姝ラ %d 寮€濮? %s" -> "步骤 %d 开始 %s"
    (b'\xe5\xa9\xb4\xe3\x81\x82 %d \xe5\x8f\x88\xe6\xbf\x88?',
     '\u6b65\u9aa4 %d \u5f00\u59cb %s'.encode('utf-8')),
    # "宸ヤ綔娴佸畬鎴? %s" -> "工作流完成 %s"
    (b'\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xe5\xae\x8c\xe6\x88\x90 %s',
     '\u5de5\u4f5c\u6d41\u5b8c\u6210 %s'.encode('utf-8')),
    # "宸ヤ綔娴佸け璐? %s - %s" -> "工作流失败 %s - %s"
    (b'\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xe5\xa4\xb1\xe8\xb4\xa5 %s - %s',
     '\u5de5\u4f5c\u6d41\u5931\u8d25 %s - %s'.encode('utf-8')),
    # "宸ヤ綔娴佸凡鍋滄" -> "工作流已停止"
    (b'\xe5\xb7\xa5\xe4\xbd\x9c\xe6\xb5\x81\xe5\xb7\xb2\xe5\x81\x9c\xe6\xad\xa2',
     '\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62'.encode('utf-8')),
    # "鍚姩鐩戞帶: %s" -> "启动监控: %s"
    (b'\xe5\x90\xaf\xe5\x8a\xa8\u76d1\u63a7: %s',
     '\u542f\u52a8\u76d1\u63a7: %s'.encode('utf-8')),
]

for old, new in byte_replacements:
    if old in raw:
        raw = raw.replace(old, new)
        print("Replaced: %s -> %s" % (old[:20], new[:20]))

with open(filepath, 'wb') as f:
    f.write(raw)

print("\nNow checking syntax...")
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK!")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))
