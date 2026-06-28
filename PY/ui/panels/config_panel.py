import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGroupBox,
    QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QTimeEdit, QComboBox, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QStackedWidget,
    QFileDialog, QColorDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QTime
from PyQt5.QtGui import QFont, QColor, QFontMetrics

from core.config_manager import ConfigManager


# 配置项描述映射
CONFIG_DESCRIPTIONS = {
    "buy_params.user_price": "目标用户价格，用于判断是否触发购买",
    "buy_params.price_coefficient": "价格乘以此系数后与目标价格比较",
    "buy_params.min_price": "可接受的最低价格阈值",
    "buy_params.max_mail_count": "单次运行最大发送邮件数量",
    "mail_params.mail_count_file": "记录已发送邮件数的文件路径",
    "mail_params.auto_increment": "每次运行后自动递增邮件计数",
    "schedule.enabled": "启用后将在指定时间自动启动工作流",
    "schedule.start_time": "定时启动的触发时间（24小时制）",
    "recognition.template_threshold": "图像模板匹配的相似度阈值（0-1）",
    "recognition.template_dir": "存放图像模板文件的目录路径",
    "recognition.ocr_gpu": "使用GPU加速OCR识别（需要CUDA支持）",
    "ocr_regions.price_region": "屏幕上价格文本所在的矩形区域",
    "ocr_regions.button_region": "屏幕上按钮所在的矩形区域",
    "wifi_control.enable_cmd": "启用WiFi的ADB命令",
    "wifi_control.disable_cmd": "禁用WiFi的ADB命令",
    "device.game_package": "游戏应用的包名，用于启动/强制停止",
    "device.base_resolution": "设备的基准分辨率，用于坐标映射",
    "device.scrcpy_server_path": "scrcpy-server.jar 文件路径",
    "timing.default_wait": "步骤间默认等待时间（秒）",
    "timing.screenshot_wait": "截图后等待画面稳定的时间（秒）",
    "timing.game_start_wait": "启动游戏后等待加载的时间（秒）",
    "timing.match_wait": "图像匹配重试间隔（秒）",
    "logging.log_file": "日志文件保存路径",
    "logging.log_level": "日志输出级别",
    "logging.max_log_size_mb": "日志文件最大大小，超过后自动轮转",
    "ui.theme": "界面主题（dark/light）",
    "ui.floating_window_opacity": "悬浮窗透明度（0-1）",
    "ui.floating_window_bg": "悬浮窗背景色（十六进制）",
    "ui.price_color": "价格文字显示颜色",
    "ui.mail_color": "邮件数文字显示颜色",
    "ui.status_color": "状态文字显示颜色",
}

# 导航分类定义：(显示名, 图标, 包含的配置组前缀列表)
CONFIG_CATEGORIES = [
    ("购买与邮件", "🛒", ["buy_params", "mail_params"]),
    ("定时任务", "⏰", ["schedule"]),
    ("识别与OCR", "🔍", ["recognition", "ocr_regions"]),
    ("设备与连接", "📱", ["device", "wifi_control"]),
    ("时间参数", "⏱️", ["timing"]),
    ("日志设置", "📝", ["logging"]),
    ("界面外观", "🎨", ["ui"]),
]


