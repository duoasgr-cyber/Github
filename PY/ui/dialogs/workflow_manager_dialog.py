import copy
import json
import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox, QFileDialog, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from core.config_manager import ConfigManager

# 预设方案模板
PRESET_WORKFLOWS = {
    "空方案": {"description": "", "device_resolution": {"width": 2400, "height": 1080}, "steps": []},
    "购买流程模板": {
        "description": "标准购买流程",
        "device_resolution": {"width": 2400, "height": 1080},
        "steps": [
            {"type": "launch", "package": "com.tencent.tmgp.dfm", "comment": "启动游戏", "wait_after": 5000},
            {"type": "wait", "seconds": 3, "comment": "等待加载"},
        ],
    },
}


class WorkflowManagerDialog(QDialog):
    """方案管理弹窗：新建（含预设）、删除、重命名、导入、导出。"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self.setWindowTitle("方案管理")
        self.setMinimumSize(500, 400)
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()

        btn_new = QPushButton("新建")
        btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(btn_new)

        btn_preset = QPushButton("从预设新建")
        btn_preset.clicked.connect(self._on_new_preset)
        btn_row.addWidget(btn_preset)

        btn_rename = QPushButton("重命名")
        btn_rename.clicked.connect(self._on_rename)
        btn_row.addWidget(btn_rename)

        btn_delete = QPushButton("删除")
        btn_delete.setProperty("class", "danger")
        btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(btn_delete)

        btn_import = QPushButton("导入")
        btn_import.clicked.connect(self._on_import)
        btn_row.addWidget(btn_import)

        btn_export = QPushButton("导出")
        btn_export.clicked.connect(self._on_export)
        btn_row.addWidget(btn_export)

        layout.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

    def _refresh_list(self):
        self._list.clear()
        workflows = self._config_manager.get_all_workflows()
        for name in sorted(workflows.keys()):
            desc = workflows[name].get("description", "")
            text = f"{name}" + (f"  —  {desc}" if desc else "")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, name)
            self._list.addItem(item)

    def _selected_name(self):
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _on_new(self):
        name, ok = QInputDialog.getText(self, "新建方案", "方案名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self._config_manager.get_workflow(name):
            QMessageBox.warning(self, "提示", f"方案 '{name}' 已存在")
            return
        self._config_manager.set_workflow(name, {"description": "", "device_resolution": {"width": 2400, "height": 1080}, "steps": []})
        self._refresh_list()

    def _on_new_preset(self):
        items = list(PRESET_WORKFLOWS.keys())
        item, ok = QInputDialog.getItem(self, "从预设新建", "选择预设:", items, 0, False)
        if not ok or not item:
            return
        template = copy.deepcopy(PRESET_WORKFLOWS[item])
        name, ok2 = QInputDialog.getText(self, "方案名称", "名称:", text=item)
        if not ok2 or not name.strip():
            return
        name = name.strip()
        if self._config_manager.get_workflow(name):
            QMessageBox.warning(self, "提示", f"方案 '{name}' 已存在")
            return
        self._config_manager.set_workflow(name, template)
        self._refresh_list()

    def _on_rename(self):
        old = self._selected_name()
        if not old:
            return
        new, ok = QInputDialog.getText(self, "重命名方案", "新名称:", text=old)
        if not ok or not new.strip() or new.strip() == old:
            return
        new = new.strip()
        if self._config_manager.get_workflow(new):
            QMessageBox.warning(self, "提示", f"方案 '{new}' 已存在")
            return
        data = self._config_manager.get_workflow(old)
        self._config_manager.delete_workflow(old)
        self._config_manager.set_workflow(new, data)
        self._refresh_list()

    def _on_delete(self):
        name = self._selected_name()
        if not name:
            return
        if QMessageBox.question(self, "删除方案", f"确认删除方案 '{name}'？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._config_manager.delete_workflow(name)
        self._refresh_list()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入方案", "", "JSON 文件 (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))
            return
        name = os.path.splitext(os.path.basename(path))[0]
        if self._config_manager.get_workflow(name):
            name2, ok = QInputDialog.getText(self, "方案已存在", "请输入新名称:", text=name + "_imported")
            if not ok or not name2.strip():
                return
            name = name2.strip()
        self._config_manager.set_workflow(name, data)
        self._refresh_list()

    def _on_export(self):
        name = self._selected_name()
        if not name:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出方案", f"{name}.json", "JSON 文件 (*.json)")
        if not path:
            return
        data = self._config_manager.get_workflow(name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))