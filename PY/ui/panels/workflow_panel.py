import copy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from ui.components.step_list_widget import StepListWidget
from ui.components.step_editor import StepEditor
from ui.components.screenshot_picker import ScreenshotPicker


STEP_TYPES = [
    ("tap", "点击", {"type": "tap", "x": 0, "y": 0, "comment": "", "wait_after": 0}),
    ("long_press", "长按", {"type": "long_press", "x": 0, "y": 0, "duration": 1000, "comment": "", "wait_after": 0}),
    ("swipe", "滑动", {"type": "swipe", "x1": 0, "y1": 0, "x2": 0, "y2": 0, "duration": 300, "comment": ""}),
    ("keyevent", "按键", {"type": "keyevent", "key": "4", "comment": ""}),
    ("wait", "等待", {"type": "wait", "seconds": 1, "comment": ""}),
    ("wifi", "WiFi控制", {"type": "wifi", "action": "enable", "comment": "", "wait_after": 0}),
    ("force_stop", "强制停止", {"type": "force_stop", "package": "", "comment": "", "wait_after": 0}),
    ("launch", "启动应用", {"type": "launch", "package": "", "comment": "", "wait_after": 0}),
    ("screenshot", "截图", {"type": "screenshot", "save_path": "", "comment": ""}),
    ("pull_file", "拉取文件", {"type": "pull_file", "remote": "", "local": "", "comment": ""}),
    ("delete_file", "删除文件", {"type": "delete_file", "path": "", "comment": ""}),
    ("check_image", "图像匹配", {"type": "check_image", "template": "", "threshold": 0.85, "comment": ""}),
    ("ocr_region", "OCR识别", {"type": "ocr_region", "region": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "comment": ""}),
    ("tap_point", "精确点击", {"type": "tap_point", "x": 0, "y": 0, "comment": "", "wait_after": 0}),
    ("call_workflow", "调用工作流", {"type": "call_workflow", "workflow": "", "comment": ""}),
    ("condition", "条件判断", {"type": "condition", "check": {}, "then_steps": [], "else_steps": [], "comment": ""}),
    ("loop", "循环", {"type": "loop", "max_count": 10, "condition": {}, "steps": [], "comment": ""}),
    ("input_text", "输入文本", {"type": "input_text", "enabled": True, "display_name": "", "text": "", "comment": ""}),
    ("variable", "变量处理", {"type": "variable", "enabled": True, "display_name": "", "var_name": "", "var_type": "string", "var_value": "", "comment": ""}),
    ("adb_command", "ADB命令", {"type": "adb_command", "enabled": True, "display_name": "", "adb_cmd": "", "assign_variable": "", "comment": ""}),
    ("expression", "表达式", {"type": "expression", "expression": "", "assign_variable": "", "comment": ""}),
]

STEP_TYPE_MAP = {t[0]: t for t in STEP_TYPES}


class StepTypeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择步骤类型")
        self.setMinimumSize(300, 400)
        self._selected_type = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._list = StepListWidget()
        for type_key, type_name, _ in STEP_TYPES:
            from PyQt5.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"{type_name} ({type_key})")
            item.setData(Qt.UserRole, type_key)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("纭畾")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_selected_type(self) -> str | None:
        current = self._list.currentItem()
        if current is None:
            return None
        return current.data(Qt.UserRole)