class ConfigPanel(QWidget):
    """配置面板：左侧分类导航 + 右侧内容区 + 顶部搜索过滤。"""

    DEFAULT_OVERRIDES = {
        "logging.log_file": "app.log",
    }

    config_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._widgets = {}
        self._loaded = False
        self._group_widgets = {}  # group_prefix -> (group_widget, config_keys)
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
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        # ---- 左侧导航 ----
        nav_widget = QWidget()
        nav_widget.setObjectName("configNav")
        nav_widget.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        nav_header = QLabel("配置分类")
        nav_header.setObjectName("navHeader")
        nav_header.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        nav_header.setContentsMargins(12, 10, 12, 10)
        nav_layout.addWidget(nav_header)

        self._search_box = QLineEdit()
        self._search_box.setObjectName("configSearch")
        self._search_box.setPlaceholderText("搜索配置项...")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setContentsMargins(8, 8, 8, 8)
        nav_layout.addWidget(self._search_box)

        self._nav_list = QListWidget()
        self._nav_list.setObjectName("configNavList")
        self._nav_list.setSpacing(0)
        for display_name, icon, _ in CONFIG_CATEGORIES:
            item = QListWidgetItem(f"  {icon}  {display_name}")
            item.setData(Qt.UserRole, display_name)
            item.setSizeHint(item.sizeHint().expandedTo(QFontMetrics(self._nav_list.font()).size(0, item.text())))
            self._nav_list.addItem(item)
        self._nav_list.setCurrentRow(0)
        nav_layout.addWidget(self._nav_list, stretch=1)

        # ---- 右侧内容区 ----
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 内容标题栏
        self._content_title = QLabel("购买与邮件")
        self._content_title.setObjectName("configContentTitle")
        self._content_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self._content_title.setContentsMargins(16, 12, 16, 12)
        right_layout.addWidget(self._content_title)

        # 堆叠内容区
        self._content_stack = QStackedWidget()
        self._content_stack.setObjectName("configContent")

        # 搜索结果页
        self._search_result_widget = QWidget()
        sr_layout = QVBoxLayout(self._search_result_widget)
        sr_layout.setContentsMargins(16, 8, 16, 16)
        self._search_result_label = QLabel("")
        self._search_result_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        sr_layout.addWidget(self._search_result_label)
        self._search_result_scroll = QScrollArea()
        self._search_result_scroll.setWidgetResizable(True)
        self._search_result_scroll.setFrameShape(QScrollArea.NoFrame)
        self._search_result_container = QWidget()
        self._search_result_form = QVBoxLayout(self._search_result_container)
        self._search_result_form.setSpacing(8)
        self._search_result_form.addStretch()
        self._search_result_scroll.setWidget(self._search_result_container)
        sr_layout.addWidget(self._search_result_scroll, stretch=1)
        self._content_stack.addWidget(self._search_result_widget)

        # 各分类页面
        self._category_pages = {}
        for display_name, icon, prefixes in CONFIG_CATEGORIES:
            page_scroll = QScrollArea()
            page_scroll.setWidgetResizable(True)
            page_scroll.setFrameShape(QScrollArea.NoFrame)
            container = QWidget()
            page_layout = QVBoxLayout(container)
            page_layout.setSpacing(12)
            page_layout.setContentsMargins(16, 8, 16, 16)

            for prefix in prefixes:
                group_widget = self._create_group_for_prefix(prefix)
                if group_widget:
                    page_layout.addWidget(group_widget)
                    self._group_widgets[prefix] = group_widget

            page_layout.addStretch()
            page_scroll.setWidget(container)
            self._content_stack.addWidget(page_scroll)
            self._category_pages[display_name] = self._content_stack.count() - 1

        self._content_stack.setCurrentIndex(1)  # 默认显示第一个分类
        right_layout.addWidget(self._content_stack, stretch=1)

        splitter.addWidget(nav_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        outer.addWidget(splitter)

        # 连接导航切换
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        self._search_box.textChanged.connect(self._on_search_changed)

    def _create_group_for_prefix(self, prefix):
        """根据配置组前缀创建对应的 QGroupBox。"""
        creators = {
            "buy_params": self._create_buy_params_group,
            "mail_params": self._create_mail_params_group,
            "schedule": self._create_schedule_group,
            "recognition": self._create_recognition_group,
            "ocr_regions": self._create_ocr_regions_group,
            "wifi_control": self._create_wifi_control_group,
            "device": self._create_device_group,
            "timing": self._create_timing_group,
            "logging": self._create_logging_group,
            "ui": self._create_ui_group,
        }
        creator = creators.get(prefix)
        if creator:
            return creator()
        return None

    def _add_form_row_with_desc(self, form, label_text, widget, config_key):
        """添加带描述的表单行。"""
        row_widget = QWidget()
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        label_row = QHBoxLayout()
        label_row.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold; color: #e6edf3;")
        label_row.addWidget(lbl)
        label_row.addStretch()

        desc = CONFIG_DESCRIPTIONS.get(config_key, "")
        if desc:
            desc_lbl = QLabel("ⓘ")
            desc_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            desc_lbl.setToolTip(desc)
            label_row.addWidget(desc_lbl)

        row_layout.addLayout(label_row)

        widget.setToolTip(desc)
        row_layout.addWidget(widget)

        form.addRow(row_widget)

    def _create_buy_params_group(self):
        group = QGroupBox("购买参数")
        form = QFormLayout()
        form.setSpacing(8)

        user_price = QDoubleSpinBox()
        user_price.setRange(0.0, 999.0)
        user_price.setSingleStep(0.1)
        user_price.setDecimals(1)
        self._widgets["buy_params.user_price"] = user_price
        self._add_form_row_with_desc(form, "用户价格:", user_price, "buy_params.user_price")

        price_coefficient = QSpinBox()
        price_coefficient.setRange(1, 99999)
        self._widgets["buy_params.price_coefficient"] = price_coefficient
        self._add_form_row_with_desc(form, "价格系数:", price_coefficient, "buy_params.price_coefficient")

        min_price = QSpinBox()
        min_price.setRange(0, 999999999)
        self._widgets["buy_params.min_price"] = min_price
        self._add_form_row_with_desc(form, "最低价格:", min_price, "buy_params.min_price")

        max_mail_count = QSpinBox()
        max_mail_count.setRange(1, 999)
        self._widgets["buy_params.max_mail_count"] = max_mail_count
        self._add_form_row_with_desc(form, "最大邮件数:", max_mail_count, "buy_params.max_mail_count")

        group.setLayout(form)
        return group

    def _create_mail_params_group(self):
        group = QGroupBox("邮件参数")
        form = QFormLayout()
        form.setSpacing(8)

        mail_count_file = QLineEdit()
        self._widgets["mail_params.mail_count_file"] = mail_count_file
        self._add_form_row_with_desc(form, "邮件计数文件:", mail_count_file, "mail_params.mail_count_file")

        auto_increment = QCheckBox("自动递增")
        self._widgets["mail_params.auto_increment"] = auto_increment
        self._add_form_row_with_desc(form, "", auto_increment, "mail_params.auto_increment")

        group.setLayout(form)
        return group

    def _create_recognition_group(self):
        group = QGroupBox("识别参数")
        form = QFormLayout()
        form.setSpacing(8)

        template_threshold = QDoubleSpinBox()
        template_threshold.setRange(0.0, 1.0)
        template_threshold.setSingleStep(0.01)
        template_threshold.setDecimals(2)
        self._widgets["recognition.template_threshold"] = template_threshold
        self._add_form_row_with_desc(form, "模板阈值:", template_threshold, "recognition.template_threshold")

        template_dir_row = QHBoxLayout()
        template_dir = QLineEdit()
        self._widgets["recognition.template_dir"] = template_dir
        template_dir_btn = QPushButton("浏览")
        template_dir_btn.clicked.connect(lambda: self._browse_directory(template_dir))
        template_dir_row.addWidget(template_dir)
        template_dir_row.addWidget(template_dir_btn)
        dir_container = QWidget()
        dir_container.setLayout(template_dir_row)
        self._add_form_row_with_desc(form, "模板目录:", dir_container, "recognition.template_dir")

        ocr_gpu = QCheckBox("使用GPU")
        self._widgets["recognition.ocr_gpu"] = ocr_gpu
        self._add_form_row_with_desc(form, "", ocr_gpu, "recognition.ocr_gpu")

        group.setLayout(form)
        return group

    def _create_ocr_regions_group(self):
        group = QGroupBox("OCR区域")
        form = QFormLayout()
        form.setSpacing(8)

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
        price_container = QWidget()
        price_container.setLayout(price_region_row)
        self._add_form_row_with_desc(form, "价格区域:", price_container, "ocr_regions.price_region")

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
        button_container = QWidget()
        button_container.setLayout(button_region_row)
        self._add_form_row_with_desc(form, "按钮区域:", button_container, "ocr_regions.button_region")

        group.setLayout(form)
        return group

    def _create_wifi_control_group(self):
        group = QGroupBox("WiFi控制")
        form = QFormLayout()
        form.setSpacing(8)

        enable_cmd = QLineEdit()
        self._widgets["wifi_control.enable_cmd"] = enable_cmd
        self._add_form_row_with_desc(form, "启用命令:", enable_cmd, "wifi_control.enable_cmd")

        disable_cmd = QLineEdit()
        self._widgets["wifi_control.disable_cmd"] = disable_cmd
        self._add_form_row_with_desc(form, "禁用命令:", disable_cmd, "wifi_control.disable_cmd")

        group.setLayout(form)
        return group

    def _create_device_group(self):
        group = QGroupBox("设备参数")
        form = QFormLayout()
        form.setSpacing(8)

        game_package = QLineEdit()
        self._widgets["device.game_package"] = game_package
        self._add_form_row_with_desc(form, "游戏包名:", game_package, "device.game_package")

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
        res_container = QWidget()
        res_container.setLayout(res_row)
        self._add_form_row_with_desc(form, "基准分辨率:", res_container, "device.base_resolution")

        scrcpy_row = QHBoxLayout()
        scrcpy_server_path = QLineEdit()
        self._widgets["device.scrcpy_server_path"] = scrcpy_server_path
        scrcpy_btn = QPushButton("浏览")
        scrcpy_btn.clicked.connect(lambda: self._browse_file(scrcpy_server_path, "JAR文件 (*.jar);;所有文件 (*)"))
        scrcpy_row.addWidget(scrcpy_server_path)
        scrcpy_row.addWidget(scrcpy_btn)
        scrcpy_container = QWidget()
        scrcpy_container.setLayout(scrcpy_row)
        self._add_form_row_with_desc(form, "Scrcpy路径:", scrcpy_container, "device.scrcpy_server_path")

        group.setLayout(form)
        return group

    def _create_timing_group(self):
        group = QGroupBox("时间参数")
        form = QFormLayout()
        form.setSpacing(8)

        default_wait = QDoubleSpinBox()
        default_wait.setRange(0.0, 60.0)
        default_wait.setSingleStep(0.1)
        default_wait.setDecimals(1)
        self._widgets["timing.default_wait"] = default_wait
        self._add_form_row_with_desc(form, "默认等待(秒):", default_wait, "timing.default_wait")

        screenshot_wait = QDoubleSpinBox()
        screenshot_wait.setRange(0.0, 60.0)
        screenshot_wait.setSingleStep(0.1)
        screenshot_wait.setDecimals(1)
        self._widgets["timing.screenshot_wait"] = screenshot_wait
        self._add_form_row_with_desc(form, "截图等待(秒):", screenshot_wait, "timing.screenshot_wait")

        game_start_wait = QSpinBox()
        game_start_wait.setRange(1, 999)
        self._widgets["timing.game_start_wait"] = game_start_wait
        self._add_form_row_with_desc(form, "游戏启动等待(秒):", game_start_wait, "timing.game_start_wait")

        match_wait = QSpinBox()
        match_wait.setRange(1, 999)
        self._widgets["timing.match_wait"] = match_wait
        self._add_form_row_with_desc(form, "匹配等待(秒):", match_wait, "timing.match_wait")

        group.setLayout(form)
        return group

    def _create_logging_group(self):
        group = QGroupBox("日志参数")
        form = QFormLayout()
        form.setSpacing(8)

        log_file = QLineEdit()
        self._widgets["logging.log_file"] = log_file
        self._add_form_row_with_desc(form, "日志文件:", log_file, "logging.log_file")

        log_level = QComboBox()
        log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._widgets["logging.log_level"] = log_level
        self._add_form_row_with_desc(form, "日志级别:", log_level, "logging.log_level")

        max_log_size_mb = QSpinBox()
        max_log_size_mb.setRange(1, 9999)
        self._widgets["logging.max_log_size_mb"] = max_log_size_mb
        self._add_form_row_with_desc(form, "最大日志大小(MB):", max_log_size_mb, "logging.max_log_size_mb")

        group.setLayout(form)
        return group

    def _create_ui_group(self):
        group = QGroupBox("界面参数")
        form = QFormLayout()
        form.setSpacing(8)

        theme = QComboBox()
        theme.addItems(["dark", "light"])
        self._widgets["ui.theme"] = theme
        self._add_form_row_with_desc(form, "主题:", theme, "ui.theme")

        floating_window_opacity = QDoubleSpinBox()
        floating_window_opacity.setRange(0.0, 1.0)
        floating_window_opacity.setSingleStep(0.05)
        floating_window_opacity.setDecimals(2)
        self._widgets["ui.floating_window_opacity"] = floating_window_opacity
        self._add_form_row_with_desc(form, "悬浮窗透明度:", floating_window_opacity, "ui.floating_window_opacity")

        floating_window_bg = QLineEdit()
        self._widgets["ui.floating_window_bg"] = floating_window_bg
        self._add_form_row_with_desc(form, "悬浮窗背景色:", floating_window_bg, "ui.floating_window_bg")

        price_color_row = QHBoxLayout()
        price_color = QLineEdit()
        self._widgets["ui.price_color"] = price_color
        price_color_btn = QPushButton("选色")
        price_color_btn.clicked.connect(lambda: self._pick_color(price_color))
        price_color_row.addWidget(price_color)
        price_color_row.addWidget(price_color_btn)
        price_container = QWidget()
        price_container.setLayout(price_color_row)
        self._add_form_row_with_desc(form, "价格颜色:", price_container, "ui.price_color")

        mail_color_row = QHBoxLayout()
        mail_color = QLineEdit()
        self._widgets["ui.mail_color"] = mail_color
        mail_color_btn = QPushButton("选色")
        mail_color_btn.clicked.connect(lambda: self._pick_color(mail_color))
        mail_color_row.addWidget(mail_color)
        mail_color_row.addWidget(mail_color_btn)
        mail_container = QWidget()
        mail_container.setLayout(mail_color_row)
        self._add_form_row_with_desc(form, "邮件颜色:", mail_container, "ui.mail_color")

        status_color_row = QHBoxLayout()
        status_color = QLineEdit()
        self._widgets["ui.status_color"] = status_color
        status_color_btn = QPushButton("选色")
        status_color_btn.clicked.connect(lambda: self._pick_color(status_color))
        status_color_row.addWidget(status_color)
        status_color_row.addWidget(status_color_btn)
        status_container = QWidget()
        status_container.setLayout(status_color_row)
        self._add_form_row_with_desc(form, "状态颜色:", status_container, "ui.status_color")

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
        from PyQt5.QtGui import QColor
        initial = QColor(current) if current else QColor(Qt.GlobalColor.white)
        color = QColorDialog.getColor(initial)
        if color.isValid():
            line_edit.setText(color.name())

    def _on_nav_changed(self, row):
        if row < 0 or row >= len(CONFIG_CATEGORIES):
            return
        display_name = CONFIG_CATEGORIES[row][0]
        self._content_title.setText(display_name)
        # index 0 是搜索结果页，分类页从 index 1 开始
        self._content_stack.setCurrentIndex(row + 1)

    def _on_search_changed(self, text):
        text = text.strip().lower()
        if not text:
            # 恢复正常导航
            self._content_stack.setCurrentIndex(self._nav_list.currentRow() + 1)
            return

        # 搜索模式：切换到搜索结果页
        self._content_stack.setCurrentIndex(0)
        self._content_title.setText(f"搜索: \"{text}\"")

        # 清空之前的搜索结果
        while self._search_result_form.count() > 1:
            item = self._search_result_form.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        match_count = 0
        for key_path, widget in self._widgets.items():
            desc = CONFIG_DESCRIPTIONS.get(key_path, "")
            # 检查是否匹配
            if text in key_path.lower() or text in desc.lower():
                # 找到该 widget 所属的 group
                group_prefix = key_path.split(".")[0]
                group_widget = self._group_widgets.get(group_prefix)
                if group_widget and widget:
                    # 创建引用显示
                    result_item = self._create_search_result_item(key_path, widget, desc, group_prefix)
                    self._search_result_form.insertWidget(match_count, result_item)
                    match_count += 1

        if match_count == 0:
            self._search_result_label.setText(f"未找到匹配 \"{text}\" 的配置项")
        else:
            self._search_result_label.setText(f"找到 {match_count} 个匹配项")

    def _create_search_result_item(self, key_path, widget, desc, group_prefix):
        """创建搜索结果中的单个配置项显示。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题行
        header = QHBoxLayout()
        category_name = ""
        for name, _, prefixes in CONFIG_CATEGORIES:
            if group_prefix in prefixes:
                category_name = name
                break

        lbl = QLabel(f"{key_path}")
        lbl.setStyleSheet("font-weight: bold; color: #58a6ff; font-size: 12px;")
        header.addWidget(lbl)

        cat_lbl = QLabel(f"[{category_name}]")
        cat_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        header.addWidget(cat_lbl)
        header.addStretch()
        layout.addLayout(header)

        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        layout.addWidget(widget)

        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #30363d;")
        layout.addWidget(separator)

        return container

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
        self.config_changed.emit()

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
