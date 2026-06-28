import json
import copy
import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QGroupBox, QScrollArea,
    QPushButton, QFrame
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step type field configuration table
# ---------------------------------------------------------------------------
STEP_TYPE_FIELDS = {
    "tap": {
        "required": ["x", "y"],
        "optional": ["wait_after"],
        "field_types": {
            "x": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "y": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "long_press": {
        "required": ["x", "y", "duration"],
        "optional": ["wait_after"],
        "field_types": {
            "x": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "y": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "duration": ("doublespinbox", {"min": 0, "max": 60000, "decimals": 0, "default": 1000, "suffix": " 毫秒"}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "swipe": {
        "required": ["x1", "y1", "x2", "y2"],
        "optional": ["duration"],
        "field_types": {
            "x1": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "y1": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "x2": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "y2": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "duration": ("doublespinbox", {"min": 0, "max": 60000, "decimals": 0, "default": 300, "suffix": " 毫秒"}),
        }
    },
    "tap_point": {
        "required": ["x", "y"],
        "optional": ["wait_after"],
        "field_types": {
            "x": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "y": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "keyevent": {
        "required": ["key"],
        "optional": [],
        "field_types": {
            "key": ("combobox", {"items": ["4", "3", "82", "26", "24", "25", "66", "61", "62", "67", "112", "111"],
                                  "labels": ["返回键(4)", "Home键(3)", "菜单键(82)", "电源键(26)", "音量+(24)", "音量-(25)", "回车键(66)", "Tab键(61)", "空格键(62)", "退格键(67)", "F1(112)", "F2(111)"],
                                  "editable": True, "default": "4"}),
        }
    },
    "wait": {
        "required": ["seconds"],
        "optional": [],
        "field_types": {
            "seconds": ("doublespinbox", {"min": 0, "max": 3600, "decimals": 1, "default": 1, "suffix": " 秒"}),
        }
    },
    "wifi": {
        "required": ["action"],
        "optional": ["wait_after"],
        "field_types": {
            "action": ("combobox", {"items": ["enable", "disable"], "labels": ["开启", "关闭"], "default": "enable"}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "force_stop": {
        "required": ["package"],
        "optional": ["wait_after"],
        "field_types": {
            "package": ("lineedit", {"placeholder": "如 com.example.app", "default": ""}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "launch": {
        "required": ["package"],
        "optional": ["wait_after"],
        "field_types": {
            "package": ("lineedit", {"placeholder": "如 com.example.app", "default": ""}),
            "wait_after": ("doublespinbox", {"min": 0, "max": 300, "decimals": 1, "default": 0, "suffix": " 秒"}),
        }
    },
    "screenshot": {
        "required": ["save_path"],
        "optional": [],
        "field_types": {
            "save_path": ("lineedit", {"placeholder": "如 /sdcard/screenshot.png", "default": ""}),
        }
    },
    "pull_file": {
        "required": ["remote", "local"],
        "optional": [],
        "field_types": {
            "remote": ("lineedit", {"placeholder": "设备路径 如 /sdcard/file", "default": ""}),
            "local": ("lineedit", {"placeholder": "本地路径 如 C:/files/file", "default": ""}),
        }
    },
    "delete_file": {
        "required": ["path"],
        "optional": [],
        "field_types": {
            "path": ("lineedit", {"placeholder": "设备文件路径 如 /sdcard/file", "default": ""}),
        }
    },
    "check_image": {
        "required": ["template", "threshold"],
        "optional": [],
        "field_types": {
            "template": ("lineedit", {"placeholder": "模板图片文件名 如 button.png", "default": ""}),
            "threshold": ("doublespinbox", {"min": 0.0, "max": 1.0, "decimals": 2, "default": 0.85, "single_step": 0.05}),
        }
    },
    "ocr_region": {
        "required": ["region"],
        "optional": [],
        "field_types": {
            "region": ("region_editor", {"default": {"left": 0, "top": 0, "right": 0, "bottom": 0}}),
        }
    },
    "call_workflow": {
        "required": ["workflow"],
        "optional": [],
        "field_types": {
            "workflow": ("combobox", {"items": [], "editable": True, "default": ""}),
        }
    },
    "condition": {
        "required": ["check"],
        "optional": ["then_steps", "else_steps"],
        "field_types": {
            "check": ("lineedit", {"placeholder": "条件 JSON", "default": "{}"}),
            "then_steps": ("lineedit", {"placeholder": "条件为真时执行的步骤", "default": "[]"}),
            "else_steps": ("lineedit", {"placeholder": "条件为假时执行的步骤", "default": "[]"}),
        }
    },
    "loop": {
        "required": ["max_count", "condition"],
        "optional": ["steps"],
        "field_types": {
            "max_count": ("spinbox", {"min": 0, "max": 99999, "default": 10}),
            "condition": ("lineedit", {"placeholder": "循环终止条件 JSON", "default": "{}"}),
            "steps": ("lineedit", {"placeholder": "循环体步骤", "default": "[]"}),
        }
    },
    "input_text": {
        "required": ["text"],
        "optional": [],
        "field_types": {
            "text": ("lineedit", {"placeholder": "要输入的文本", "default": ""}),
        }
    },
    "variable": {
        "required": ["var_name", "var_type", "var_value"],
        "optional": [],
        "field_types": {
            "var_name": ("lineedit", {"placeholder": "变量名", "default": ""}),
            "var_type": ("combobox", {"items": ["string", "int", "bool"], "default": "string"}),
            "var_value": ("lineedit", {"placeholder": "变量值", "default": ""}),
        }
    },
    "adb_command": {
        "required": ["adb_cmd"],
        "optional": ["assign_variable"],
        "field_types": {
            "adb_cmd": ("lineedit", {"placeholder": "ADB命令 如 shell input tap 500 500", "default": ""}),
            "assign_variable": ("lineedit", {"placeholder": "结果赋值到变量名（可选）", "default": ""}),
        }
    },
    "expression": {
        "required": ["expression"],
        "optional": ["assign_variable"],
        "field_types": {
            "expression": ("lineedit", {"placeholder": "表达式 如 ${var1} + 1", "default": ""}),
            "assign_variable": ("lineedit", {"placeholder": "结果赋值到变量名", "default": ""}),
        }
    },
}


# Advanced options shown in collapsible section for ALL types
ADVANCED_FIELDS = {
    "on_fail": ("combobox", {"items": ["fail", "retry", "backoff", "skip", "abort", "stop", "recover"],
                              "labels": ["失败(fail)", "重试(retry)", "退避重试(backoff)", "跳过(skip)", "中止(abort)", "停止(stop)", "恢复(recover)"],
                              "default": "fail"}),
    "retry_count": ("spinbox", {"min": 0, "max": 99, "default": 0}),
    "assign_variable": ("lineedit", {"placeholder": "结果赋值到变量名", "default": ""}),
    "recover_workflow": ("lineedit", {"placeholder": "恢复工作流名称", "default": ""}),
    "comment": ("lineedit", {"placeholder": "备注说明", "default": ""}),
}


# Field labels
FIELD_LABELS = {
    "enabled": "鍚敤",
    "display_name": "显示名称",
    "x": "X坐标",
    "y": "Y坐标",
    "x1": "起点X",
    "y1": "起点Y",
    "x2": "终点X",
    "y2": "终点Y",
    "duration": "时长(ms)",
    "comment": "备注",
    "wait_after": "等待后(ms)",
    "key": "按键",
    "seconds": "秒数",
    "action": "动作",
    "package": "包名",
    "save_path": "保存路径",
    "remote": "远程路径",
    "local": "本地路径",
    "path": "文件路径",
    "template": "模板路径",
    "threshold": "阈值",
    "region": "区域",
    "workflow": "工作流",
    "check": "条件",
    "then_steps": "满足步骤",
    "else_steps": "不满足步骤",
    "max_count": "最大次数",
    "steps": "步骤",
    "text": "文本",
    "var_name": "变量名",
    "var_type": "变量类型",
    "var_value": "变量值",
    "adb_cmd": "ADB命令",
    "assign_variable": "结果存入变量",
}


# Step types that support coordinate pickup
PICKUP_TYPES = ("tap", "long_press", "tap_point", "swipe")
# Step types that show recognition result UI
RECOGNITION_TYPES = ("check_image", "ocr_region")

# condition 分支模式字段：满足/不满足时，选择"内嵌步骤"还是"调用工作流"
BRANCH_MODE_FIELDS = {"then_mode", "else_mode"}
BRANCH_WORKFLOW_FIELDS = {"then_workflow", "else_workflow"}
BRANCH_STEPS_FIELDS = {"then_steps", "else_steps"}
BRANCH_MODE_EMBEDDED = "内嵌步骤"
BRANCH_MODE_WORKFLOW = "调用工作流"


class RegionEditor(QWidget):
    """Custom widget for editing a region with 4 spinboxes (left, top, right, bottom)."""

    valueChanged = pyqtSignal()

    def __init__(self, params=None, parent=None):
        super().__init__(parent)
        self._params = params or {}
        default = self._params.get("default", {"left": 0, "top": 0, "right": 0, "bottom": 0})

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._spins = {}
        for key, label_text in [("left", "左:"), ("top", "上:"), ("right", "右:"), ("bottom", "下:")]:
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Microsoft YaHei", 9))
            layout.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(default.get(key, 0))
            spin.setFont(QFont("Microsoft YaHei", 9))
            spin.valueChanged.connect(self.valueChanged.emit)
            layout.addWidget(spin)
            self._spins[key] = spin

        layout.addStretch()

    def value(self):
        return {key: spin.value() for key, spin in self._spins.items()}

    def set_value(self, val):
        if isinstance(val, dict):
            for key, spin in self._spins.items():
                spin.setValue(val.get(key, 0))


class StepEditor(QWidget):
    """Editor for a single workflow step's properties with type-specific forms."""

    step_changed = pyqtSignal(dict)
    pickup_requested = pyqtSignal(bool)  # (sync_tap: bool)

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._current_index = -1
        self._current_step = None
        self._updating = False
        self._field_widgets = {}          # ALL field widgets (basic + type-specific + advanced)
        self._field_rows = []             # List of (row_layout, parent_layout) tuples for cleanup
        self._clearable_field_names = set()  # Names of type-specific + advanced fields
        self._advanced_defaults = {
            name: params.get("default") for name, (_, params) in ADVANCED_FIELDS.items()
        }
        # Swipe two-click pickup state
        self._swipe_pickup_phase = 0       # 0=idle, 1=waiting first click, 2=waiting second click
        self._swipe_reenter_pending = False  # Flag: re-enter pickup mode after exit_pickup_mode
        # Step executor reference (for connecting signals)
        self._step_executor = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._placeholder = QLabel("选择步骤以编辑")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setFont(QFont("Microsoft YaHei", 14))
        self._placeholder.setStyleSheet("color: #aaaaaa;")
        self._layout.addWidget(self._placeholder)

        # ---- Zone 1: Basic Info (top, fixed) ----
        self._setup_basic_zone(layout)

        # ---- Zone 2: Type-Specific Parameters (middle, scrollable) ----
        self._setup_type_zone(layout)

        # ---- Zone 3: Advanced Options (bottom, collapsible) ----
        self._setup_advanced_zone(layout)

        # ---- Pickup container ----
        self._setup_pickup_zone(layout)

        # ---- Recognition result container ----
        self._recognition_container = QWidget()
        self._setup_recognition_ui()
        layout.addWidget(self._recognition_container)

    def _setup_basic_zone(self, parent_layout):
        """Zone 1 - Basic Info: display_name + enabled."""
        self._basic_container = QWidget()
        basic_layout = QHBoxLayout(self._basic_container)
        basic_layout.setContentsMargins(0, 4, 0, 4)
        basic_layout.setSpacing(4)

        lbl = QLabel("显示名称:")
        lbl.setFont(QFont("Microsoft YaHei", 9))
        lbl.setFixedWidth(100)
        lbl.setStyleSheet("color: #c9d1d9;")
        basic_layout.addWidget(lbl)

        self._display_name_edit = QLineEdit()
        self._display_name_edit.setFont(QFont("Microsoft YaHei", 9))
        self._display_name_edit.setPlaceholderText("步骤显示名称（可选）")
        self._display_name_edit.setStyleSheet(
            "QLineEdit { background-color: #161b22; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 2px 4px; }"
            "QLineEdit:focus { border: 1px solid #58a6ff; }"
        )
        self._display_name_edit.textChanged.connect(lambda: self._on_field_changed())
        basic_layout.addWidget(self._display_name_edit, stretch=1)

        self._enabled_check = QCheckBox("启用")
        self._enabled_check.setChecked(True)
        self._enabled_check.setFont(QFont("Microsoft YaHei", 9))
        self._enabled_check.setStyleSheet(
            "QCheckBox { color: #c9d1d9; font-size: 11px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self._enabled_check.stateChanged.connect(lambda: self._on_field_changed())
        basic_layout.addWidget(self._enabled_check)

        parent_layout.addWidget(self._basic_container)

        # Register basic widgets in _field_widgets
        self._field_widgets["display_name"] = self._display_name_edit
        self._field_widgets["enabled"] = self._enabled_check

    def _setup_type_zone(self, parent_layout):
        """Zone 2 - Type-Specific Parameters (scrollable)."""
        scroll = QScrollArea()
        scroll.setMinimumHeight(200)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setSpacing(4)
        self._fields_layout.addStretch()
        scroll.setWidget(self._fields_container)
        parent_layout.addWidget(scroll, stretch=1)

    def _setup_advanced_zone(self, parent_layout):
        """Zone 3 - Advanced Options (collapsible QGroupBox)."""
        self._advanced_group = QGroupBox("高级选项")
        self._advanced_group.setCheckable(True)
        self._advanced_group.setChecked(False)
        self._advanced_group.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        self._advanced_group.setStyleSheet(
            "QGroupBox { color: #8b949e; border: 1px solid #30363d; "
            "border-radius: 4px; margin-top: 8px; padding-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
            "QGroupBox::indicator { width: 14px; height: 14px; }"
        )
        group_layout = QVBoxLayout(self._advanced_group)
        group_layout.setContentsMargins(4, 4, 4, 4)
        group_layout.setSpacing(4)

        self._advanced_content = QWidget()
        self._advanced_layout = QVBoxLayout(self._advanced_content)
        self._advanced_layout.setContentsMargins(0, 0, 0, 0)
        self._advanced_layout.setSpacing(4)
        self._advanced_layout.addStretch()
        group_layout.addWidget(self._advanced_content)

        self._advanced_group.toggled.connect(self._advanced_content.setVisible)
        self._advanced_content.setVisible(False)
        parent_layout.addWidget(self._advanced_group)

    def _setup_pickup_zone(self, parent_layout):
        """Pickup container for coordinate selection from screen mirror."""
        self._pickup_container = QWidget()
        pickup_layout = QVBoxLayout(self._pickup_container)
        pickup_layout.setContentsMargins(0, 4, 0, 0)
        pickup_layout.setSpacing(4)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #30363d;")
        pickup_layout.addWidget(sep)

        pickup_btn_row = QHBoxLayout()
        pickup_btn_row.setSpacing(8)

        self._btn_pickup = QPushButton("📍 从投屏获取坐标")
        self._btn_pickup.setFixedHeight(32)
        self._btn_pickup.setStyleSheet(
            "QPushButton { background-color: #1f6feb; color: white; "
            "border: 1px solid #388bfd; border-radius: 6px; "
            "font-size: 12px; font-weight: bold; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #388bfd; }"
            "QPushButton:pressed { background-color: #1158c7; }"
        )
        self._btn_pickup.clicked.connect(self._on_pickup_clicked)
        pickup_btn_row.addWidget(self._btn_pickup)

        self._chk_sync_tap = QCheckBox("同步tap")
        self._chk_sync_tap.setStyleSheet(
            "QCheckBox { color: #c9d1d9; font-size: 11px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        pickup_btn_row.addWidget(self._chk_sync_tap)
        pickup_btn_row.addStretch()

        pickup_layout.addLayout(pickup_btn_row)

        self._pickup_hint = QLabel(
            "💡 1. 请确保本窗口不遮挡手机屏幕\n"
            "    2. 在手机上操作到目标位置，然后在投屏画面上点击该位置"
        )
        self._pickup_hint.setStyleSheet(
            "color: #d29922; font-size: 11px; background-color: #161b22; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 6px 8px;"
        )
        self._pickup_hint.setWordWrap(True)
        self._pickup_hint.setVisible(False)
        pickup_layout.addWidget(self._pickup_hint)

        self._pickup_container.setVisible(False)
        parent_layout.addWidget(self._pickup_container)

    def _setup_recognition_ui(self):
        """设置识别结果显示 UI"""
        layout = QVBoxLayout(self._recognition_container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #30363d;")
        layout.addWidget(sep)

        title = QLabel("📊 识别结果")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)

        self._status_label = QLabel("状态: 待执行")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self._status_label)

        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        # 坐标信息标签
        self._coord_label = QLabel("")
        self._coord_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        self._coord_label.setWordWrap(True)
        layout.addWidget(self._coord_label)

        # OCR 逐字置信度容器
        self._ocr_detail_container = QWidget()
        ocr_detail_layout = QVBoxLayout(self._ocr_detail_container)
        ocr_detail_layout.setContentsMargins(0, 0, 0, 0)
        ocr_detail_layout.setSpacing(2)
        self._ocr_detail_title = QLabel("逐字识别详情:")
        self._ocr_detail_title.setStyleSheet("color: #8b949e; font-size: 11px;")
        ocr_detail_layout.addWidget(self._ocr_detail_title)
        self._ocr_detail_label = QLabel("")
        self._ocr_detail_label.setStyleSheet("color: #c9d1d9; font-size: 10px; background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 4px 6px;")
        self._ocr_detail_label.setWordWrap(True)
        ocr_detail_layout.addWidget(self._ocr_detail_label)
        self._ocr_detail_container.setVisible(False)
        layout.addWidget(self._ocr_detail_container)

        self._preview_container = QWidget()
        preview_layout = QHBoxLayout(self._preview_container)
        preview_layout.setContentsMargins(0, 4, 0, 0)
        preview_layout.setSpacing(8)

        self._template_preview = QLabel()
        self._template_preview.setFixedSize(100, 100)
        self._template_preview.setStyleSheet(
            "border: 1px solid #30363d; background-color: #161b22;"
        )
        self._template_preview.setAlignment(Qt.AlignCenter)
        self._template_preview.setText("预览")
        preview_layout.addWidget(self._template_preview)

        self._match_preview = QLabel()
        self._match_preview.setFixedSize(100, 100)
        self._match_preview.setStyleSheet(
            "border: 1px solid #30363d; background-color: #161b22;"
        )
        self._match_preview.setAlignment(Qt.AlignCenter)
        self._match_preview.setText("预览")
        preview_layout.addWidget(self._match_preview)

        preview_layout.addStretch()
        layout.addWidget(self._preview_container)

        # 确保容器有最小高度，避免被布局挤出可见区域
        self._recognition_container.setMinimumHeight(80)
        self._recognition_container.setVisible(False)

    # ------------------------------------------------------------------
    # Control factories
    # ------------------------------------------------------------------
    def _create_spinbox(self, params):
        widget = QSpinBox()
        widget.setRange(params.get("min", 0), params.get("max", 999999))
        widget.setValue(params.get("default", 0))
        if "suffix" in params:
            widget.setSuffix(params["suffix"])
        widget.setFont(QFont("Microsoft YaHei", 9))
        widget.setStyleSheet(
            "QSpinBox { background-color: #161b22; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 2px 4px; }"
            "QSpinBox:focus { border: 1px solid #58a6ff; }"
        )
        return widget

    def _create_doublespinbox(self, params):
        widget = QDoubleSpinBox()
        widget.setRange(params.get("min", 0.0), params.get("max", 999999.0))
        widget.setDecimals(params.get("decimals", 2))
        widget.setValue(params.get("default", 0.0))
        if "suffix" in params:
            widget.setSuffix(params["suffix"])
        if "single_step" in params:
            widget.setSingleStep(params["single_step"])
        widget.setFont(QFont("Microsoft YaHei", 9))
        widget.setStyleSheet(
            "QDoubleSpinBox { background-color: #161b22; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 2px 4px; }"
            "QDoubleSpinBox:focus { border: 1px solid #58a6ff; }"
        )
        return widget

    def _create_lineedit(self, params):
        widget = QLineEdit()
        widget.setPlaceholderText(params.get("placeholder", ""))
        widget.setText(str(params.get("default", "")))
        widget.setFont(QFont("Microsoft YaHei", 9))
        widget.setStyleSheet(
            "QLineEdit { background-color: #161b22; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 2px 4px; }"
            "QLineEdit:focus { border: 1px solid #58a6ff; }"
        )
        return widget

    def _create_checkbox(self, params):
        widget = QCheckBox()
        widget.setChecked(params.get("default", False))
        widget.setFont(QFont("Microsoft YaHei", 9))
        widget.setStyleSheet(
            "QCheckBox { color: #c9d1d9; font-size: 11px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        return widget

    def _create_combobox(self, params):
        widget = QComboBox()
        widget.setEditable(params.get("editable", False))
        items = params.get("items", [])
        labels = params.get("labels")
        if labels and len(labels) == len(items):
            for item, label in zip(items, labels):
                widget.addItem(label, userData=item)
        else:
            for item in items:
                widget.addItem(item)
        # Set default
        default = params.get("default", "")
        if items:
            self._set_combobox_value(widget, default)
        widget.setFont(QFont("Microsoft YaHei", 9))
        widget.setStyleSheet(
            "QComboBox { background-color: #161b22; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 2px 4px; }"
            "QComboBox:focus { border: 1px solid #58a6ff; }"
            "QComboBox QAbstractItemView { background-color: #161b22; color: #c9d1d9; "
            "selection-background-color: #1f6feb; }"
        )
        return widget

    def _create_region_editor(self, params):
        widget = RegionEditor(params)
        return widget

    def _set_combobox_value(self, combo, value):
        """Set combobox value by searching userData first, then text."""
        if value is None:
            value = ""
        value_str = str(value)
        idx = combo.findData(value_str)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findText(value_str)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if combo.isEditable():
            combo.setEditText(value_str)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Field generation
    # ------------------------------------------------------------------
    def _add_field(self, key, control_type, params, value, parent_layout, is_required=False):
        """Generate a single field row and add it to parent_layout."""
        row_layout = QHBoxLayout()
        row_layout.setSpacing(4)

        label_text = FIELD_LABELS.get(key, key)
        if is_required:
            label = QLabel(f'<span style="color:#f85149;">*</span> {label_text}:')
            label.setTextFormat(Qt.RichText)
        else:
            label = QLabel(f"{label_text}:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setFixedWidth(100)
        label.setStyleSheet("color: #c9d1d9;")
        row_layout.addWidget(label)

        widget = self._build_control(key, control_type, params, value)
        row_layout.addWidget(widget, stretch=1)

        parent_layout.insertLayout(parent_layout.count() - 1, row_layout)

        self._field_widgets[key] = widget
        self._field_rows.append((row_layout, parent_layout))
        self._clearable_field_names.add(key)

    def _build_control(self, key, control_type, params, value):
        """Build a control widget for the given field config and value."""
        if control_type == "spinbox":
            widget = self._create_spinbox(params)
            if value is not None:
                try:
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    pass
            widget.valueChanged.connect(lambda: self._on_field_changed())

        elif control_type == "doublespinbox":
            widget = self._create_doublespinbox(params)
            if value is not None:
                try:
                    widget.setValue(float(value))
                except (TypeError, ValueError):
                    pass
            widget.valueChanged.connect(lambda: self._on_field_changed())

        elif control_type == "lineedit":
            widget = self._create_lineedit(params)
            if isinstance(value, (dict, list)):
                widget.setText(json.dumps(value, ensure_ascii=False))
            elif value is not None:
                widget.setText(str(value))
            widget.textChanged.connect(lambda: self._on_field_changed())

        elif control_type == "checkbox":
            widget = self._create_checkbox(params)
            if value is not None:
                widget.setChecked(bool(value))
            widget.stateChanged.connect(lambda: self._on_field_changed())

        elif control_type == "combobox":
            widget = self._create_combobox(params)
            # Special: populate workflow combobox from config_manager
            if key == "workflow" and self._config_manager:
                try:
                    workflows = self._config_manager.get_all_workflows()
                    if workflows:
                        for wf_name in workflows.keys():
                            widget.addItem(wf_name)
                except Exception as e:
                    logger.warning("Failed to populate workflow list: %s", e)
            self._set_combobox_value(widget, value if value is not None else params.get("default", ""))
            widget.currentIndexChanged.connect(lambda: self._on_field_changed())
            if widget.isEditable():
                widget.editTextChanged.connect(lambda: self._on_field_changed())

        elif control_type == "region_editor":
            widget = self._create_region_editor(params)
            if isinstance(value, dict):
                widget.set_value(value)
            widget.valueChanged.connect(lambda: self._on_field_changed())

        else:
            widget = QLineEdit(str(value) if value is not None else "")
            widget.setFont(QFont("Microsoft YaHei", 9))
            widget.textChanged.connect(lambda: self._on_field_changed())

        return widget

    def _generate_type_fields(self, step_type, step):
        """Generate type-specific fields (required first, then optional)."""
        type_config = STEP_TYPE_FIELDS.get(step_type)
        if not type_config:
            return

        required = type_config.get("required", [])
        optional = type_config.get("optional", [])
        field_types = type_config.get("field_types", {})

        for field_name in required:
            if field_name not in field_types:
                continue
            control_type, params = field_types[field_name]
            value = step.get(field_name, params.get("default"))
            self._add_field(field_name, control_type, params, value,
                            self._fields_layout, is_required=True)

        for field_name in optional:
            if field_name not in field_types:
                continue
            control_type, params = field_types[field_name]
            value = step.get(field_name, params.get("default"))
            self._add_field(field_name, control_type, params, value,
                            self._fields_layout, is_required=False)

    def _generate_advanced_fields(self, step_type, step):
        """Generate advanced option fields, skipping those already in type-specific fields."""
        type_field_names = set(
            STEP_TYPE_FIELDS.get(step_type, {}).get("field_types", {}).keys()
        )

        for field_name, (control_type, params) in ADVANCED_FIELDS.items():
            if field_name in type_field_names:
                continue
            value = step.get(field_name, params.get("default"))
            self._add_field(field_name, control_type, params, value,
                            self._advanced_layout, is_required=False)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def load_step(self, index: int, step: dict):
        self._updating = True
        self._current_index = index
        self._current_step = copy.deepcopy(step)
        self._swipe_pickup_phase = 0
        self._swipe_reenter_pending = False

        step_type = step.get("type", "")
        self._type_label.setText(f"步骤 {index + 1}: {step_type}")

        # Clear existing type-specific and advanced fields
        self._clear_all_rows()

        # Set basic info fields
        self._display_name_edit.setText(step.get("display_name", ""))
        self._enabled_check.setChecked(step.get("enabled", True))

        # Generate type-specific fields
        self._generate_type_fields(step_type, step)

        # Generate advanced fields
        self._generate_advanced_fields(step_type, step)

        self._updating = False

        # Show/hide pickup container
        self._pickup_container.setVisible(step_type in PICKUP_TYPES)

        # Show/hide recognition container
        if step_type in RECOGNITION_TYPES:
            execution_result = step.get("execution_result")
            if execution_result:
                self._on_step_result_updated(index, {
                    "execution_result": execution_result,
                    "preview": step.get("preview", {})
                })
            else:
                self._recognition_container.setVisible(True)
                self._status_label.setText("状态: 待执行")
                self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
                self._result_label.setText("")
                self._coord_label.setText("")
                self._coord_label.setVisible(False)
                self._ocr_detail_container.setVisible(False)
                self._template_preview.setText("预览")
                self._match_preview.setText("预览")
                # 强制更新布局
                self._recognition_container.updateGeometry()
                self.updateGeometry()
        else:
            self._recognition_container.setVisible(False)

    def clear_step(self):
        self._updating = True
        self._current_index = -1
        self._current_step = None
        self._swipe_pickup_phase = 0
        self._swipe_reenter_pending = False
        self._type_label.setText("未选择步骤")
        self._clear_all_rows()
        self._display_name_edit.setText("")
        self._enabled_check.setChecked(True)
        self._pickup_container.setVisible(False)
        self._recognition_container.setVisible(False)
        self._updating = False

    def get_current_index(self) -> int:
        return self._current_index

    def set_step_executor(self, executor):
        """设置步骤执行器并连接信号"""
        self._step_executor = executor
        if executor:
            executor.step_result_updated.connect(self._on_step_result_updated)

    def update_coord_fields(self, x: int, y: int):
        """Update coordinate fields when a point is selected from screenshot."""
        if self._current_step is None:
            return
        step_type = self._current_step.get("type", "")
        type_label = QLabel("类型: {}".format(step_type))
        type_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._form_layout.addWidget(type_label)

        # 屏蔽字段信号，避免每个 setValue 各触发一次 step_changed/set_workflow，
        # 导致一次拾取写入多份 workflows.json（x/y 各一次保存）。
        self._updating = True
        try:
            if step_type in ("tap", "long_press", "tap_point"):
                if "x" in self._field_widgets:
                    w = self._field_widgets["x"]
                    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                        w.setValue(x)
                if "y" in self._field_widgets:
                    w = self._field_widgets["y"]
                    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                        w.setValue(y)

            elif step_type == "swipe":
                if self._swipe_pickup_phase == 1:
                    # First click: set start point, switch to phase 2
                    if "x1" in self._field_widgets:
                        w = self._field_widgets["x1"]
                        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                            w.setValue(x)
                    if "y1" in self._field_widgets:
                        w = self._field_widgets["y1"]
                        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                            w.setValue(y)
                    self._swipe_pickup_phase = 2
                    self._swipe_reenter_pending = True
                elif self._swipe_pickup_phase == 2:
                    # Second click: set end point, reset phase
                    if "x2" in self._field_widgets:
                        w = self._field_widgets["x2"]
                        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                            w.setValue(x)
                    if "y2" in self._field_widgets:
                        w = self._field_widgets["y2"]
                        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                            w.setValue(y)
                    self._swipe_pickup_phase = 0
        finally:
            self._updating = False

        # 字段批量更新完成后，统一 emit 一次 step_changed
        self._on_field_changed()

    def is_sync_tap_checked(self) -> bool:
        """返回「同步tap」勾选框状态。"""
        return self._chk_sync_tap.isChecked()

    # ------------------------------------------------------------------
    # Recognition result UI (preserved from original)
    # ------------------------------------------------------------------
    def _on_step_result_updated(self, step_index: int, result: dict):
        """步骤结果更新回调"""
        if step_index != self._current_index:
            return

        execution_result = result.get("execution_result", {})
        status = execution_result.get("status", "pending")

        status_colors = {
            "success": "#3fb950",
            "fail": "#f85149",
            "running": "#1f6feb",
            "pending": "#8b949e"
        }

        status_texts = {
            "success": "成功",
            "fail": "失败",
            "running": "执行中",
            "pending": "待执行"
        }

        self._status_label.setText(f"状态: {status_texts.get(status, status)}")
        self._status_label.setStyleSheet(f"color: {status_colors.get(status, '#8b949e')}; font-size: 11px;")

        step_type = self._current_step.get("type", "") if self._current_step else ""
        if step_type == "check_image":
            confidence = execution_result.get("confidence", 0)
            self._result_label.setText(f"匹配置信度: {confidence:.2%}")
            # 显示匹配位置坐标
            match_location = execution_result.get("match_location")
            if match_location:
                self._coord_label.setText(
                    f"匹配位置: ({match_location.get('x', 0)}, {match_location.get('y', 0)})"
                )
                self._coord_label.setVisible(True)
            else:
                self._coord_label.setVisible(False)
            self._ocr_detail_container.setVisible(False)
        elif step_type == "ocr_region":
            text = execution_result.get("recognized_text", "")
            self._result_label.setText(f"识别文本: {text}")
            # 显示 OCR 区域坐标
            region = self._current_step.get("region", {}) if self._current_step else {}
            if region:
                self._coord_label.setText(
                    f"识别区域: ({region.get('left', 0)}, {region.get('top', 0)}, "
                    f"{region.get('right', 0)}, {region.get('bottom', 0)})"
                )
                self._coord_label.setVisible(True)
            else:
                self._coord_label.setVisible(False)
            # 显示 OCR 逐字置信度
            ocr_details = execution_result.get("ocr_details", [])
            if ocr_details:
                detail_parts = []
                for item in ocr_details:
                    char_text = item.get("text", "")
                    conf = item.get("confidence", 0)
                    detail_parts.append(f"{char_text}({conf:.0%})")
                self._ocr_detail_label.setText("  ".join(detail_parts))
                self._ocr_detail_container.setVisible(True)
            else:
                self._ocr_detail_container.setVisible(False)
        else:
            self._coord_label.setVisible(False)
            self._ocr_detail_container.setVisible(False)

        preview = result.get("preview", {})
        self._update_preview_images(preview, step_type)

        self._recognition_container.setVisible(True)
        # 强制更新布局，确保容器可见
        self._recognition_container.updateGeometry()
        self.updateGeometry()

    def _update_preview_images(self, preview: dict, step_type: str):
        """更新预览图像"""
        if step_type == "check_image":
            template_image = preview.get("template_image", "")
            if template_image:
                self._set_image_from_base64(self._template_preview, template_image, "模板")

            screenshot_thumbnail = preview.get("screenshot_thumbnail", "")
            if screenshot_thumbnail:
                self._set_image_from_base64(self._match_preview, screenshot_thumbnail, "匹配结果")

        elif step_type == "ocr_region":
            region_image = preview.get("region_image", "")
            if region_image:
                self._set_image_from_base64(self._template_preview, region_image, "识别区域")

            highlighted_text = preview.get("highlighted_text", "")
            if highlighted_text:
                self._set_image_from_base64(self._match_preview, highlighted_text, "识别结果")

    def _set_image_from_base64(self, label: QLabel, base64_str: str, placeholder: str):
        """从 base64 字符串设置图像"""
        if not base64_str:
            label.setText(placeholder)
            return

        try:
            import base64
            from PyQt5.QtGui import QPixmap

            image_data = base64.b64decode(base64_str)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            label.setPixmap(pixmap.scaled(
                label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        except Exception:
            label.setText(placeholder)

    # ------------------------------------------------------------------
    # Internal: field change handling
    # ------------------------------------------------------------------
    def _clear_all_rows(self):
        """Remove all type-specific and advanced field rows (NOT basic info fields)."""
        for row_layout, parent_layout in self._field_rows:
            while row_layout.count():
                item = row_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            parent_layout.removeItem(row_layout)
        self._field_rows.clear()

        for name in self._clearable_field_names:
            if name in self._field_widgets:
                del self._field_widgets[name]
        self._clearable_field_names.clear()

    def _read_widget_value(self, widget, field_name):
        """Read value from a widget, handling each control type."""
        if isinstance(widget, RegionEditor):
            return widget.value()

        if isinstance(widget, QCheckBox):
            return widget.isChecked()

        if isinstance(widget, QSpinBox):
            return widget.value()

        if isinstance(widget, QDoubleSpinBox):
            return widget.value()

        if isinstance(widget, QComboBox):
            idx = widget.currentIndex()
            data = widget.itemData(idx) if idx >= 0 else None
            if data is not None:
                return data
            return widget.currentText()

        if isinstance(widget, QLineEdit):
            text = widget.text()
            original = self._current_step.get(field_name) if self._current_step else None
            if isinstance(original, dict):
                try:
                    return json.loads(text) if text else {}
                except (json.JSONDecodeError, TypeError):
                    return text
            elif isinstance(original, list):
                try:
                    return json.loads(text) if text else []
                except (json.JSONDecodeError, TypeError):
                    return text
            elif isinstance(original, bool):
                return text
            elif isinstance(original, int):
                try:
                    return int(text) if text else 0
                except ValueError:
                    return text
            elif isinstance(original, float):
                try:
                    return float(text) if text else 0.0
                except ValueError:
                    return text
            else:
                return text

        return None

    def _on_field_changed(self):
        """Collect values from all field widgets and emit step_changed."""
        if self._updating or self._current_step is None:
            return

        step_type = self._current_step.get("type", "unknown")
        step = {"type": step_type}

        # Basic info: always include enabled, include display_name if non-empty
        display_name = self._display_name_edit.text()
        if display_name:
            step["display_name"] = display_name
        step["enabled"] = self._enabled_check.isChecked()

        # Type-specific fields: include all
        type_config = STEP_TYPE_FIELDS.get(step_type, {})
        type_field_names = set(type_config.get("field_types", {}).keys())
        for field_name in type_field_names:
            if field_name in self._field_widgets:
                step[field_name] = self._read_widget_value(
                    self._field_widgets[field_name], field_name
                )

        # Advanced fields: include only if non-default
        type_field_names_set = type_field_names
        for field_name, (control_type, params) in ADVANCED_FIELDS.items():
            if field_name in type_field_names_set:
                # Already included from type-specific section
                continue
            if field_name not in self._field_widgets:
                continue
            value = self._read_widget_value(self._field_widgets[field_name], field_name)
            default = self._advanced_defaults.get(field_name)
            if value != default:
                step[field_name] = value

        self.step_changed.emit(step)

    # ------------------------------------------------------------------
    # Pickup mode
    # ------------------------------------------------------------------
    def _on_pickup_clicked(self):
        """点击「从投屏获取坐标」按钮。"""
        sync_tap = self._chk_sync_tap.isChecked()
        step_type = self._current_step.get("type", "") if self._current_step else ""

        if step_type == "swipe":
            self._swipe_pickup_phase = 1
            self._swipe_reenter_pending = False
            self._enter_pickup_mode()
            self._pickup_hint.setText(
                "💡 第1次点击：选择起始位置\n"
                "    在投屏画面上点击滑动起始位置"
            )
        else:
            self._swipe_pickup_phase = 0
            self._swipe_reenter_pending = False
            self._enter_pickup_mode()
            self._pickup_hint.setText(
                "💡 1. 请确保本窗口不遮挡手机屏幕\n"
                "    2. 在手机上操作到目标位置，然后在投屏画面上点击该位置"
            )

        self.pickup_requested.emit(sync_tap)

    def _enter_pickup_mode(self):
        """进入坐标选择模式 — 更新按钮和提示状态。"""
        self._btn_pickup.setText("✕ 取消选择")
        self._btn_pickup.setStyleSheet(
            "QPushButton { background-color: #da3633; color: white; "
            "border: 1px solid #f85149; border-radius: 6px; "
            "font-size: 12px; font-weight: bold; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #f85149; }"
            "QPushButton:pressed { background-color: #b62324; }"
        )
        self._pickup_hint.setVisible(True)
        try:
            self._btn_pickup.clicked.disconnect(self._on_pickup_clicked)
        except TypeError:
            pass
        self._btn_pickup.clicked.connect(self.exit_pickup_mode)

    def exit_pickup_mode(self):
        """退出坐标选择模式 — 恢复按钮和提示状态。"""
        # Swipe two-click mode: if waiting for second click, re-enter pickup mode
        if self._swipe_reenter_pending:
            self._swipe_reenter_pending = False
            self._pickup_hint.setText(
                "💡 第2次点击：选择结束位置\n"
                "    在投屏画面上点击滑动结束位置"
            )
            # Re-enter pickup mode on the picker side
            self.pickup_requested.emit(self._chk_sync_tap.isChecked())
            return

        # Actually exit
        self._swipe_pickup_phase = 0
        self._swipe_reenter_pending = False
        self._btn_pickup.setText("📍 从投屏获取坐标")
        self._btn_pickup.setStyleSheet(
            "QPushButton { background-color: #1f6feb; color: white; "
            "border: 1px solid #388bfd; border-radius: 6px; "
            "font-size: 12px; font-weight: bold; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #388bfd; }"
            "QPushButton:pressed { background-color: #1158c7; }"
        )
        self._pickup_hint.setVisible(False)
        try:
            self._btn_pickup.clicked.disconnect(self.exit_pickup_mode)
        except TypeError:
            pass
        self._btn_pickup.clicked.connect(self._on_pickup_clicked)
