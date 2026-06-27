from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


STEP_FIELD_DEFS = {
    "tap": ["enabled", "display_name", "x", "y", "comment", "wait_after"],
    "long_press": ["enabled", "display_name", "x", "y", "duration", "comment", "wait_after"],
    "swipe": ["enabled", "display_name", "x1", "y1", "x2", "y2", "duration", "comment"],
    "keyevent": ["enabled", "display_name", "key", "comment"],
    "wait": ["enabled", "display_name", "seconds", "comment"],
    "wifi": ["enabled", "display_name", "action", "comment", "wait_after"],
    "force_stop": ["enabled", "display_name", "package", "comment", "wait_after"],
    "launch": ["enabled", "display_name", "package", "comment", "wait_after"],
    "screenshot": ["enabled", "display_name", "save_path", "comment"],
    "pull_file": ["enabled", "display_name", "remote", "local", "comment"],
    "delete_file": ["enabled", "display_name", "path", "comment"],
    "check_image": ["enabled", "display_name", "template", "threshold", "assign_variable", "comment"],
    "ocr_region": ["enabled", "display_name", "region", "assign_variable", "comment"],
    "tap_point": ["enabled", "display_name", "x", "y", "comment", "wait_after"],
    "call_workflow": ["enabled", "display_name", "workflow", "comment"],
    "condition": ["enabled", "display_name", "check", "then_steps", "else_steps", "comment"],
    "loop": ["enabled", "display_name", "max_count", "condition", "steps", "comment"],
    "input_text": ["enabled", "display_name", "text", "comment"],
    "variable": ["enabled", "display_name", "var_name", "var_type", "var_value", "comment"],
    "adb_command": ["enabled", "display_name", "adb_cmd", "assign_variable", "comment"],
    "expression": ["enabled", "display_name", "expression", "assign_variable", "comment"],
}

