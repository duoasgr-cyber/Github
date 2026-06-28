import copy
import base64

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPalette, QFontMetrics, QPixmap
from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu, QAction,
    QLineEdit, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QStyle, QStyleOption,
    QSizePolicy
)

STEP_TYPES = [
    ("tap", "点击"),
    ("long_press", "长按"),
    ("swipe", "滑动"),
    ("keyevent", "按键事件"),
    ("wait", "等待"),
    ("wifi", "WiFi控制"),
    ("force_stop", "强制停止"),
    ("launch", "启动应用"),
    ("screenshot", "截图"),
    ("pull_file", "拉取文件"),
    ("delete_file", "删除文件"),
    ("check_image", "图像匹配"),
    ("ocr_region", "OCR识别"),
    ("tap_point", "精确点击"),
    ("call_workflow", "调用工作流"),
    ("condition", "条件分支"),
    ("loop", "循环"),
    ("input_text", "输入文本"),
    ("variable", "变量"),
    ("adb_command", "ADB命令"),
    ("expression", "表达式"),
]

STEP_TYPE_DISPLAY = {t[0]: t[1] for t in STEP_TYPES}

# step type color map for left bar indicator
STEP_TYPE_COLORS = {
    "tap": "#1f6feb",
    "long_press": "#1f6feb",
    "swipe": "#1f6feb",
    "tap_point": "#1f6feb",
    "keyevent": "#58a6ff",
    "wait": "#8b949e",
    "wifi": "#a371f7",
    "force_stop": "#da3633",
    "launch": "#3fb950",
    "screenshot": "#d29922",
    "pull_file": "#d29922",
    "delete_file": "#da3633",
    "check_image": "#3fb950",
    "ocr_region": "#3fb950",
    "call_workflow": "#a371f7",
    "condition": "#d29922",
    "loop": "#d29922",
    "input_text": "#58a6ff",
    "variable": "#a371f7",
    "adb_command": "#f0883e",
    "expression": "#a371f7",
}

# Unified step execution states
STEP_STATE_COLORS = {
    "pending": {"fg": "#8b949e", "bg": None, "bold": False},
    "running": {"fg": "#ffffff", "bg": "#1f6feb", "bold": True},
    "success": {"fg": "#3fb950", "bg": None, "bold": False},
    "fail": {"fg": "#f85149", "bg": None, "bold": False},
    "skip": {"fg": "#d29922", "bg": None, "bold": False},
    "disabled": {"fg": "#80484f58", "bg": None, "bold": False},
}

# on_fail 策略中文显示
ON_FAIL_DISPLAY = {
    "retry": "重试",
    "backoff": "退避重试",
    "skip": "跳过",
    "abort": "中止",
    "stop": "停止",
    "recover": "恢复",
}

# 识别步骤类型（需要显示缩略图的步骤）
RECOGNITION_TYPES = ("check_image", "ocr_region")

# 步骤关键参数字段（用于第二行摘要显示）
STEP_SUMMARY_FIELDS = {
    "tap": ["x", "y", "wait_after", "on_fail"],
    "long_press": ["x", "y", "duration", "wait_after", "on_fail"],
    "swipe": ["x1", "y1", "x2", "y2", "on_fail"],
    "tap_point": ["x", "y", "wait_after", "on_fail"],
    "keyevent": ["key", "on_fail"],
    "wait": ["seconds", "on_fail"],
    "wifi": ["action", "wait_after", "on_fail"],
    "force_stop": ["package", "wait_after", "on_fail"],
    "launch": ["package", "wait_after", "on_fail"],
    "screenshot": ["save_path", "on_fail"],
    "pull_file": ["remote", "on_fail"],
    "delete_file": ["path", "on_fail"],
    "check_image": ["template", "threshold", "execution_result", "on_fail"],
    "ocr_region": ["region", "execution_result", "on_fail"],
    "call_workflow": ["workflow", "on_fail"],
    "condition": ["then_steps", "else_steps", "on_fail"],
    "loop": ["max_count", "steps", "on_fail"],
    "input_text": ["text", "on_fail"],
    "variable": ["var_name", "var_type", "on_fail"],
    "adb_command": ["adb_cmd", "on_fail"],
    "expression": ["expression", "on_fail"],
}


