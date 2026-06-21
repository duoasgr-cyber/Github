import copy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from ui.components.step_list_widget import StepListWidget
from ui.components.step_editor import StepEditor


STEP_TYPES = [
    ("tap", "点击", {"type": "tap", "x": 0, "y": 0, "wait_after": 0, "comment": ""}),
    ("long_press", "长按", {"type": "long_press", "x": 0, "y": 0, "duration": 1000, "wait_after": 0, "comment": ""}),
    ("swipe", "滑动", {"type": "swipe", "x1": 0, "y1": 0, "x2": 0, "y2": 0, "duration": 300, "comment": ""}),
    ("keyevent", "按键", {"type": "keyevent", "key": "4", "comment": ""}),
    ("wait", "等待", {"type": "wait", "seconds": 1, "comment": ""}),
    ("wifi", "WiFi控制", {"type": "wifi", "action": "enable", "wait_after": 0, "comment": ""}),
    ("force_stop", "强制停止", {"type": "force_stop", "package": "", "wait_after": 0, "comment": ""}),
    ("launch", "启动应用", {"type": "launch", "package": "", "wait_after": 0, "comment": ""}),
    ("screenshot", "截图", {"type": "screenshot", "save_path": "", "comment": ""}),
    ("pull_file", "拉取文件", {"type": "pull_file", "remote": "", "local": "", "comment": ""}),
    ("delete_file", "删除文件", {"type": "delete_file", "path": "", "comment": ""}),
    ("check_image", "图像匹配", {"type": "check_image", "template": "", "threshold": 0.85, "comment": ""}),
    ("ocr_region", "OCR识别", {"type": "ocr_region", "region": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "comment": ""}),
    ("tap_point", "精确点击", {"type": "tap_point", "x": 0, "y": 0, "wait_after": 0, "comment": ""}),
    ("call_workflow", "调用工作流", {"type": "call_workflow", "workflow": "", "comment": ""}),
    ("condition", "条件判断", {"type": "condition", "check": {}, "then_steps": [], "else_steps": [], "comment": ""}),
    ("loop", "循环", {"type": "loop", "max_count": 10, "condition": {}, "steps": [], "comment": ""}),
    ("input_text", "输入文本", {"type": "input_text", "enabled": True, "display_name": "", "text": "", "comment": ""}),
    ("variable", "变量处理", {"type": "variable", "enabled": True, "display_name": "", "var_name": "", "var_type": "string", "comment": ""}),
    ("adb_command", "ADB命令", {"type": "adb_command", "enabled": True, "display_name": "", "adb_cmd": "", "assign_variable": "", "comment": ""}),
    ("expression", "表达式", {"type": "expression", "expression": "", "assign_variable": "", "comment": ""}),
]

STEP_TYPE_MAP = {t[0]: t for t in STEP_TYPES}

# 步骤类型分类（用于卡片选择弹窗）
STEP_CATEGORIES = [
    {
        "name": "坐标操作",
        "icon": "👆",
        "color": "#1f6feb",
        "types": ["tap", "long_press", "swipe", "tap_point"],
        "descriptions": {
            "tap": "在指定坐标执行单次点击",
            "long_press": "在指定坐标执行长按操作",
            "swipe": "从一个坐标滑动到另一个坐标",
            "tap_point": "精确坐标点击（带校准）",
        }
    },
    {
        "name": "系统控制",
        "icon": "⚙️",
        "color": "#58a6ff",
        "types": ["keyevent", "wait", "wifi", "force_stop", "launch"],
        "descriptions": {
            "keyevent": "发送按键事件（如返回键、Home键）",
            "wait": "等待指定秒数后继续",
            "wifi": "控制设备WiFi开关",
            "force_stop": "强制停止指定应用",
            "launch": "启动指定应用",
        }
    },
    {
        "name": "文件操作",
        "icon": "📁",
        "color": "#d29922",
        "types": ["screenshot", "pull_file", "delete_file"],
        "descriptions": {
            "screenshot": "截取当前屏幕并保存",
            "pull_file": "从设备拉取文件到本地",
            "delete_file": "删除设备上的文件",
        }
    },
    {
        "name": "识别检测",
        "icon": "🔍",
        "color": "#3fb950",
        "types": ["check_image", "ocr_region"],
        "descriptions": {
            "check_image": "图像模板匹配检测",
            "ocr_region": "OCR识别指定区域文字",
        }
    },
    {
        "name": "流程控制",
        "icon": "🔀",
        "color": "#d29922",
        "types": ["condition", "loop", "call_workflow"],
        "descriptions": {
            "condition": "条件分支判断",
            "loop": "循环执行子步骤",
            "call_workflow": "调用另一个工作流",
        }
    },
    {
        "name": "高级操作",
        "icon": "⚡",
        "color": "#a371f7",
        "types": ["input_text", "variable", "adb_command", "expression"],
        "descriptions": {
            "input_text": "输入指定文本内容",
            "variable": "设置或修改变量",
            "adb_command": "执行自定义ADB命令",
            "expression": "计算表达式并赋值",
        }
    },
]