class WorkflowPanel(QWidget):
    workflow_selected = pyqtSignal(str)
    step_selected = pyqtSignal(int)
    step_added = pyqtSignal(int)
    step_deleted = pyqtSignal(int)
    step_moved = pyqtSignal(int, int)

    def __init__(self, config_manager: ConfigManager, screen_capture=None, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._screen_capture = screen_capture
        self._current_workflow_name: str = ""
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        wf_toolbar = QHBoxLayout()
        wf_toolbar.setSpacing(4)
        self._workflow_combo = QComboBox()
        self._workflow_combo.setFont(QFont("Microsoft YaHei", 10))
        self._workflow_combo.currentIndexChanged.connect(self.on_workflow_selected)
        wf_toolbar.addWidget(self._workflow_combo, stretch=1)

        btn_new_wf = QPushButton("新建")
        btn_new_wf.setFixedHeight(28)
        btn_new_wf.clicked.connect(self._new_workflow)
        wf_toolbar.addWidget(btn_new_wf)

        btn_rename_wf = QPushButton("重命名")
        btn_rename_wf.setFixedHeight(28)
        btn_rename_wf.clicked.connect(self._rename_workflow)
        wf_toolbar.addWidget(btn_rename_wf)

        btn_delete_wf = QPushButton("删除")
        btn_delete_wf.setFixedHeight(28)
        btn_delete_wf.clicked.connect(self._delete_workflow)
        wf_toolbar.addWidget(btn_delete_wf)

        left_layout.addLayout(wf_toolbar)

        self._step_list = StepListWidget()
        left_layout.addWidget(self._step_list, stretch=1)

        step_toolbar = QHBoxLayout()
        step_toolbar.setSpacing(4)

        btn_add = QPushButton("添加步骤")
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(self.add_step)
        step_toolbar.addWidget(btn_add)

        btn_delete = QPushButton("删除步骤")
        btn_delete.setFixedHeight(28)
        btn_delete.clicked.connect(self.delete_step)
        step_toolbar.addWidget(btn_delete)

        btn_copy = QPushButton("复制步骤")
        btn_copy.setFixedHeight(28)
        btn_copy.clicked.connect(self.copy_step)
        step_toolbar.addWidget(btn_copy)

        btn_up = QPushButton("上移")
        btn_up.setFixedHeight(28)
        btn_up.clicked.connect(self.move_step_up)
        step_toolbar.addWidget(btn_up)

        btn_down = QPushButton("下移")
        btn_down.setFixedHeight(28)
        btn_down.clicked.connect(self.move_step_down)
        step_toolbar.addWidget(btn_down)
        btn_snippet = QPushButton("片段库")
        btn_snippet.setFixedHeight(28)
        btn_snippet.clicked.connect(self._open_snippet_manager)
        step_toolbar.addWidget(btn_snippet)

        left_layout.addLayout(step_toolbar)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self._step_editor = StepEditor(config_manager=self._config_manager, parent=self)
        right_layout.addWidget(self._step_editor, stretch=3)

        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture, parent=self)
        self._screenshot_picker.setMinimumWidth(240)
        right_layout.addWidget(self._screenshot_picker, stretch=2)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

    def _connect_signals(self):
        self._step_list.step_clicked.connect(self._on_step_clicked)
        self._step_list.step_order_changed.connect(self._on_step_order_changed)
        self._step_editor.step_changed.connect(self._on_step_changed)
        self._screenshot_picker.point_selected.connect(self._on_point_selected)
        self.step_selected.connect(self._on_step_selected_for_editor)

    def _on_step_clicked(self, index: int):
        self.step_selected.emit(index)

    def _on_step_selected_for_editor(self, index: int):
        if index < 0:
            self._step_editor.clear_step()
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            self._step_editor.clear_step()
            return
        steps = workflow.get("steps", [])
        if index >= len(steps):
            self._step_editor.clear_step()
            return
        self._step_editor.load_step(index, steps[index])
        self._screenshot_picker.capture_and_display()

    def _on_step_order_changed(self):
        if not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        old_steps = workflow.get("steps", [])
        new_order = []
        for i in range(self._step_list.count()):
            item = self._step_list.item(i)
            original_index = i
            if original_index < len(old_steps):
                new_order.append(old_steps[original_index])
        workflow["steps"] = new_order
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()

    def _on_step_changed(self, updated_step: dict):
        index = self._step_editor.get_current_index()
        if index < 0 or not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if index >= len(steps):
            return
        steps[index] = updated_step
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._step_list.setCurrentRow(index)

    def _on_point_selected(self, x: int, y: int):
        self._step_editor.update_coord_fields(x, y)

    def load_workflows(self):
        self._workflow_combo.blockSignals(True)
        self._workflow_combo.clear()
        workflows = self._config_manager.get_all_workflows()
        for name in workflows:
            self._workflow_combo.addItem(name)
        self._workflow_combo.blockSignals(False)
        if self._workflow_combo.count() > 0:
            self._workflow_combo.setCurrentIndex(0)
            self.on_workflow_selected(0)

    def on_workflow_selected(self, index: int):
        if index < 0:
            self._current_workflow_name = ""
            self._step_list.clear()
            self._step_editor.clear_step()
            return
        name = self._workflow_combo.itemText(index)
        self._current_workflow_name = name
        self.refresh_step_list()
        self._step_editor.clear_step()
        self.workflow_selected.emit(name)

    def add_step(self):
        if not self._current_workflow_name:
            return
        dialog = StepTypeDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        selected_type = dialog.get_selected_type()
        if selected_type is None:
            return
        type_info = STEP_TYPE_MAP.get(selected_type)
        if type_info is None:
            return
        new_step = copy.deepcopy(type_info[2])
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            workflow = {"description": "", "device_resolution": {"width": 2400, "height": 1080}, "steps": []}
        steps = workflow.get("steps", [])
        steps.append(new_step)
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        new_index = len(steps) - 1
        self._step_list.setCurrentRow(new_index)
        self.step_added.emit(new_index)

    def append_recorded_steps(self, steps: list) -> int:
        """追加录制的步骤到当前工作流，返回新增起始索引（-1 表示未追加）。"""
        if not self._current_workflow_name or not steps:
            return -1
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            workflow = {"description": "", "device_resolution": {"width": 2400, "height": 1080}, "steps": []}
        existing = workflow.get("steps", [])
        start_index = len(existing)
        existing.extend(copy.deepcopy(steps))
        workflow["steps"] = existing
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        return start_index

    def get_device_resolution(self) -> tuple:
        """返回当前工作流的设备分辨率 (width, height)，用于录制坐标基准。"""
        if not self._current_workflow_name:
            return (2400, 1080)
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return (2400, 1080)
        dr = workflow.get("device_resolution", {})
        return (dr.get("width", 2400), dr.get("height", 1080))

    def set_editing_locked(self, locked: bool) -> None:
        """录制期间锁定步骤编辑，防止并发修改。"""
        self._step_list.setEnabled(not locked)
        # add/delete/copy/move 等按钮如有也可在此禁用

    def delete_step(self):
        if not self._current_workflow_name:
            return
        row = self._step_list.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(
            self, "删除步骤", "确定要删除选中的步骤吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if row >= len(steps):
            return
        steps.pop(row)
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._step_editor.clear_step()
        self.step_deleted.emit(row)

    def copy_step(self):
        if not self._current_workflow_name:
            return
        row = self._step_list.currentRow()
        if row < 0:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if row >= len(steps):
            return
        copied = copy.deepcopy(steps[row])
        steps.insert(row + 1, copied)
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._step_list.setCurrentRow(row + 1)
        self.step_added.emit(row + 1)

    def move_step_up(self):
        if not self._current_workflow_name:
            return
        row = self._step_list.currentRow()
        if row <= 0:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if row >= len(steps):
            return
        steps[row - 1], steps[row] = steps[row], steps[row - 1]
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        old_index = row
        new_index = row - 1
        self.refresh_step_list()
        self._step_list.setCurrentRow(new_index)
        self.step_moved.emit(old_index, new_index)

    def move_step_down(self):
        if not self._current_workflow_name:
            return
        row = self._step_list.currentRow()
        if row < 0:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if row >= len(steps) - 1:
            return
        steps[row], steps[row + 1] = steps[row + 1], steps[row]
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        old_index = row
        new_index = row + 1
        self.refresh_step_list()
        self._step_list.setCurrentRow(new_index)
        self.step_moved.emit(old_index, new_index)

    def get_current_workflow(self) -> str:
        return self._current_workflow_name

    def get_current_step_index(self) -> int:
        return self._step_list.currentRow()

    def refresh_step_list(self):
        if not self._current_workflow_name:
            self._step_list.clear()
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            self._step_list.clear()
            return
        steps = workflow.get("steps", [])
        self._step_list.load_steps(steps)

    workflow_saved = pyqtSignal(str)

    def _new_workflow(self):
        name, ok = QInputDialog.getText(self, "新建工作流", "工作流名称")
        if not ok or not name.strip():
            return
        name = name.strip()
        workflows = self._config_manager.get_all_workflows()
        if name in workflows:
            QMessageBox.warning(self, "提示", f"工作流 '{name}' 已存在")
            return
        workflow = {
            "description": "",
            "device_resolution": {"width": 2400, "height": 1080},
            "steps": [],
        }
        self._config_manager.set_workflow(name, workflow)
        self.load_workflows()
        index = self._workflow_combo.findText(name)
        if index >= 0:
            self._workflow_combo.setCurrentIndex(index)

    def _rename_workflow(self):
        if not self._current_workflow_name:
            return
        old_name = self._current_workflow_name
        new_name, ok = QInputDialog.getText(
            self, "重命名工作流", "新名称", text=old_name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == old_name:
            return
        workflows = self._config_manager.get_all_workflows()
        if new_name in workflows:
            QMessageBox.warning(self, "提示", f"工作流 '{new_name}' 已存在")
            return
        workflow_data = workflows.get(old_name, {})
        self._config_manager.delete_workflow(old_name)
        self._config_manager.set_workflow(new_name, workflow_data)
        self.load_workflows()
        index = self._workflow_combo.findText(new_name)
        if index >= 0:
            self._workflow_combo.setCurrentIndex(index)

    def _delete_workflow(self):
        if not self._current_workflow_name:
            return
        reply = QMessageBox.question(
            self,
            "删除工作流",
            f"确定要删除工作流 '{self._current_workflow_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._config_manager.delete_workflow(self._current_workflow_name)
        self._current_workflow_name = ""
        self._step_editor.clear_step()
        self.load_workflows()

