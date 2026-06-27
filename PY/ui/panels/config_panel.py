import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGroupBox,
    QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QTimeEdit, QComboBox, QPushButton,
    QHBoxLayout, QFileDialog, QColorDialog, QLabel
)
from PyQt5.QtCore import Qt, QTime

from core.config_manager import ConfigManager


class ConfigPanel(QWidget):
    DEFAULT_OVERRIDES = {
        "logging.log_file": "app.log",
    }

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._widgets = {}
        self._loaded = False
        self._init_ui()
        self._connect_signals()
        self.load_config()
        self._loaded = True

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        layout.addWidget(self._create_buy_params_group())
        layout.addWidget(self._create_mail_params_group())
        layout.addWidget(self._create_recognition_group())
        layout.addWidget(self._create_ocr_regions_group())
        layout.addWidget(self._create_wifi_control_group())
        layout.addWidget(self._create_device_group())
        layout.addWidget(self._create_timing_group())
        layout.addWidget(self._create_logging_group())
        layout.addWidget(self._create_ui_group())
        layout.addStretch()

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _create_buy_params_group(self):
        group = QGroupBox("购买参数")
        form = QFormLayout()

        user_price = QDoubleSpinBox()
        user_price.setRange(0.0, 999.0)
        user_price.setSingleStep(0.1)
        user_price.setDecimals(1)
        self._widgets["buy_params.user_price"] = user_price
        form.addRow("用户价格:", user_price)

        price_coefficient = QSpinBox()
        price_coefficient.setRange(1, 99999)
        self._widgets["buy_params.price_coefficient"] = price_coefficient
        form.addRow("价格系数:", price_coefficient)

        min_price = QSpinBox()
        min_price.setRange(0, 999999999)
        self._widgets["buy_params.min_price"] = min_price
        form.addRow("最低价格:", min_price)

        max_mail_count = QSpinBox()
        max_mail_count.setRange(1, 999)
        self._widgets["buy_params.max_mail_count"] = max_mail_count
        form.addRow("最大邮件数:", max_mail_count)

        group.setLayout(form)
        return group

    def _create_mail_params_group(self):
        group = QGroupBox("邮件参数")
        form = QFormLayout()

        mail_count_file = QLineEdit()
        self._widgets["mail_params.mail_count_file"] = mail_count_file
        form.addRow("邮件计数文件:", mail_count_file)

        auto_increment = QCheckBox("自动递增")
        self._widgets["mail_params.auto_increment"] = auto_increment
        form.addRow("", auto_increment)

        group.setLayout(form)
        return group

    def _create_recognition_group(self):
        group = QGroupBox("识别参数")
        form = QFormLayout()

        template_threshold = QDoubleSpinBox()
        template_threshold.setRange(0.0, 1.0)
        template_threshold.setSingleStep(0.01)
        template_threshold.setDecimals(2)
        self._widgets["recognition.template_threshold"] = template_threshold
        form.addRow("模板阈值:", template_threshold)

        template_dir_row = QHBoxLayout()
        template_dir = QLineEdit()
        self._widgets["recognition.template_dir"] = template_dir
        template_dir_btn = QPushButton("浏览")
        template_dir_btn.clicked.connect(lambda: self._browse_directory(template_dir))
        template_dir_row.addWidget(template_dir)
        template_dir_row.addWidget(template_dir_btn)
        form.addRow("模板目录:", template_dir_row)

        ocr_gpu = QCheckBox("使用GPU")
        self._widgets["recognition.ocr_gpu"] = ocr_gpu
        form.addRow("", ocr_gpu)

        group.setLayout(form)
        return group

    def _create_ocr_regions_group(self):
        group = QGroupBox("OCR区域")
        form = QFormLayout()

        price_region_row = QHBoxLayout()
        price_left = QSpinBox()
        price_left.setRange(0, 99999)
        self._widgets["ocr_regions.price_region.left"] = price_left
        price_top = QSpinBox()
        price_top.setRange(0, 99999)
        self._widgets["ocr_regions.price_region.top"] = price_top
        price_right = QSpinBox()
        price_right.setRange(0, 99999)
        self._widgets["ocr_regions.price_region.right"] = price_right
        price_bottom = QSpinBox()
        price_bottom.setRange(0, 99999)
        self._widgets["ocr_regions.price_region.bottom"] = price_bottom
        for label, sb in [("L", price_left), ("T", price_top), ("R", price_right), ("B", price_bottom)]:
            price_region_row.addWidget(QLabel(label))
            price_region_row.addWidget(sb)
        form.addRow("价格区域:", price_region_row)

        button_region_row = QHBoxLayout()
        button_left = QSpinBox()
        button_left.setRange(0, 99999)
        self._widgets["ocr_regions.button_region.left"] = button_left
        button_top = QSpinBox()
        button_top.setRange(0, 99999)
        self._widgets["ocr_regions.button_region.top"] = button_top
        button_right = QSpinBox()
        button_right.setRange(0, 99999)
        self._widgets["ocr_regions.button_region.right"] = button_right
        button_bottom = QSpinBox()
        button_bottom.setRange(0, 99999)
        self._widgets["ocr_regions.button_region.bottom"] = button_bottom
        for label, sb in [("L", button_left), ("T", button_top), ("R", button_right), ("B", button_bottom)]:
            button_region_row.addWidget(QLabel(label))
            button_region_row.addWidget(sb)
        form.addRow("按钮区域:", button_region_row)

        group.setLayout(form)
        return group

    def _create_wifi_control_group(self):
        group = QGroupBox("WiFi控制")
        form = QFormLayout()

        enable_cmd = QLineEdit()
        self._widgets["wifi_control.enable_cmd"] = enable_cmd
        form.addRow("启用命令:", enable_cmd)

        disable_cmd = QLineEdit()
        self._widgets["wifi_control.disable_cmd"] = disable_cmd
        form.addRow("禁用命令:", disable_cmd)

        group.setLayout(form)
        return group

    def _create_device_group(self):
        group = QGroupBox("设备参数")
        form = QFormLayout()

        game_package = QLineEdit()
        self._widgets["device.game_package"] = game_package
        form.addRow("游戏包名:", game_package)

        res_row = QHBoxLayout()
        base_width = QSpinBox()
        base_width.setRange(1, 99999)
        self._widgets["device.base_resolution.width"] = base_width
        base_height = QSpinBox()
        base_height.setRange(1, 99999)
        self._widgets["device.base_resolution.height"] = base_height
        res_row.addWidget(QLabel("宽:"))
        res_row.addWidget(base_width)
        res_row.addWidget(QLabel("高:"))
        res_row.addWidget(base_height)
        form.addRow("基准分辨率:", res_row)

        scrcpy_row = QHBoxLayout()
        scrcpy_server_path = QLineEdit()
        self._widgets["device.scrcpy_server_path"] = scrcpy_server_path
        scrcpy_btn = QPushButton("浏览")
        scrcpy_btn.clicked.connect(lambda: self._browse_file(scrcpy_server_path, "JAR文件 (*.jar);;所有文件 (*)"))
        scrcpy_row.addWidget(scrcpy_server_path)
        scrcpy_row.addWidget(scrcpy_btn)
        form.addRow("Scrcpy路径:", scrcpy_row)

        group.setLayout(form)
        return group

    def _create_timing_group(self):
        group = QGroupBox("时间参数")
        form = QFormLayout()

        default_wait = QDoubleSpinBox()
        default_wait.setRange(0.0, 60.0)
        default_wait.setSingleStep(0.1)
        default_wait.setDecimals(1)
        self._widgets["timing.default_wait"] = default_wait
        form.addRow("默认等待(秒):", default_wait)

        screenshot_wait = QDoubleSpinBox()
        screenshot_wait.setRange(0.0, 60.0)
        screenshot_wait.setSingleStep(0.1)
        screenshot_wait.setDecimals(1)
        self._widgets["timing.screenshot_wait"] = screenshot_wait
        form.addRow("截图等待(秒):", screenshot_wait)

        game_start_wait = QSpinBox()
        game_start_wait.setRange(1, 999)
        self._widgets["timing.game_start_wait"] = game_start_wait
        form.addRow("游戏启动等待(秒):", game_start_wait)

        match_wait = QSpinBox()
        match_wait.setRange(1, 999)
        self._widgets["timing.match_wait"] = match_wait
        form.addRow("匹配等待(秒):", match_wait)

        group.setLayout(form)
        return group

    def _create_logging_group(self):
        group = QGroupBox("日志参数")
        form = QFormLayout()

        log_file = QLineEdit()
        self._widgets["logging.log_file"] = log_file
        form.addRow("日志文件:", log_file)

        log_level = QComboBox()
        log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._widgets["logging.log_level"] = log_level
        form.addRow("日志级别:", log_level)

        max_log_size_mb = QSpinBox()
        max_log_size_mb.setRange(1, 9999)
        self._widgets["logging.max_log_size_mb"] = max_log_size_mb
        form.addRow("最大日志大小(MB):", max_log_size_mb)

        group.setLayout(form)
        return group

    def _create_ui_group(self):
        group = QGroupBox("界面参数")
        form = QFormLayout()

        theme = QComboBox()
        theme.addItems(["dark", "light"])
        self._widgets["ui.theme"] = theme
        form.addRow("主题:", theme)

        floating_window_opacity = QDoubleSpinBox()
        floating_window_opacity.setRange(0.0, 1.0)
        floating_window_opacity.setSingleStep(0.05)
        floating_window_opacity.setDecimals(2)
        self._widgets["ui.floating_window_opacity"] = floating_window_opacity
        form.addRow("悬浮窗透明度:", floating_window_opacity)

        floating_window_bg = QLineEdit()
        self._widgets["ui.floating_window_bg"] = floating_window_bg
        form.addRow("悬浮窗背景色:", floating_window_bg)

        price_color_row = QHBoxLayout()
        price_color = QLineEdit()
        self._widgets["ui.price_color"] = price_color
        price_color_btn = QPushButton("选色")
        price_color_btn.clicked.connect(lambda: self._pick_color(price_color))
        price_color_row.addWidget(price_color)
        price_color_row.addWidget(price_color_btn)
        form.addRow("价格颜色:", price_color_row)

        mail_color_row = QHBoxLayout()
        mail_color = QLineEdit()
        self._widgets["ui.mail_color"] = mail_color
        mail_color_btn = QPushButton("选色")
        mail_color_btn.clicked.connect(lambda: self._pick_color(mail_color))
        mail_color_row.addWidget(mail_color)
        mail_color_row.addWidget(mail_color_btn)
        form.addRow("邮件颜色:", mail_color_row)

        status_color_row = QHBoxLayout()
        status_color = QLineEdit()
        self._widgets["ui.status_color"] = status_color
        status_color_btn = QPushButton("选色")
        status_color_btn.clicked.connect(lambda: self._pick_color(status_color))
        status_color_row.addWidget(status_color)
        status_color_row.addWidget(status_color_btn)
        form.addRow("状态颜色:", status_color_row)

        group.setLayout(form)
        return group

    def _browse_directory(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            line_edit.setText(path)

    def _browse_file(self, line_edit, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter_str)
        if path:
            line_edit.setText(path)

    def _pick_color(self, line_edit):
        current = line_edit.text().strip()
        color = QColorDialog.getColor(current)
        if color.isValid():
            line_edit.setText(color.name())

    def load_config(self):
        for key_path, widget in self._widgets.items():
            value = self._config_manager.get_config(key_path)
            if value is None or (isinstance(value, str) and not value.strip()):
                value = self.DEFAULT_OVERRIDES.get(key_path, value)
            if value is None:
                continue
            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QTimeEdit):
                if isinstance(value, str) and value:
                    t = QTime.fromString(value, "HH:mm")
                    if t.isValid():
                        widget.setTime(t)

    def _resolve_config_value(self, key_path: str, value):
        if isinstance(value, str) and not value.strip():
            return self.DEFAULT_OVERRIDES.get(key_path, value)
        return value

    def save_config(self):
        for key_path, widget in self._widgets.items():
            if isinstance(widget, QDoubleSpinBox):
                self._config_manager.set_config(key_path, widget.value())
            elif isinstance(widget, QSpinBox):
                self._config_manager.set_config(key_path, widget.value())
            elif isinstance(widget, QLineEdit):
                self._config_manager.set_config(key_path, self._resolve_config_value(key_path, widget.text()))
            elif isinstance(widget, QCheckBox):
                self._config_manager.set_config(key_path, widget.isChecked())
            elif isinstance(widget, QComboBox):
                self._config_manager.set_config(key_path, widget.currentText())
            elif isinstance(widget, QTimeEdit):
                self._config_manager.set_config(key_path, widget.time().toString("HH:mm"))

    def _on_value_changed(self):
        if not self._loaded:
            return
        self.save_config()

    def _connect_signals(self):
        for widget in self._widgets.values():
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.valueChanged.connect(self._on_value_changed)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._on_value_changed)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._on_value_changed)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._on_value_changed)
            elif isinstance(widget, QTimeEdit):
                widget.timeChanged.connect(self._on_value_changed)
