import copy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
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


# 主流程允许的步骤类型：仅编排类（调用工作流/条件/循环/等待）
MAIN_FLOW_STEP_TYPES = [
    ("call_workflow", "调用工作流", {"type": "call_workflow", "workflow": "", "comment": ""}),
    ("condition", "条件判断", {
        "type": "condition", "check": {},
        "then_mode": "内嵌步骤", "then_steps": [], "then_workflow": "",
        "else_mode": "内嵌步骤", "else_steps": [], "else_workflow": "",
        "comment": "",
    }),
    ("loop", "循环", {"type": "loop", "max_count": 10, "condition": {}, "steps": [], "comment": ""}),
    ("wait", "等待", {"type": "wait", "seconds": 1, "comment": ""}),
]

MAIN_FLOW_TYPE_MAP = {t[0]: t for t in MAIN_FLOW_STEP_TYPES}


class MainFlowStepTypeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择主流程步骤类型")
        self.setMinimumSize(300, 250)
        self._selected_type = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._list = StepListWidget()
        from PyQt5.QtWidgets import QListWidgetItem
        for type_key, type_name, _ in MAIN_FLOW_STEP_TYPES:
            item = QListWidgetItem("{} ({})".format(type_name, type_key))
            item.setData(Qt.UserRole, type_key)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_selected_type(self):
        current = self._list.currentItem()
        if current is None:
            return None
        return current.data(Qt.UserRole)


