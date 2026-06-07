import sys, os

filepath = r'D:\Github\PY\ui\main_window.py'
with open(filepath, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]

    # 1. Replace imports (lines 30-31)
    if i == 30 and 'DeviceBindWidget' in line:
        new_lines.append('from ui.components.sidebar_widget import SidebarWidget\n')
        i += 1
        continue
    if i == 31 and 'WorkflowSwitcher' in line:
        new_lines.append('from ui.components.screenshot_picker import ScreenshotPicker\n')
        i += 1
        continue

    # 2. Replace _init_ui method (lines 91-151)
    if i == 91 and 'def _init_ui' in line:
        new_lines.append(line)
        new_lines.append(lines[92])
        new_lines.append(lines[93])
        new_lines.append('\n')
        new_lines.append('        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n')
        new_lines.append('        ui_state_path = os.path.join(base_dir, "config", "ui_state.json")\n')
        new_lines.append('\n')
        new_lines.append(lines[95])
        new_lines.append(lines[96])
        new_lines.append(lines[97])
        new_lines.append(lines[98])
        new_lines.append(lines[99])
        new_lines.append('\n')
        new_lines.append(lines[101])
        new_lines.append(lines[102])
        new_lines.append('\n')
        new_lines.append(lines[104])
        new_lines.append(lines[105])
        new_lines.append(lines[106])
        new_lines.append(lines[107])
        new_lines.append('\n')
        new_lines.append('        # -- collapsible sidebar\n')
        new_lines.append('        self._sidebar = SidebarWidget(\n')
        new_lines.append('            self._device_manager, self._adb_core,\n')
        new_lines.append('            self._config_manager, ui_state_path=ui_state_path\n')
        new_lines.append('        )\n')
        new_lines.append('        self._sidebar.setFixedWidth(260)\n')
        new_lines.append('        self._device_bind = self._sidebar.device_bind\n')
        new_lines.append('        self._workflow_switcher = self._sidebar.workflow_switcher\n')
        new_lines.append('        self._step_preview = self._sidebar.step_preview\n')
        new_lines.append('\n')
        new_lines.append('        self._stacked = QStackedWidget()\n')
        new_lines.append('        self._panels = {\n')
        new_lines.append('            "workflow_editor": WorkflowPanel(self._config_manager, None),\n')
        new_lines.append('            "configuration": ConfigPanel(self._config_manager),\n')
        new_lines.append('            "device_management": DevicePanel(self._device_manager, self._adb_core),\n')
        new_lines.append('            "status_monitor": StatusPanel(),\n')
        new_lines.append('            "test": TestPanel(self._step_executor, self._config_manager),\n')
        new_lines.append('        }\n')
        new_lines.append('        for _, key in self.NAV_ITEMS:\n')
        new_lines.append('            self._stacked.addWidget(self._panels[key])\n')
        new_lines.append('\n')
        new_lines.append('        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture)\n')
        new_lines.append('\n')
        new_lines.append('        editor_splitter = QSplitter(Qt.Horizontal)\n')
        new_lines.append('        editor_splitter.addWidget(self._stacked)\n')
        new_lines.append('        editor_splitter.addWidget(self._screenshot_picker)\n')
        new_lines.append('        editor_splitter.setStretchFactor(0, 3)\n')
        new_lines.append('        editor_splitter.setStretchFactor(1, 2)\n')
        new_lines.append('        editor_splitter.setChildrenCollapsible(False)\n')
        new_lines.append('\n')
        new_lines.append('        self._log_panel = LogPanel()\n')
        new_lines.append('\n')
        new_lines.append('        main_splitter = QSplitter(Qt.Vertical)\n')
        new_lines.append('        main_splitter.addWidget(editor_splitter)\n')
        new_lines.append('        main_splitter.addWidget(self._log_panel)\n')
        new_lines.append('        main_splitter.setStretchFactor(0, 5)\n')
        new_lines.append('        main_splitter.setStretchFactor(1, 1)\n')
        new_lines.append('        main_splitter.setSizes([620, 180])\n')
        new_lines.append('        main_splitter.setChildrenCollapsible(False)\n')
        new_lines.append('        self._main_splitter = main_splitter\n')
        new_lines.append('\n')
        new_lines.append('        body_layout.addWidget(self._sidebar)\n')
        new_lines.append('        body_layout.addWidget(main_splitter, stretch=1)\n')
        new_lines.append('\n')
        new_lines.append('        outer.addWidget(body, stretch=1)\n')
        new_lines.append('        self._init_status_bar()\n')
        i = 152
        continue

    # 3. Update _connect_signals
    if 'self._workflow_switcher.workflow_changed.connect' in line:
        new_lines.append('        self._sidebar.workflow_changed.connect(self._on_workflow_switched)\n')
        i += 1; continue
    if 'self._workflow_switcher.manage_requested.connect' in line:
        new_lines.append('        self._sidebar.manage_requested.connect(self._on_manage_workflows)\n')
        i += 1; continue
    if 'self._device_bind.device_selected.connect' in line:
        new_lines.append('        self._sidebar.device_selected.connect(self._on_device_selected)\n')
        i += 1; continue
    if 'self._device_bind.rename_requested.connect' in line:
        new_lines.append('        self._sidebar.rename_requested.connect(self._on_device_rename_requested)\n')
        i += 1; continue
    if 'self._step_preview.step_clicked.connect' in line:
        new_lines.append('        self._sidebar.step_clicked.connect(self._on_step_selected)\n')
        i += 1; continue
    if 'self._step_preview.step_order_changed.connect' in line:
        new_lines.append('        self._sidebar.step_order_changed.connect(self._refresh_preview)\n')
        new_lines.append('        self._screenshot_picker.point_selected.connect(self._on_screenshot_point_selected)\n')
        i += 1; continue

    # 4. Add new methods after _on_step_selected
    if 'def _on_step_selected(self, row: int):' in line:
        new_lines.append(line)
        i += 1
        while i < len(lines) and (lines[i].startswith('        ') or lines[i].strip() == ''):
            new_lines.append(lines[i])
            i += 1
        new_lines.append('\n')
        new_lines.append('    def _on_screenshot_point_selected(self, x: int, y: int):\n')
        new_lines.append('        wf_panel = self._panels["workflow_editor"]\n')
        new_lines.append('        if hasattr(wf_panel, "_step_editor"):\n')
        new_lines.append('            wf_panel._step_editor.update_coord_fields(x, y)\n')
        new_lines.append('\n')
        new_lines.append('    def keyPressEvent(self, event):\n')
        new_lines.append('        from PyQt5.QtGui import QKeySequence\n')
        new_lines.append('        if event.matches(QKeySequence("Ctrl+B")):\n')
        new_lines.append('            self._sidebar.toggle()\n')
        new_lines.append('        elif event.matches(QKeySequence("Ctrl+Shift+L")):\n')
        new_lines.append('            self._toggle_log_panel()\n')
        new_lines.append('        else:\n')
        new_lines.append('            super().keyPressEvent(event)\n')
        new_lines.append('\n')
        new_lines.append('    def _toggle_log_panel(self):\n')
        new_lines.append('        sizes = self._main_splitter.sizes()\n')
        new_lines.append('        if sizes[1] > 10:\n')
        new_lines.append('            self._main_splitter.setSizes([sizes[0] + sizes[1], 0])\n')
        new_lines.append('        else:\n')
        new_lines.append('            self._main_splitter.setSizes([620, 180])\n')
        continue

    new_lines.append(line)
    i += 1

with open(filepath, 'w', encoding='utf-8-sig') as f:
    f.writelines(new_lines)

print("main_window.py updated successfully")