FIELD_LABELS = {
    "enabled": "启用",
    "display_name": "显示名称",
    "x": "X坐标",
    "y": "Y坐标",
    "x1": "起点X",
    "y1": "起点Y",
    "x2": "终点X",
    "y2": "终点Y",
    "duration": "时长(ms)",
    "comment": "备注",
    "wait_after": "等待(秒)",
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

WIFI_ACTIONS = ["enable", "disable", "toggle"]
VAR_TYPES = ["bool", "int", "string"]

COORD_FIELDS = {"x", "y", "x1", "y1", "x2", "y2"}
INT_FIELDS = {"duration", "wait_after"}
FLOAT_FIELDS = {"seconds", "threshold", "max_count"}
COMBO_FIELDS = {"action", "workflow", "var_type"}
BOOL_FIELDS = {"enabled"}
CHECKBOX_FIELDS = {"enabled"}


class StepEditor(QScrollArea):
    step_changed = pyqtSignal(dict)

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._current_step = {}
        self._current_index = -1
        self._field_widgets = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._emit_step_changed)
        self._updating = False

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)

        self._placeholder = QLabel("选择步骤以编辑")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setFont(QFont("Microsoft YaHei", 14))
        self._placeholder.setStyleSheet("color: #aaaaaa;")
        self._layout.addWidget(self._placeholder)

        self._form_widget = QWidget()
        self._form_layout = QVBoxLayout(self._form_widget)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(4)
        self._form_widget.setVisible(False)
        self._layout.addWidget(self._form_widget)

        self._layout.addStretch()
        self.setWidget(container)

    def load_step(self, index, step):
        self._updating = True
        self._current_index = index
        self._current_step = dict(step) if step else {}
        self._rebuild_form()
        self._updating = False

    def clear_step(self):
        self._updating = True
        self._current_index = -1
        self._current_step = {}
        self._placeholder.setVisible(True)
        self._form_widget.setVisible(False)
        self._updating = False

    def _rebuild_form(self):
        self._placeholder.setVisible(False)
        self._form_widget.setVisible(True)

        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._field_widgets.clear()

        step_type = self._current_step.get("type", "")
        type_label = QLabel("绫诲瀷: {}".format(step_type))
        type_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._form_layout.addWidget(type_label)

        fields = STEP_FIELD_DEFS.get(step_type, [])
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(4)

        for field_name in fields:
            widget = self._create_field_widget(field_name)
            self._field_widgets[field_name] = widget
            label_text = FIELD_LABELS.get(field_name, field_name)
            form.addRow("{}:".format(label_text), widget)
            value = self._current_step.get(field_name)
            self._set_field_value(widget, field_name, value)

        form_widget = QWidget()
        form_widget.setLayout(form)
        self._form_layout.addWidget(form_widget)

    def _create_field_widget(self, field_name):
        if field_name in CHECKBOX_FIELDS:
            cb = QCheckBox()
            cb.stateChanged.connect(lambda: self._on_field_changed())
            return cb

        if field_name in COMBO_FIELDS:
            combo = QComboBox()
            combo.setFont(QFont("Microsoft YaHei", 9))
            if field_name == "action":
                combo.addItems(WIFI_ACTIONS)
            elif field_name == "workflow":
                if self._config_manager:
                    workflows = self._config_manager.get_all_workflows()
                    combo.addItems(sorted(workflows.keys()) if isinstance(workflows, dict) else workflows)
            elif field_name == "var_type":
                combo.addItems(VAR_TYPES)
            combo.currentIndexChanged.connect(lambda: self._on_field_changed())
            return combo

        if field_name in COORD_FIELDS:
            spin = QSpinBox()
            spin.setFont(QFont("Microsoft YaHei", 9))
            spin.setRange(0, 99999)
            spin.setSingleStep(1)
            spin.valueChanged.connect(lambda: self._on_field_changed())
            return spin

        if field_name in INT_FIELDS:
            spin = QSpinBox()
            spin.setFont(QFont("Microsoft YaHei", 9))
            spin.setRange(0, 999999)
            spin.setSingleStep(100)
            spin.valueChanged.connect(lambda: self._on_field_changed())
            return spin

        if field_name in FLOAT_FIELDS:
            spin = QDoubleSpinBox()
            spin.setFont(QFont("Microsoft YaHei", 9))
            spin.setRange(0.0, 999999.0)
            spin.setDecimals(2)
            if field_name == "threshold":
                spin.setSingleStep(0.05)
                spin.setRange(0.0, 1.0)
            elif field_name == "max_count":
                spin.setDecimals(0)
                spin.setSingleStep(1)
            else:
                spin.setSingleStep(0.5)
            spin.valueChanged.connect(lambda: self._on_field_changed())
            return spin

        line_edit = QLineEdit()
        line_edit.setFont(QFont("Microsoft YaHei", 9))
        line_edit.textChanged.connect(lambda: self._on_field_changed())
        return line_edit

    def _set_field_value(self, widget, field_name, value):
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value) if value is not None else True)
        elif isinstance(widget, QComboBox):
            if value is not None:
                idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value) if value is not None else 0)
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value) if value is not None else 0.0)
        elif isinstance(widget, QLineEdit):
            text = str(value) if value is not None else ""
            if field_name == "region" and isinstance(value, dict):
                text = "{},{},{},{}".format(
                    value.get('left', 0), value.get('top', 0),
                    value.get('right', 0), value.get('bottom', 0)
                )
            widget.setText(text)

    def _get_field_value(self, widget, field_name):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QLineEdit):
            text = widget.text()
            if field_name == "region":
                try:
                    parts = [int(p.strip()) for p in text.split(",")]
                    if len(parts) == 4:
                        return {"left": parts[0], "top": parts[1], "right": parts[2], "bottom": parts[3]}
                except ValueError:
                    pass
                return text
            return text
        return None

    def _on_field_changed(self):
        if self._updating:
            return
        updated = dict(self._current_step)
        for field_name, widget in self._field_widgets.items():
            updated[field_name] = self._get_field_value(widget, field_name)
        self._current_step = updated
        self._save_timer.start()

    def _emit_step_changed(self):
        self.step_changed.emit(dict(self._current_step))

    def update_coord_fields(self, x, y):
        self._updating = True
        step_type = self._current_step.get("type", "")
        if step_type in ("tap", "tap_point", "long_press"):
            if "x" in self._field_widgets:
                self._field_widgets["x"].setValue(x)
            if "y" in self._field_widgets:
                self._field_widgets["y"].setValue(y)
            self._current_step["x"] = x
            self._current_step["y"] = y
        elif step_type == "swipe":
            if "x2" in self._field_widgets:
                self._field_widgets["x2"].setValue(x)
            if "y2" in self._field_widgets:
                self._field_widgets["y2"].setValue(y)
            self._current_step["x2"] = x
            self._current_step["y2"] = y
        self._updating = False
        self.step_changed.emit(self._current_step)

    def get_current_step(self):
        return dict(self._current_step)

    def get_current_index(self):
        return self._current_index