class MainFlowPanel(QWidget):
    """主流程编排面板。

    复用 StepListWidget + StepEditor 编辑 main_flow 数据。
    与普通 WorkflowPanel 的区别：
    - 数据源是 ConfigManager.get_main_flow() / set_main_flow()
    - 步骤类型限定为编排类（call_workflow / condition / loop / wait）
    - 无工作流切换器（主流程全局唯一）
    """

    main_flow_saved = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, screen_capture=None, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._screen_capture = screen_capture
        self._main_flow = {"description": "", "steps": []}
        self._setup_ui()
        self._connect_signals()
        self.load_main_flow()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧：描述 + 步骤列表 + 工具栏 + 编辑器
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # 主流程描述
        desc_layout = QHBoxLayout()
        desc_label = QPushButton("主流程说明")
        desc_label.setFixedHeight(28)
        desc_label.setStyleSheet(
            "QPushButton { text-align: left; padding-left: 8px; "
            "background: #161b22; border: 1px solid #30363d; border-radius: 4px; "
            "color: #e6edf3; font-weight: bold; }"
        )
        desc_label.clicked.connect(self._edit_description)
        self._desc_btn = desc_label
        desc_layout.addWidget(desc_label)
        left_layout.addLayout(desc_layout)

        # 步骤列表
        self._step_list = StepListWidget()
        left_layout.addWidget(self._step_list, stretch=1)

        # 步骤工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        btn_add = QPushButton("添加步骤")
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(self._add_step)
        toolbar.addWidget(btn_add)

        btn_delete = QPushButton("删除步骤")
        btn_delete.setFixedHeight(28)
        btn_delete.clicked.connect(self._delete_step)
        toolbar.addWidget(btn_delete)

        btn_copy = QPushButton("复制步骤")
        btn_copy.setFixedHeight(28)
        btn_copy.clicked.connect(self._copy_step)
        toolbar.addWidget(btn_copy)

        btn_up = QPushButton("上移")
        btn_up.setFixedHeight(28)
        btn_up.clicked.connect(self._move_up)
        toolbar.addWidget(btn_up)

        btn_down = QPushButton("下移")
        btn_down.setFixedHeight(28)
        btn_down.clicked.connect(self._move_down)
        toolbar.addWidget(btn_down)

        btn_save = QPushButton("保存")
        btn_save.setFixedHeight(28)
        btn_save.setStyleSheet(
            "QPushButton { background-color: #238636; color: white; "
            "border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #2ea043; }"
        )
        btn_save.clicked.connect(self._save)
        toolbar.addWidget(btn_save)

        left_layout.addLayout(toolbar)

        # 步骤编辑器
        self._step_editor = StepEditor(config_manager=self._config_manager, parent=self)
        left_layout.addWidget(self._step_editor, stretch=1)

        # 右侧：投屏窗口（用于选点）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self._screenshot_picker = ScreenshotPicker(screen_capture=self._screen_capture, parent=self)
        self._screenshot_picker.setMinimumWidth(320)
        right_layout.addWidget(self._screenshot_picker)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter)

    def _connect_signals(self):
        self._step_list.step_clicked.connect(self._on_step_clicked)
        self._step_list.step_order_changed.connect(self._on_step_order_changed)
        self._step_editor.step_changed.connect(self._on_step_changed)
        self._step_editor.coord_pick_requested.connect(self._on_coord_pick_requested)
        self._screenshot_picker.point_selected.connect(self._on_point_selected)

    def load_main_flow(self):
        self._main_flow = self._config_manager.get_main_flow()
        self._refresh_step_list()
        self._update_desc_button()
        self._step_editor.clear_step()

    def _refresh_step_list(self):
        steps = self._main_flow.get("steps", [])
        self._step_list.load_steps(steps)

    def _update_desc_button(self):
        desc = self._main_flow.get("description", "")
        if desc:
            self._desc_btn.setText("主流程说明: {}".format(desc))
        else:
            self._desc_btn.setText("主流程说明 (点击编辑)")

    def _edit_description(self):
        old_desc = self._main_flow.get("description", "")
        text, ok = QInputDialog.getText(
            self, "编辑主流程说明", "说明:", text=old_desc
        )
        if ok:
            self._main_flow["description"] = text
            self._update_desc_button()

    def _on_step_clicked(self, index: int):
        if index < 0:
            self._step_editor.clear_step()
            return
        steps = self._main_flow.get("steps", [])
        if index >= len(steps):
            self._step_editor.clear_step()
            return
        self._step_editor.load_step(index, steps[index])
        self._screenshot_picker.capture_and_display()

    def _on_step_order_changed(self):
        old_steps = self._main_flow.get("steps", [])
        new_order = []
        for i in range(self._step_list.count()):
            if i < len(old_steps):
                new_order.append(old_steps[i])
        self._main_flow["steps"] = new_order
        self._refresh_step_list()

    def _on_step_changed(self, updated_step: dict):
        index = self._step_editor.get_current_index()
        if index < 0:
            return
        steps = self._main_flow.get("steps", [])
        if index >= len(steps):
            return
        steps[index] = updated_step
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        self._step_list.setCurrentRow(index)

    def _on_point_selected(self, x: int, y: int):
        self._step_editor.update_coord_fields(x, y)

    def _on_coord_pick_requested(self, group_key: str):
        if not self._screenshot_picker._live_mode:
            self._screenshot_picker.capture_and_display()
        self._screenshot_picker.enter_pick_mode(group_key)

    def _add_step(self):
        dialog = MainFlowStepTypeDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        selected_type = dialog.get_selected_type()
        if selected_type is None:
            return
        type_info = MAIN_FLOW_TYPE_MAP.get(selected_type)
        if type_info is None:
            return
        new_step = copy.deepcopy(type_info[2])
        steps = self._main_flow.get("steps", [])
        steps.append(new_step)
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        new_index = len(steps) - 1
        self._step_list.setCurrentRow(new_index)

    def _delete_step(self):
        row = self._step_list.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(
            self, "删除步骤", "确定要删除选中的步骤吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        steps = self._main_flow.get("steps", [])
        if row >= len(steps):
            return
        steps.pop(row)
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        self._step_editor.clear_step()

    def _copy_step(self):
        row = self._step_list.currentRow()
        if row < 0:
            return
        steps = self._main_flow.get("steps", [])
        if row >= len(steps):
            return
        copied = copy.deepcopy(steps[row])
        steps.insert(row + 1, copied)
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        self._step_list.setCurrentRow(row + 1)

    def _move_up(self):
        row = self._step_list.currentRow()
        if row <= 0:
            return
        steps = self._main_flow.get("steps", [])
        if row >= len(steps):
            return
        steps[row - 1], steps[row] = steps[row], steps[row - 1]
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        self._step_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._step_list.currentRow()
        steps = self._main_flow.get("steps", [])
        if row < 0 or row >= len(steps) - 1:
            return
        steps[row + 1], steps[row] = steps[row], steps[row + 1]
        self._main_flow["steps"] = steps
        self._refresh_step_list()
        self._step_list.setCurrentRow(row + 1)

    def _save(self):
        self._config_manager.set_main_flow(self._main_flow)
        self.main_flow_saved.emit()
        QMessageBox.information(self, "保存成功", "主流程已保存。")