class StepTypeCard(QFrame):
    """步骤类型选择卡片。"""
    clicked_signal = pyqtSignal(str)

    def __init__(self, type_key, type_name, description, icon, color, parent=None):
        super().__init__(parent)
        self._type_key = type_key
        self._type_name = type_name
        self._color = color
        self._hovered = False

        self.setObjectName("stepTypeCard")
        self.setFixedSize(160, 80)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # 图标 + 名称行
        header = QHBoxLayout()
        header.setSpacing(6)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 18px; color: {color};")
        header.addWidget(icon_lbl)
        name_lbl = QLabel(type_name)
        name_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #e6edf3;")
        header.addWidget(name_lbl)
        header.addStretch()
        layout.addLayout(header)

        # 描述
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("font-size: 10px; color: #8b949e;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setMaximumHeight(32)
        layout.addWidget(desc_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_signal.emit(self._type_key)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 背景
        if self._hovered:
            bg = QColor("#21262d")
        else:
            bg = QColor("#161b22")
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(self._color), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        # 左侧颜色条
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawRoundedRect(0, 4, 3, self.height() - 8, 1, 1)
        painter.end()


class StepTypeDialog(QDialog):
    """步骤类型选择弹窗 — 分类网格卡片布局。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择步骤类型")
        self.setMinimumSize(560, 520)
        self._selected_type = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("选择要添加的步骤类型")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(16)

        for category in STEP_CATEGORIES:
            # 分类标题
            cat_header = QHBoxLayout()
            cat_icon = QLabel(category["icon"])
            cat_icon.setStyleSheet("font-size: 16px;")
            cat_header.addWidget(cat_icon)
            cat_name = QLabel(category["name"])
            cat_name.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            cat_name.setStyleSheet(f"color: {category['color']};")
            cat_header.addWidget(cat_name)
            cat_header.addStretch()
            container_layout.addLayout(cat_header)

            # 卡片网格
            grid = QGridLayout()
            grid.setSpacing(8)
            cols = 3
            for i, type_key in enumerate(category["types"]):
                type_info = STEP_TYPE_MAP.get(type_key)
                if not type_info:
                    continue
                type_name = type_info[1]
                desc = category["descriptions"].get(type_key, "")
                card = StepTypeCard(
                    type_key, type_name, desc,
                    category["icon"], category["color"]
                )
                card.clicked_signal.connect(self._on_card_clicked)
                grid.addWidget(card, i // cols, i % cols)
            container_layout.addLayout(grid)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_card_clicked(self, type_key):
        self._selected_type = type_key
        self.accept()

    def get_selected_type(self):
        return self._selected_type


class WorkflowPanel(QWidget):
    workflow_selected = pyqtSignal(str)
    step_selected = pyqtSignal(int)
    step_added = pyqtSignal(int)
    step_deleted = pyqtSignal(int)
    step_moved = pyqtSignal(int, int)

    def __init__(self, config_manager: ConfigManager, screen_capture=None, step_executor=None, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._screen_capture = screen_capture
        self._step_executor = step_executor
        self._current_workflow_name: str = ""
        self._undo_stack = []
        self._redo_stack = []
        self._max_history = 50
        self._setup_ui()
        self._connect_signals()
        
        # 设置步骤执行器到步骤编辑器
        if self._step_executor:
            self._step_editor.set_step_executor(self._step_executor)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ---- 顶部：工作流工具栏（横跨全宽）----
        wf_toolbar = QHBoxLayout()
        wf_toolbar.setSpacing(4)
        self._workflow_combo = QComboBox()
        self._workflow_combo.setFont(QFont("Microsoft YaHei", 10))
        self._workflow_combo.currentIndexChanged.connect(self.on_workflow_selected)
        wf_toolbar.addWidget(self._workflow_combo, stretch=1)

        btn_new_wf = self._create_icon_button("＋", "新建工作流", self._new_workflow)
        wf_toolbar.addWidget(btn_new_wf)
        btn_rename_wf = self._create_icon_button("✎", "重命名工作流", self._rename_workflow)
        wf_toolbar.addWidget(btn_rename_wf)
        btn_delete_wf = self._create_icon_button("🗑", "删除工作流", self._delete_workflow)
        wf_toolbar.addWidget(btn_delete_wf)

        main_layout.addLayout(wf_toolbar)

        # ---- 中部：splitter（步骤列表 | 编辑器）----
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left_widget.setMinimumWidth(200)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._step_list = StepListWidget()
        left_layout.addWidget(self._step_list, stretch=1)

        # 步骤工具栏 — 图标按钮分组
        step_toolbar = QHBoxLayout()
        step_toolbar.setSpacing(2)

        # 添加组
        btn_add = self._create_icon_button("＋", "添加步骤 (Ctrl+N)", self.add_step, "primary")
        step_toolbar.addWidget(btn_add)

        # 分隔线
        step_toolbar.addWidget(self._create_separator())

        # 编辑组
        btn_copy = self._create_icon_button("⧉", "复制步骤 (Ctrl+D)", self.copy_step)
        step_toolbar.addWidget(btn_copy)
        btn_delete = self._create_icon_button("🗑", "删除步骤 (Delete)", self.delete_step, "danger")
        step_toolbar.addWidget(btn_delete)

        # 分隔线
        step_toolbar.addWidget(self._create_separator())

        # 排序组
        btn_up = self._create_icon_button("↑", "上移", self.move_step_up)
        step_toolbar.addWidget(btn_up)
        btn_down = self._create_icon_button("↓", "下移", self.move_step_down)
        step_toolbar.addWidget(btn_down)

        # 分隔线
        step_toolbar.addWidget(self._create_separator())

        # 高级组
        btn_snippet = self._create_icon_button("📋", "代码片段", self._open_snippet_manager)
        step_toolbar.addWidget(btn_snippet)

        # 撤销/重做
        step_toolbar.addWidget(self._create_separator())
        self._btn_undo = self._create_icon_button("↶", "撤销 (Ctrl+Z)", self._undo)
        self._btn_undo.setEnabled(False)
        step_toolbar.addWidget(self._btn_undo)
        self._btn_redo = self._create_icon_button("↷", "重做 (Ctrl+Y)", self._redo)
        self._btn_redo.setEnabled(False)
        step_toolbar.addWidget(self._btn_redo)

        step_toolbar.addStretch()

        left_layout.addLayout(step_toolbar)

        self._step_editor = StepEditor(config_manager=self._config_manager, parent=self)
        self._step_editor.setMinimumHeight(280)

        splitter.addWidget(left_widget)
        splitter.addWidget(self._step_editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 780])
        self._splitter = splitter

        main_layout.addWidget(splitter)

    def _create_icon_button(self, icon, tooltip, callback, style_class=None):
        """创建图标按钮。"""
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setProperty("role", "toolbar-icon")
        if style_class:
            btn.setProperty("class", style_class)
        btn.clicked.connect(callback)
        return btn

    def _create_separator(self):
        """创建工具栏分隔线。"""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("color: #30363d;")
        return sep

    def _connect_signals(self):
        self._step_list.step_clicked.connect(self._on_step_clicked)
        self._step_list.step_order_changed.connect(self._on_step_order_changed)
        self._step_list.step_reset_result_requested.connect(self._on_reset_step_result)
        self._step_editor.step_changed.connect(self._on_step_changed)
        self.step_selected.connect(self._on_step_selected_for_editor)

        # 连接步骤执行器的信号
        if self._step_executor:
            self._step_executor.step_result_updated.connect(self._on_step_result_updated)

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

    def _on_step_order_changed(self):
        if not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        # _move_step 已经交换了 _raw_steps，直接使用即可
        workflow["steps"] = list(self._step_list._raw_steps)
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

    def _on_reset_step_result(self, index: int):
        """重置步骤执行结果"""
        if not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if index >= len(steps):
            return
        steps[index].pop("execution_result", None)
        steps[index].pop("preview", None)
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._step_list.setCurrentRow(index)
        # 如果当前选中的是这个步骤，更新编辑器
        if self._step_editor.get_current_index() == index:
            self._step_editor.load_step(index, steps[index])

    def _on_step_result_updated(self, step_index: int, result: dict):
        """步骤结果更新回调"""
        if not self._current_workflow_name:
            return

        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return

        steps = workflow.get("steps", [])
        if step_index >= len(steps):
            return

        # 更新步骤数据
        steps[step_index].update(result)
        workflow["steps"] = steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)

        # 更新步骤列表中对应项的缩略图和摘要（避免全量刷新）
        self._step_list.update_step_thumbnail(step_index)

        # 如果当前选中的是这个步骤，更新编辑器
        if self._step_editor.get_current_index() == step_index:
            self._step_editor._on_step_result_updated(step_index, result)

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

    def _push_undo(self):
        """保存当前状态到撤销栈。"""
        if not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if workflow:
            self._undo_stack.append(copy.deepcopy(workflow.get("steps", [])))
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
            self._update_undo_redo_buttons()

    def _undo(self):
        if not self._undo_stack or not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        # 当前状态存入 redo
        self._redo_stack.append(copy.deepcopy(workflow.get("steps", [])))
        # 恢复
        old_steps = self._undo_stack.pop()
        workflow["steps"] = old_steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._update_undo_redo_buttons()

    def _redo(self):
        if not self._redo_stack or not self._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(self._current_workflow_name)
        if not workflow:
            return
        self._undo_stack.append(copy.deepcopy(workflow.get("steps", [])))
        new_steps = self._redo_stack.pop()
        workflow["steps"] = new_steps
        self._config_manager.set_workflow(self._current_workflow_name, workflow)
        self.refresh_step_list()
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        self._btn_undo.setEnabled(len(self._undo_stack) > 0)
        self._btn_redo.setEnabled(len(self._redo_stack) > 0)

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
        self._push_undo()
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
        self._push_undo()
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
        self._push_undo()
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
        self._push_undo()
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
        self._push_undo()
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
            QMessageBox.warning(self, "提示", f"工作流'{name}' 已存在")
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
            QMessageBox.warning(self, "提示", f"工作流'{new_name}' 已存在")
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

    def _open_snippet_manager(self):
        try:
            from ui.dialogs.snippet_manager_dialog import SnippetManager, SnippetManagerDialog
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            manager = SnippetManager(base_dir)
            dialog = SnippetManagerDialog(manager, self)
            dialog.snippet_selected.connect(self._on_snippet_selected)
            dialog.exec_()
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to open snippet manager: {e}")

    def _on_snippet_selected(self, snippet_id: str):
        try:
            from ui.dialogs.snippet_manager_dialog import SnippetManager
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            manager = SnippetManager(base_dir)
            steps = manager.instantiate_snippet(snippet_id)
            if steps and self._current_workflow_name:
                wf = self._config_manager.get_workflow(self._current_workflow_name)
                if not wf:
                    return
                self._push_undo()
                wf_steps = wf.get("steps", [])
                for step in steps:
                    wf_steps.append(step)
                wf["steps"] = wf_steps
                self._config_manager.set_workflow(self._current_workflow_name, wf)
                self.load_workflows()
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to use snippet: {e}")

    def get_right_splitter_sizes(self):
        """返回右侧 splitter 尺寸（已移除截图预览区，返回空列表）。"""
        return []

    def set_right_splitter_sizes(self, sizes):
        """恢复右侧 splitter 尺寸（已移除截图预览区，忽略）。"""
        pass

    def get_splitter_sizes(self):
        """返回左侧步骤列表与右侧编辑区之间的水平 splitter 尺寸。"""
        return self._splitter.sizes()

    def set_splitter_sizes(self, sizes):
        """恢复左侧步骤列表与右侧编辑区之间的水平 splitter 尺寸。"""
        if sizes and len(sizes) == 2:
            self._splitter.setSizes(sizes)
