import copy

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.config_manager import ConfigManager


class MergeWorkflowsDialog(QDialog):
    """把多个方案按指定顺序整合成一个新的大方案。

    选中的源方案会按列表中的顺序拼接步骤，生成新工作流，
    并可选删除源方案（移动模式）。当前方案默认被选中，
    用户可通过上下移动把它放到期望位置。
    """

    def __init__(self, config_manager: ConfigManager, current_workflow: str = "", parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._current_workflow = current_workflow
        self._merged_name = ""
        self.setWindowTitle("整合成大方案")
        self.setMinimumSize(480, 520)
        self._setup_ui()
        self._load_workflows()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("选择要整合的方案并调整顺序")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)

        hint = QLabel("勾选需要整合的方案，用 ↑/↓ 调整顺序。当前方案默认被选中。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(hint)

        # 方案列表（可勾选、可单选排序）
        self._list = QListWidget()
        self._list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self._list, stretch=1)

        # 排序按钮
        order_layout = QHBoxLayout()
        self._btn_up = QPushButton("↑ 上移")
        self._btn_up.setToolTip("上移选中的方案")
        self._btn_up.clicked.connect(self._move_up)
        order_layout.addWidget(self._btn_up)

        self._btn_down = QPushButton("↓ 下移")
        self._btn_down.setToolTip("下移选中的方案")
        self._btn_down.clicked.connect(self._move_down)
        order_layout.addWidget(self._btn_down)

        self._btn_check_all = QPushButton("全选")
        self._btn_check_all.clicked.connect(self._check_all)
        order_layout.addWidget(self._btn_check_all)

        self._btn_uncheck_all = QPushButton("全不选")
        self._btn_uncheck_all.clicked.connect(self._uncheck_all)
        order_layout.addWidget(self._btn_uncheck_all)

        order_layout.addStretch()
        layout.addLayout(order_layout)

        # 新方案名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("新方案名称:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例如: master_programme")
        name_layout.addWidget(self._name_edit, stretch=1)
        layout.addLayout(name_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton("确认整合")
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _load_workflows(self):
        workflows = self._config_manager.get_all_workflows()
        for name in sorted(workflows.keys()):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if name == self._current_workflow else Qt.Unchecked)
            item.setData(Qt.UserRole, name)
            self._list.addItem(item)

        if self._current_workflow and self._current_workflow in workflows:
            default_name = f"{self._current_workflow}_merged"
            counter = 1
            base = default_name
            while default_name in workflows:
                default_name = f"{base}_{counter}"
                counter += 1
            self._name_edit.setText(default_name)

    def _selected_items(self):
        """返回按列表顺序排列的已勾选项目。"""
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item)
        return result

    def _move_up(self):
        row = self._list.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)

    def _move_down(self):
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        self._swap_rows(row, row + 1)

    def _swap_rows(self, row_a: int, row_b: int):
        item_a = self._list.takeItem(row_a)
        item_b = self._list.takeItem(row_b)
        self._list.insertItem(row_a, item_b)
        self._list.insertItem(row_b, item_a)
        self._list.setCurrentRow(row_b)

    def _check_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Checked)

    def _uncheck_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Unchecked)

    def _on_ok(self):
        selected = self._selected_items()
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个要整合的方案")
            return

        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "提示", "请输入新方案名称")
            return

        workflows = self._config_manager.get_all_workflows()
        if new_name in workflows:
            QMessageBox.warning(self, "提示", f"方案 '{new_name}' 已存在")
            return

        merged_steps = []
        merged_resolution = None
        source_names = []
        for item in selected:
            name = item.data(Qt.UserRole)
            wf = workflows.get(name, {})
            steps = wf.get("steps", [])
            merged_steps.extend(copy.deepcopy(steps))
            source_names.append(name)
            if merged_resolution is None:
                merged_resolution = wf.get("device_resolution")

        if merged_resolution is None:
            merged_resolution = {"width": 2400, "height": 1080}

        new_workflow = {
            "description": f"整合方案: {', '.join(source_names)}",
            "device_resolution": merged_resolution,
            "steps": merged_steps,
        }

        self._config_manager.set_workflow(new_name, new_workflow)

        # 移动模式：删除源方案
        for name in source_names:
            self._config_manager.delete_workflow(name)

        self._merged_name = new_name
        self.accept()

    def get_merged_name(self) -> str:
        return self._merged_name
