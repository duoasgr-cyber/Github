from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FieldGroupWidget(QWidget):
    """带颜色标识 header 的字段分组卡片。

    用于 StepEditor 中按语义分组渲染字段，每个卡片包含：
    - 带颜色圆点的 header（标题 + 可选的"投屏选点"按钮）
    - 内部 QFormLayout 供外部添加字段行
    """

    # 坐标类分组发出选点请求
    pick_requested = pyqtSignal(str)

    def __init__(self, group_key, group_def, coord_pick=False, parent=None):
        super().__init__(parent)
        self._group_key = group_key
        self._color = group_def.get("color", "#8b949e")
        self._label = group_def.get("label", group_key)
        self._coord_pick = coord_pick
        self._form_layout = None
        self._pick_button = None
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 卡片边框容器
        card = QFrame()
        card.setObjectName("fieldGroupCard")
        card.setStyleSheet(
            "QFrame#fieldGroupCard {{"
            "  border: 1px solid #30363d; border-radius: 6px;"
            "  background-color: #0d1117;"
            "}}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- Header ---
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet(
            "background-color: #161b22;"
            "border-bottom: 1px solid #30363d;"
            "border-top-left-radius: 6px;"
            "border-top-right-radius: 6px;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 8, 0)
        header_layout.setSpacing(8)

        # 颜色圆点
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            "background-color: {}; border-radius: 4px; border: none;".format(
                self._color
            )
        )
        header_layout.addWidget(dot)

        # 标题
        title = QLabel(self._label)
        title.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        title.setStyleSheet("color: #e6edf3; border: none; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # 坐标组：投屏选点按钮
        if self._coord_pick:
            btn = QPushButton("投屏选点")
            btn.setFixedHeight(20)
            btn.setFont(QFont("Microsoft YaHei", 8))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {{"
                "  background: transparent; color: {color};"
                "  border: 1px solid {color}; border-radius: 3px;"
                "  padding: 1px 8px; min-width: 40px;"
                "}}"
                "QPushButton:hover {{"
                "  background-color: {color}22;"
                "}}"
                "QPushButton:pressed {{"
                "  background-color: {color}44;"
                "}}"
            ).format(color=self._color)
            btn.clicked.connect(lambda: self.pick_requested.emit(self._group_key))
            header_layout.addWidget(btn)
            self._pick_button = btn

        card_layout.addWidget(header)

        # --- Body (form) ---
        body = QWidget()
        body.setStyleSheet("background-color: #0d1117; border: none;")
        self._form_layout = QFormLayout(body)
        self._form_layout.setContentsMargins(12, 8, 12, 8)
        self._form_layout.setSpacing(6)
        self._form_layout.setLabelAlignment(Qt.AlignRight)
        card_layout.addWidget(body)

        outer.addWidget(card)

    @property
    def form_layout(self):
        return self._form_layout

    @property
    def pick_button(self):
        return self._pick_button