def _format_summary(step: dict) -> str:
    """生成步骤关键参数摘要文本。"""
    step_type = step.get("type", "")
    fields = STEP_SUMMARY_FIELDS.get(step_type, [])
    parts = []
    on_fail_part = None
    for field in fields:
        # on_fail 策略特殊处理（置于摘要末尾）
        if field == "on_fail":
            value = step.get(field)
            if value and value != "fail":
                display = ON_FAIL_DISPLAY.get(value, value)
                retry_count = step.get("retry_count", 0)
                if retry_count and retry_count > 0:
                    display += f"×{retry_count}"
                on_fail_part = display
            continue

        # 条件分支 / 循环体步数
        if field == "then_steps":
            value = step.get(field)
            if isinstance(value, list) and len(value) > 0:
                parts.append(f"真分支({len(value)}步)")
            continue
        if field == "else_steps":
            value = step.get(field)
            if isinstance(value, list) and len(value) > 0:
                parts.append(f"假分支({len(value)}步)")
            continue
        if field == "steps":
            value = step.get(field)
            if isinstance(value, list) and len(value) > 0:
                parts.append(f"循环体({len(value)}步)")
            continue

        # 特殊处理执行结果
        if field == "execution_result":
            result = step.get("execution_result")
            if result:
                status = result.get("status", "")
                if status == "success":
                    if step_type == "check_image":
                        confidence = result.get("confidence", 0)
                        match_loc = result.get("match_location")
                        loc_str = ""
                        if match_loc:
                            loc_str = f" @({match_loc.get('x', 0)},{match_loc.get('y', 0)})"
                        parts.append(f"匹配成功({confidence:.0%}){loc_str}")
                    elif step_type == "ocr_region":
                        text = result.get("recognized_text", "")
                        if len(text) > 20:
                            text = text[:17] + "..."
                        parts.append(f"识别: {text}")
                elif status == "fail":
                    if step_type == "check_image":
                        parts.append("匹配失败")
                    else:
                        parts.append("识别失败")
                elif status == "running":
                    parts.append("执行中...")
            continue

        value = step.get(field)
        if value is None or value == "":
            continue
        # wait_after 字段即使为 0 也显示
        if field not in ("wait_after", "wait_before") and value == 0:
            continue
        if field == "region" and isinstance(value, dict):
            parts.append(f"区域({value.get('left',0)},{value.get('top',0)},{value.get('right',0)},{value.get('bottom',0)})")
        else:
            # 截断过长的值
            val_str = str(value)
            if len(val_str) > 30:
                val_str = val_str[:27] + "..."
            parts.append(f"{field}={val_str}")

    # on_fail 标记置于摘要末尾
    if on_fail_part:
        parts.append(on_fail_part)

    return "  |  ".join(parts) if parts else ""


def _get_thumbnail_pixmap(step: dict) -> QPixmap:
    """从步骤数据中提取缩略图 QPixmap，无图则返回空 QPixmap。"""
    preview = step.get("preview", {})
    step_type = step.get("type", "")

    base64_str = ""
    if step_type == "check_image":
        # 优先显示截图缩略图（含匹配标记），其次模板图
        base64_str = preview.get("screenshot_thumbnail", "") or preview.get("template_image", "")
    elif step_type == "ocr_region":
        # 优先显示高亮文本图，其次区域图
        base64_str = preview.get("highlighted_text", "") or preview.get("region_image", "")

    if not base64_str:
        return QPixmap()

    try:
        image_data = base64.b64decode(base64_str)
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        return pixmap
    except Exception:
        return QPixmap()


