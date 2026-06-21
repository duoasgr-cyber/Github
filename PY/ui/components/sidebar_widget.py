import json
import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
)
from PyQt5.QtGui import QFont

from ui.components.device_bind_widget import DeviceBindWidget
from ui.components.workflow_switcher import WorkflowSwitcher
from ui.components.step_list_widget import StepListWidget


class SidebarWidget(QWidget):
    """可折叠侧边栏：设备信息 + 方案切换 + 步骤预览。"""

    step_clicked = pyqtSignal(int)
    step_order_changed = pyqtSignal()
    workflow_changed = pyqtSignal(str)
    manage_requested = pyqtSignal()
    device_selected = pyqtSignal(str, str)
    rename_requested = pyqtSignal(str, str)
    open_mirror_requested = pyqtSignal(str)  # 新增：打开高清投屏

    EXPANDED_WIDTH = 260
    COLLAPSED_WIDTH = 48

    def __init__(self, device_manager, adb_core, config_manager,
                 ui_state_path=None, parent=None):
        super().__init__(parent)
        self._device_manager = device_manager
        self._adb_core = adb_core
        self._config_manager = config_manager
        self._ui_state_path = ui_state_path
        self._collapsed = False
        self._animation = None

        self._load_state()
        self._init_ui()
        self._connect_signals()

        if self._collapsed:
            self._apply_collapsed_state(animated=False)

    # ---- UI 构建 -----------------------------------------------------------

    def _init_ui(self):
        self.setObjectName("sidebar")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 折叠按钮
        self._btn_toggle = QPushButton("◀")
        self._btn_toggle.setObjectName("sidebarToggle")
        self._btn_toggle.setFixedHeight(32)
        self._btn_toggle.setCursor(Qt.PointingHandCursor)
        self._btn_toggle.clicked.connect(self.toggle)
        main_layout.addWidget(self._btn_toggle)

        # 内容区
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self._device_bind = DeviceBindWidget(self._device_manager, self._adb_core)
        self._workflow_switcher = WorkflowSwitcher(self._config_manager)
        self._step_preview = StepListWidget()
        self._step_preview.setMinimumHeight(160)

        content_layout.addWidget(self._device_bind)
        content_layout.addWidget(self._workflow_switcher)
        content_layout.addWidget(self._step_preview, stretch=1)

        main_layout.addWidget(self._content)

        # 折叠时的迷你信息区
        self._mini_info = QWidget()
        mini_layout = QVBoxLayout(self._mini_info)
        mini_layout.setContentsMargins(4, 8, 4, 8)
        mini_layout.setSpacing(6)
        mini_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self._mini_device_dot = QLabel("●")
        self._mini_device_dot.setAlignment(Qt.AlignCenter)
        self._mini_device_dot.setStyleSheet("color: #8b949e; font-size: 16px;")
        self._mini_device_dot.setToolTip("设备状态")

        self._mini_step_count = QLabel("0步")
        self._mini_step_count.setAlignment(Qt.AlignCenter)
        self._mini_step_count.setStyleSheet("color: #8b949e; font-size: 10px;")
        self._mini_step_count.setToolTip("步骤数量")

        mini_layout.addWidget(self._mini_device_dot)
        mini_layout.addWidget(self._mini_step_count)
        mini_layout.addStretch()

        self._mini_info.setVisible(False)
        main_layout.addWidget(self._mini_info)

        self.setFixedWidth(self.EXPANDED_WIDTH if not self._collapsed else self.COLLAPSED_WIDTH)

    def _connect_signals(self):
        self._device_bind.device_selected.connect(self.device_selected.emit)
        self._device_bind.rename_requested.connect(self.rename_requested.emit)
        self._device_bind.open_mirror_requested.connect(self.open_mirror_requested.emit)
        self._workflow_switcher.workflow_changed.connect(self._on_workflow_changed)
        self._workflow_switcher.manage_requested.connect(self.manage_requested.emit)
        self._step_preview.step_clicked.connect(self.step_clicked.emit)
        self._step_preview.step_order_changed.connect(self.step_order_changed.emit)

    # ---- 公开接口 -----------------------------------------------------------

    def set_mirror_active(self, active: bool):
        """更新投屏按钮状态。"""
        self._device_bind.set_mirror_active(active)

    @property
    def device_bind(self):
        return self._device_bind

    @property
    def workflow_switcher(self):
        return self._workflow_switcher

    @property
    def step_preview(self):
        return self._step_preview

    def toggle(self):
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def is_collapsed(self):
        return self._collapsed

    def update_mini_info(self):
        """更新折叠模式下的迷你信息。"""
        serial = self._device_bind._bound_serial
        online = self._device_bind._is_device_online()
        if online:
            self._mini_device_dot.setStyleSheet("color: #3fb950; font-size: 16px;")
            self._mini_device_dot.setToolTip(f"设备: {serial} (在线)")
        elif serial:
            self._mini_device_dot.setStyleSheet("color: #d29922; font-size: 16px;")
            self._mini_device_dot.setToolTip(f"设备: {serial} (离线)")
        else:
            self._mini_device_dot.setStyleSheet("color: #8b949e; font-size: 16px;")
            self._mini_device_dot.setToolTip("未选择设备")

        count = self._step_preview.count()
        self._mini_step_count.setText(f"{count}步")
        wf = self._workflow_switcher.current_workflow()
        self._mini_step_count.setToolTip(f"方案: {wf or '无'}")

    # ---- 内部逻辑 -----------------------------------------------------------

    def _on_workflow_changed(self, name):
        self.update_mini_info()
        self.workflow_changed.emit(name)

    def _collapse(self):
        self._collapsed = True
        self._apply_collapsed_state(animated=True)
        self._save_state()

    def _expand(self):
        self._collapsed = False
        self._apply_expanded_state(animated=True)
        self._save_state()

    def _apply_collapsed_state(self, animated=True):
        self._btn_toggle.setText("▶")
        self._content.setVisible(False)
        self._mini_info.setVisible(True)
        self.update_mini_info()

        target = self.COLLAPSED_WIDTH
        if animated:
            self._animate_width(target)
        else:
            self.setFixedWidth(target)

    def _apply_expanded_state(self, animated=True):
        self._btn_toggle.setText("◀")
        self._content.setVisible(True)
        self._mini_info.setVisible(False)

        target = self.EXPANDED_WIDTH
        if animated:
            self._animate_width(target)
        else:
            self.setFixedWidth(target)

    def _animate_width(self, target_width):
        anim = QPropertyAnimation(self, b"maximumWidth")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        current = self.width()
        anim.setStartValue(current)
        anim.setEndValue(target_width)
        anim.finished.connect(lambda: self.setFixedWidth(target_width))
        anim.start()
        self._animation = anim  # 保持引用，防止被 GC

    # ---- 状态持久化 ---------------------------------------------------------

    def _load_state(self):
        if not self._ui_state_path:
            return
        try:
            if os.path.exists(self._ui_state_path):
                with open(self._ui_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._collapsed = data.get("sidebar_collapsed", False)
        except Exception:
            self._collapsed = False

    def _save_state(self):
        if not self._ui_state_path:
            return
        try:
            data = {}
            if os.path.exists(self._ui_state_path):
                with open(self._ui_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["sidebar_collapsed"] = self._collapsed
            os.makedirs(os.path.dirname(self._ui_state_path), exist_ok=True)
            tmp = self._ui_state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._ui_state_path)
        except Exception:
            pass
