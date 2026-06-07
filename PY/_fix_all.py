import sys

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')

# Line-by-line fixes (0-indexed)
fixes = {
    # Status bar labels
    346: '        self._device_label = QLabel("\u8bbe\u5907: \u672a\u8fde\u63a5")'.encode('utf-8'),
    348: '        self._ocr_label = QLabel("OCR: \u672a\u52a0\u8f7d")'.encode('utf-8'),
    # Tray actions
    366: '        show_action = QAction("\u663e\u793a\u4e3b\u7a97\u53e3", self)'.encode('utf-8'),
    367: '        hide_action = QAction("\u9690\u85cf\u4e3b\u7a97\u53e3", self)'.encode('utf-8'),
    368: '        quit_action = QAction("\u9000\u51fa", self)'.encode('utf-8'),
    # Monitoring - start
    465: '            QMessageBox.warning(self, "\u65e0\u6cd5\u542f\u52a8", "\u8bf7\u5148\u5728\u4fa7\u4fa7\u8fb9\u680f\u9009\u62e9\u8bbe\u5907\u540e\u518d\u542f\u52a8\u3002")'.encode('utf-8'),
    477: '        self._panels["status_monitor"].update_status("\u8fd0\u884c\u4e2d", "#00ff88")'.encode('utf-8'),
    479: '        self._floating_widget.update_status("\u8fd0\u884c\u4e2d", "#00ff88")'.encode('utf-8'),
    # Monitoring - stop
    489: '        self._panels["status_monitor"].update_status("\u505c\u6b62\u4e2d..", "#ffaa00")'.encode('utf-8'),
    490: '        self._floating_widget.update_status("\u505c\u6b62\u4e2d..", "#ffaa00")'.encode('utf-8'),
    # Monitoring - pause
    493: '        self._panels["status_monitor"].update_status("\u5df2\u6682\u505c", "#ffaa00")'.encode('utf-8'),
    494: '        self._floating_widget.update_status("\u5df2\u6682\u505c", "#ffaa00")'.encode('utf-8'),
    # Monitoring - resume
    497: '        self._panels["status_monitor"].update_status("\u8fd0\u884c\u4e2d", "#00ff88")'.encode('utf-8'),
    498: '        self._floating_widget.update_status("\u8fd0\u884c\u4e2d", "#00ff88")'.encode('utf-8'),
    # Monitoring - completed
    502: '        self._panels["status_monitor"].update_status("\u5df2\u5b8c\u6210", "#a0a0a0")'.encode('utf-8'),
    503: '        self._floating_widget.update_status("\u5df2\u5b8c\u6210", "#a0a0a0")'.encode('utf-8'),
    # Device status
    504: '    def set_device_status(self, serial: str):'.encode('utf-8'),
    505: '        if serial:'.encode('utf-8'),
    506: '            self._device_label.setText(f"\u8bbe\u5907: {serial}")'.encode('utf-8'),
    507: '        else:'.encode('utf-8'),
    508: '            self._device_label.setText("\u8bbe\u5907: \u672a\u8fde\u63a5")'.encode('utf-8'),
    509: '    def set_connection_status(self, connected: bool):'.encode('utf-8'),
    510: '        self._connection_label.setText("\u8fde\u63a5: \u5df2\u8fde\u63a5" if connected else "\u8fde\u63a5: \u65ad\u5f00")'.encode('utf-8'),
    # Log messages
    512: '        logging.info("\u6b65\u9aa4 %d \u5f00\u59cb %s", index + 1, step_type)'.encode('utf-8'),
    514: '        logging.info("\u5de5\u4f5c\u6d41\u5b8c\u6210 %s", name)'.encode('utf-8'),
    516: '        logging.error("\u5de5\u4f5c\u6d41\u5931\u8d25 %s - %s", name, error)'.encode('utf-8'),
    518: '        logging.info("\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62")'.encode('utf-8'),
    # Exception handler
    396: '            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)'.encode('utf-8'),
    398: '                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)'.encode('utf-8'),
    # Tray tooltip
    352: '        self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u62a2\u8d2d\u5de5\u5177 v2.0")'.encode('utf-8'),
    # Monitoring start log
    484: '            logging.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7")'.encode('utf-8'),
    486: '            logging.warning("\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d")'.encode('utf-8'),
    488: '        logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)'.encode('utf-8'),
    # Settings dialog labels
    196: '        dlg.setWindowTitle("\u8bbe\u7f6e")'.encode('utf-8'),
    200: '        tabs.addTab(self._panels["configuration"], "\u914d\u7f6e")'.encode('utf-8'),
    201: '        tabs.addTab(self._panels["device_management"], "\u8bbe\u5907\u7ba1\u7406")'.encode('utf-8'),
}

for idx, new_line in fixes.items():
    if idx < len(lines):
        lines[idx] = new_line

raw = b'\n'.join(lines)
with open(filepath, 'wb') as f:
    f.write(raw)

import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("AST parse OK")
except SyntaxError as e:
    print("SyntaxError at line %d: %s" % (e.lineno, e.msg))
    ls = content.split('\n')
    if e.lineno and e.lineno <= len(ls):
        print("Line: %s" % repr(ls[e.lineno-1]))
