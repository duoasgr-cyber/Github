import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\ui\main_window.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Line index (0-based) -> replacement line content (using actual Unicode chars)
fixes = {}

fixes[108] = '        ("\u5de5\u4f5c\u6d41\u7f16\u8f91", "workflow_editor"),'
fixes[109] = '        ("\u914d\u7f6e", "configuration"),'
fixes[110] = '        ("\u8bbe\u5907\u7ba1\u7406", "device_management"),'
fixes[111] = '        ("\u8fd0\u884c\u76d1\u63a7", "status_monitor"),'
fixes[112] = '        ("\u6d4b\u8bd5", "test"),'
fixes[150] = '        self.setWindowTitle("\u4e09\u89d2\u6d32\u81ea\u52a8\u5316\u62a2\u8d2d\u5de5\u5177 v2.0")'
fixes[195] = '            icon="\U0001f4f7",'
fixes[196] = '            message="\u6682\u65e0\u622a\u56fe",'
fixes[197] = '            hint="\u9009\u62e9\u5750\u6807\u6b65\u9aa4\u540e\u81ea\u52a8\u622a\u56fe"'
fixes[305] = '        dlg.setWindowTitle("\u8bbe\u7f6e")'
fixes[309] = '        tabs.addTab(self._panels["configuration"], "\u914d\u7f6e")'
fixes[310] = '        tabs.addTab(self._panels["device_management"], "\u8bbe\u5907\u7ba1\u7406")'
fixes[327] = '        if QMessageBox.question(self, "\u5173\u95ed\u4efb\u52a1", f"\u786e\u5b9a\u5173\u95ed\u4efb\u52a1\u300c{title}\u300d\u5417\uff1f", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:'
fixes[408] = '                    icon="\u274c",'
fixes[409] = '                    message="\u5f53\u524d\u6b65\u9aa4\u65e0\u5750\u6807",'
fixes[410] = '                    hint="\u9009\u62e9\u70b9\u51fb/\u6ed1\u52a8\u7c7b\u578b\u6b65\u9aa4"'
fixes[487] = '        self._device_label = QLabel("\u8bbe\u5907: \u672a\u8fde\u63a5")'
fixes[488] = '        self._connection_label = QLabel("\u8fde\u63a5: \u65ad\u5f00")'
fixes[489] = '        self._ocr_label = QLabel("OCR: \u672a\u52a0\u8f7d")'
fixes[503] = '        self._tray_icon.setToolTip("\u4e09\u89d2\u6d32\u81ea\u52a8\u5316\u62a2\u8d2d\u5de5\u5177 v2.0")'
fixes[507] = '        show_action = QAction("\u663e\u793a\u4e3b\u7a97\u53e3", self)'
fixes[508] = '        hide_action = QAction("\u9690\u85cf\u4e3b\u7a97\u53e3", self)'
fixes[509] = '        quit_action = QAction("\u9000\u51fa", self)'
fixes[571] = '            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)'
fixes[573] = '                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)'
fixes[576] = '            logging.critical("\u672a\u5904\u7406\u7684\u5f02\u5e38:\\n%s", tb_text)'
fixes[578] = '                self._log_panel._append_log(f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc_value}", logging.ERROR)'
fixes[612] = '            QMessageBox.warning(self, "\u65e0\u6cd5\u542f\u52a8", "\u8bf7\u5148\u5728\u4fa7\u8fb9\u680f\u9009\u62e9\u8bbe\u5907\u540e\u518d\u542f\u52a8\u3002")'
fixes[616] = '            logging.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41\uff0c\u65e0\u6cd5\u542f\u52a8\u76d1\u63a7")'
fixes[619] = '            logging.warning("\u5de5\u4f5c\u6d41\u5df2\u5728\u8fd0\u884c\u4e2d")'
fixes[624] = '        self._panels["status_monitor"].update_status("\u8fd0\u884c\u4e2d", "#00ff88")'
fixes[626] = '        self._floating_widget.update_status("\u8fd0\u884c\u4e2d", "#00ff88")'
fixes[628] = '        logging.info("\u542f\u52a8\u76d1\u63a7: %s", workflow_name)'
fixes[632] = '        self._panels["status_monitor"].update_status("\u505c\u6b62\u4e2d...", "#ffaa00")'
fixes[633] = '        self._floating_widget.update_status("\u505c\u6b62\u4e2d...", "#ffaa00")'
fixes[637] = '        self._panels["status_monitor"].update_status("\u5df2\u6682\u505c", "#ffaa00")'
fixes[638] = '        self._floating_widget.update_status("\u5df2\u6682\u505c", "#ffaa00")'
fixes[642] = '        self._panels["status_monitor"].update_status("\u8fd0\u884c\u4e2d", "#00ff88")'
fixes[643] = '        self._floating_widget.update_status("\u8fd0\u884c\u4e2d", "#00ff88")'
fixes[646] = '        self._panels["status_monitor"].update_status("\u5df2\u5b8c\u6210", "#a0a0a0")'
fixes[647] = '        self._floating_widget.update_status("\u5df2\u5b8c\u6210", "#a0a0a0")'
fixes[651] = '            self._device_label.setText(f"\u8bbe\u5907: {serial}")'
fixes[653] = '            self._device_label.setText("\u8bbe\u5907: \u672a\u8fde\u63a5")'
fixes[657] = '        self._connection_label.setText("\u8fde\u63a5: \u5df2\u8fde\u63a5" if connected else "\u8fde\u63a5: \u65ad\u5f00")'
fixes[660] = '        logging.info("\u6b65\u9aa4 %d \u5f00\u59cb: %s", index + 1, step_type)'
fixes[663] = '        logging.info("\u5de5\u4f5c\u6d41\u5b8c\u6210: %s", name)'
fixes[666] = '        logging.error("\u5de5\u4f5c\u6d41\u5931\u8d25: %s - %s", name, error)'
fixes[669] = '        logging.info("\u5de5\u4f5c\u6d41\u5df2\u505c\u6b62")'

# Apply fixes
changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        old = lines[idx]
        lines[idx] = replacement
        changed += 1
        print("Fixed L" + str(idx+1))

print("\nTotal lines changed: " + str(changed))

# Write back
new_content = '\n'.join(lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("File written successfully.")