class StepItemWidget(QWidget):
    """自定义步骤列表项：左侧缩略图（识别步骤）+ 右侧双行文本。"""

    THUMB_SIZE = 40
    jump_clicked = pyqtSignal(str)  # 点击跳转按钮时发射，携带 jump_to 标签名

    def __init__(self, step: dict, index: int, parent=None):
        super().__init__(parent)
        self._step = step
        self._index = index
        self._state = "pending"
        self._color_hex = STEP_TYPE_COLORS.get(step.get("type", ""), "#8b949e")
        self._thumb_pixmap = QPixmap()
        self._setup_ui(step, index)

    def _setup_ui(self, step: dict, index: int):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 6, 6)
        layout.setSpacing(8)

        step_type = step.get("type", "unknown")
        enabled = step.get("enabled", True)
        display_name = step.get("display_name", "")
        type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)

        # 缩略图（仅识别步骤）
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(self.THUMB_SIZE, self.THUMB_SIZE)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setStyleSheet(
            "border: 1px solid #30363d; border-radius: 4px; background-color: #161b22;"
        )
        if step_type in RECOGNITION_TYPES:
            pixmap = _get_thumbnail_pixmap(step)
            if not pixmap.isNull():
                self._thumb_pixmap = pixmap
                self._thumb_label.setPixmap(
                    pixmap.scaled(self.THUMB_SIZE, self.THUMB_SIZE,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                # 无预览图时显示类型图标
                self._thumb_label.setText("🔍")
                self._thumb_label.setStyleSheet(
                    "border: 1px solid #30363d; border-radius: 4px; "
                    "background-color: #161b22; color: #8b949e; font-size: 16px;"
                )
            layout.addWidget(self._thumb_label)
        else:
            # 非识别步骤：显示类型图标
            type_icons = {
                "tap": "👆", "long_press": "👆", "swipe": "↔", "tap_point": "🎯",
                "keyevent": "⌨", "wait": "⏱", "wifi": "📶", "force_stop": "⛔",
                "launch": "🚀", "screenshot": "📷", "pull_file": "📥", "delete_file": "🗑",
                "call_workflow": "📞", "condition": "🔀", "loop": "🔁",
                "input_text": "✏", "variable": "📌", "adb_command": "💻", "expression": "🧮",
            }
            icon = type_icons.get(step_type, "•")
            self._thumb_label.setText(icon)
            self._thumb_label.setStyleSheet(
                "border: 1px solid #30363d; border-radius: 4px; "
                "background-color: #161b22; color: #8b949e; font-size: 16px;"
            )
            layout.addWidget(self._thumb_label)

        # 右侧文本区
        text_container = QWidget()
        text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        # 第一行：序号 + 显示名/类型
        if display_name:
            line1 = f"{index + 1}. {display_name}  [{type_display}]"
        else:
            line1 = f"{index + 1}. {type_display}"
        if not enabled:
            line1 += "  [已禁用]"

        self._line1_label = QLabel(line1)
        self._line1_label.setFont(QFont("Microsoft YaHei", 10))
        self._line1_label.setStyleSheet("color: #c9d1d9;")
        text_layout.addWidget(self._line1_label)

        # 第二行：关键参数摘要
        summary = _format_summary(step)
        comment = step.get("comment", "")
        if comment:
            if summary:
                summary += f"  |  备注={comment}"
            else:
                summary = f"备注={comment}"

        self._line2_label = QLabel(summary)
        self._line2_label.setFont(QFont("Microsoft YaHei", 9))
        self._line2_label.setStyleSheet("color: #8b949e;")
        self._line2_label.setVisible(bool(summary))
        text_layout.addWidget(self._line2_label)

        # 第三行：跳转信息
        self._jump_label = QLabel("")
        self._jump_label.setFont(QFont("Microsoft YaHei", 9))
        self._jump_label.setStyleSheet("color: #58a6ff;")
        self._jump_label.setCursor(Qt.PointingHandCursor)
        self._jump_label.setVisible(False)
        self._jump_label.mousePressEvent = lambda event: self._on_jump_clicked()
        text_layout.addWidget(self._jump_label)

        # 第四行：跳入点标记
        self._jump_target_label = QLabel("")
        self._jump_target_label.setFont(QFont("Microsoft YaHei", 9))
        self._jump_target_label.setStyleSheet("color: #f85149;")
        self._jump_target_label.setVisible(False)
        text_layout.addWidget(self._jump_target_label)

        text_layout.addStretch(1)

        layout.addWidget(text_container, stretch=1)

        self.setMinimumHeight(52)
        self.setMaximumHeight(90)

        # 更新跳转显示
        self._update_jump_display(step)

    def set_state(self, state: str):
        """更新执行状态视觉。"""
        self._state = state
        state_style = STEP_STATE_COLORS.get(state, STEP_STATE_COLORS["pending"])
        fg = state_style["fg"]

        if state == "disabled":
            self._line1_label.setStyleSheet("color: #80484f58;")
            self._line2_label.setStyleSheet("color: #80484f58;")
            font = self._line1_label.font()
            font.setStrikeOut(True)
            self._line1_label.setFont(font)
        elif state == "running":
            self._line1_label.setStyleSheet(f"color: {fg}; font-weight: bold;")
            self._line2_label.setStyleSheet(f"color: {fg};")
        elif state == "success":
            self._line1_label.setStyleSheet(f"color: {fg};")
            self._line2_label.setStyleSheet(f"color: {fg};")
        elif state == "fail":
            self._line1_label.setStyleSheet(f"color: {fg};")
            self._line2_label.setStyleSheet(f"color: {fg};")
        else:
            self._line1_label.setStyleSheet("color: #c9d1d9;")
            self._line2_label.setStyleSheet("color: #8b949e;")

        self.update()

    def update_step_data(self, step: dict):
        """更新步骤数据（如识别结果更新后）。"""
        self._step = step
        step_type = step.get("type", "")

        # 更新缩略图
        if step_type in RECOGNITION_TYPES:
            pixmap = _get_thumbnail_pixmap(step)
            if not pixmap.isNull():
                self._thumb_pixmap = pixmap
                self._thumb_label.setPixmap(
                    pixmap.scaled(self.THUMB_SIZE, self.THUMB_SIZE,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        # 更新摘要文本
        summary = _format_summary(step)
        comment = step.get("comment", "")
        if comment:
            if summary:
                summary += f"  |  备注={comment}"
            else:
                summary = f"备注={comment}"
        self._line2_label.setText(summary)
        self._line2_label.setVisible(bool(summary))

        # 更新跳转显示
        self._update_jump_display(step)

    def _update_jump_display(self, step: dict):
        """更新跳转信息行和跳入点标记的显示。"""
        # 跳转出箭头
        jump_to = step.get("jump_to", "")
        jump_count = step.get("jump_count", 0)
        if jump_to:
            count_str = f" ×{jump_count}" if jump_count > 0 else ""
            self._jump_label.setText(f"跳转 [->{jump_to}{count_str}]")
            self._jump_label.setVisible(True)
        else:
            self._jump_label.setVisible(False)

        # 跳入点标记
        jump_label = step.get("jump_label", "")
        is_jump_target = step.get("is_jump_target", False)
        if is_jump_target and jump_label:
            self._jump_target_label.setText(f"跳入点 [{jump_label}]")
            self._jump_target_label.setVisible(True)
        else:
            self._jump_target_label.setVisible(False)

    def paintEvent(self, event):
        """绘制左侧颜色条。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 左侧颜色条
        enabled = self._step.get("enabled", True)
        color_hex = "#484f58" if not enabled or self._state == "disabled" else self._color_hex
        color = QColor(color_hex)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(0, 4, 4, self.height() - 8, 2, 2)

        painter.end()
        super().paintEvent(event)


class StepListWidget(QListWidget):
    """增强版步骤列表：缩略图、双行显示、搜索过滤、脉冲动画、拖拽指示线。"""

    step_order_changed = pyqtSignal()
    step_clicked = pyqtSignal(int)
    step_copy_requested = pyqtSignal(int)
    step_delete_requested = pyqtSignal(int)
    step_toggle_enabled = pyqtSignal(int)
    step_reset_result_requested = pyqtSignal(int)
    step_jump_clicked = pyqtSignal(str)  # 携带 jump_to 标签名

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setObjectName("stepListWidget")
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.currentRowChanged.connect(self._on_row_changed)
        self._expanded = True
        self._raw_steps: list = []
        self._step_states: dict = {}  # index -> state string
        self._filter_text = ""
        self.itemDoubleClicked.connect(self._toggle_expand)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 脉冲动画（当前执行步骤）
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_phase = 0
        self._running_index = -1

        # 拖拽指示线
        self._drop_indicator_rect = QRect()

        # 搜索框
        self._search_box = None

    def set_search_box(self, search_box: QLineEdit):
        """关联外部搜索框。"""
        self._search_box = search_box
        search_box.textChanged.connect(self._on_filter_changed)

    def _on_filter_changed(self, text):
        self._filter_text = text.strip().lower()
        self._refresh_display()

    def _on_row_changed(self, row: int):
        self.step_clicked.emit(row)

    def load_steps(self, steps: list):
        self._raw_steps = list(steps) if steps else []
        self._step_states = {}
        self._refresh_display()

    def set_step_state(self, index: int, state: str):
        """Set the execution state of a step for unified highlighting.

        States: pending, running, success, fail, skip, disabled
        """
        self._step_states[index] = state
        if state == "running":
            self._running_index = index
            if not self._pulse_timer.isActive():
                self._pulse_timer.start(100)
        elif index == self._running_index:
            self._running_index = -1
            if self._pulse_timer.isActive():
                self._pulse_timer.stop()
                self._pulse_phase = 0
        if 0 <= index < self.count():
            self._apply_step_state(index, state)

    def clear_step_states(self):
        """Reset all step states to pending."""
        self._step_states.clear()
        self._running_index = -1
        if self._pulse_timer.isActive():
            self._pulse_timer.stop()
            self._pulse_phase = 0
        for i in range(self.count()):
            self._apply_step_state(i, "pending")

    def _on_pulse_tick(self):
        """脉冲动画 tick。"""
        self._pulse_phase = (self._pulse_phase + 1) % 20
        if 0 <= self._running_index < self.count():
            rect = self.visualRect(self.indexFromItem(self.item(self._running_index)))
            if rect.isValid():
                self.viewport().update(rect)

    def _apply_step_state(self, index: int, state: str):
        """Apply visual state to a list item via its custom widget."""
        item = self.item(index)
        if item is None:
            return

        # 更新自定义 widget 的状态
        widget = self.itemWidget(item)
        if isinstance(widget, StepItemWidget):
            widget.set_state(state)

        # 同时更新 QListWidgetItem 的基本属性（用于拖拽等场景）
        state_style = STEP_STATE_COLORS.get(state, STEP_STATE_COLORS["pending"])
        if state_style["bg"]:
            item.setBackground(QColor(state_style["bg"]))
        else:
            item.setBackground(QColor(0, 0, 0, 0))
        item.setForeground(QColor(state_style["fg"]))
        font = item.font()
        font.setBold(state_style["bold"])
        font.setStrikeOut(state == "disabled")
        item.setFont(font)

    def update_step_thumbnail(self, index: int):
        """更新指定步骤的缩略图和摘要（识别结果更新后调用）。"""
        if index < 0 or index >= len(self._raw_steps):
            return
        # 找到对应的 item
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.UserRole) == index:
                widget = self.itemWidget(item)
                if isinstance(widget, StepItemWidget):
                    widget.update_step_data(self._raw_steps[index])
                break

    def _step_matches_filter(self, step: dict) -> bool:
        """检查步骤是否匹配搜索过滤。"""
        if not self._filter_text:
            return True
        step_type = step.get("type", "")
        type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
        comment = step.get("comment", "")
        return (self._filter_text in step_type.lower() or
                self._filter_text in type_display.lower() or
                self._filter_text in comment.lower())

    def _refresh_display(self):
        self.blockSignals(True)
        self.clear()
        if not self._raw_steps:
            empty = QListWidgetItem('暂无步骤 - 点击"添加步骤"开始')
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            empty.setForeground(QColor("#484f58"))
            f = empty.font()
            f.setItalic(True)
            empty.setFont(f)
            self.addItem(empty)
            self.blockSignals(False)
            return

        if self._expanded:
            for i, step in enumerate(self._raw_steps):
                # 应用搜索过滤
                if not self._step_matches_filter(step):
                    continue

                # 创建占位 QListWidgetItem
                item = QListWidgetItem()
                item.setData(Qt.UserRole, i)
                step_type = step.get("type", "unknown")
                color = STEP_TYPE_COLORS.get(step_type, "#8b949e")
                item.setData(Qt.UserRole + 1, color)

                # 创建自定义 widget
                step_widget = StepItemWidget(step, i, self)
                enabled = step.get("enabled", True)
                state = self._step_states.get(i, "pending")
                if not enabled:
                    state = "disabled"
                step_widget.set_state(state)

                # 设置 item 大小
                item.setSizeHint(QSize(0, step_widget.minimumHeight()))

                self.addItem(item)
                self.setItemWidget(item, step_widget)
        else:
            type_counts = {}
            for step in self._raw_steps:
                step_type = step.get("type", "unknown")
                type_display = STEP_TYPE_DISPLAY.get(step_type, step_type)
                type_counts[type_display] = type_counts.get(type_display, 0) + 1
            summary = "  |  ".join(f"{name}({cnt})" for name, cnt in type_counts.items())
            total = len(self._raw_steps)
            item = QListWidgetItem(f"Total {total} steps: {summary}")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.addItem(item)

        self.blockSignals(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._expanded:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制运行中步骤的脉冲边框
        if 0 <= self._running_index < self.count():
            item = self.item(self._running_index)
            rect = self.visualRect(self.indexFromItem(item))
            if rect.isValid():
                # 脉冲透明度
                alpha = int(80 + 60 * abs((self._pulse_phase / 10.0) - 1))
                pulse_color = QColor(31, 111, 235, alpha)
                painter.setPen(QPen(pulse_color, 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        # 绘制拖拽指示线
        if self._drop_indicator_rect.isValid():
            painter.setPen(QPen(QColor("#1f6feb"), 2))
            painter.setBrush(QBrush(QColor("#1f6feb")))
            y = self._drop_indicator_rect.y()
            painter.drawRect(0, y - 1, self.viewport().width(), 2)
            # 画两个小三角指示
            painter.drawRoundedRect(0, y - 4, 8, 8, 2, 2)

        painter.end()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        # 更新拖拽指示线位置
        pos = event.pos()
        row = self._get_drop_row(pos)
        if 0 <= row < self.count():
            item = self.item(row)
            rect = self.visualRect(self.indexFromItem(item))
            self._drop_indicator_rect = QRect(0, rect.y(), self.viewport().width(), 0)
        else:
            self._drop_indicator_rect = QRect()
        self.viewport().update()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self._drop_indicator_rect = QRect()
        self.viewport().update()

    def dropEvent(self, event):
        self._drop_indicator_rect = QRect()
        self.viewport().update()

        # 记录拖拽前每个 item 的原始索引
        old_order = []
        for i in range(self.count()):
            item = self.item(i)
            old_order.append(item.data(Qt.UserRole) if item else i)

        super().dropEvent(event)

        # 根据拖拽后的新视觉顺序更新 _raw_steps
        new_raw_steps = [None] * self.count()
        for i in range(self.count()):
            item = self.item(i)
            if item:
                orig_idx = item.data(Qt.UserRole)
                if orig_idx is not None and 0 <= orig_idx < len(self._raw_steps):
                    new_raw_steps[i] = self._raw_steps[orig_idx]
                # 更新 UserRole 为新索引
                item.setData(Qt.UserRole, i)

        # 填充缺失项
        for i in range(len(new_raw_steps)):
            if new_raw_steps[i] is None and i < len(self._raw_steps):
                new_raw_steps[i] = self._raw_steps[i]

        self._raw_steps = new_raw_steps
        self.step_order_changed.emit()

    def _get_drop_row(self, pos: QPoint) -> int:
        """获取拖拽位置对应的行号。"""
        item = self.itemAt(pos)
        if item:
            return self.row(item)
        # 如果在最后
        if pos.y() > self.visualRect(self.indexFromItem(self.item(self.count() - 1))).bottom():
            return self.count()
        return -1

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        index = item.data(Qt.UserRole)
        if index is None:
            return

        menu = QMenu(self)

        act_copy = menu.addAction("复制步骤  Ctrl+D")
        act_delete = menu.addAction("删除步骤  Del")
        menu.addSeparator()
        step = self._raw_steps[index] if index < len(self._raw_steps) else {}
        enabled = step.get("enabled", True)
        act_toggle = menu.addAction("禁用" if enabled else "启用  Space")
        menu.addSeparator()
        act_reset_result = menu.addAction("重置执行结果")
        menu.addSeparator()
        act_up = menu.addAction("上移")
        act_down = menu.addAction("下移")

        act_up.setEnabled(index > 0)
        act_down.setEnabled(index < len(self._raw_steps) - 1)

        action = menu.exec_(self.mapToGlobal(pos))
        if action == act_copy:
            self.step_copy_requested.emit(index)
        elif action == act_delete:
            self.step_delete_requested.emit(index)
        elif action == act_toggle:
            self.step_toggle_enabled.emit(index)
        elif action == act_reset_result:
            self.step_reset_result_requested.emit(index)
        elif action == act_up:
            self._move_step(index, index - 1)
        elif action == act_down:
            self._move_step(index, index + 1)

    def _move_step(self, from_idx, to_idx):
        if 0 <= from_idx < len(self._raw_steps) and 0 <= to_idx < len(self._raw_steps):
            self._raw_steps[from_idx], self._raw_steps[to_idx] = \
                self._raw_steps[to_idx], self._raw_steps[from_idx]
            self._refresh_display()
            self.setCurrentRow(to_idx)
            self.step_order_changed.emit()

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._refresh_display()
