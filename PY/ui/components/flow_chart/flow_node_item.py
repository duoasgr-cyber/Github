"""流程图节点图元。

基于 QGraphicsItem 自绘不同形状的节点：
- 圆角矩形: call_workflow / loop / wait / collapsed
- 菱形: condition
- 小标签: branch_label（满足/不满足）

匹配现有深色主题（#0d1117 背景）。
"""

from typing import Optional

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (
    QColor, QFont, QPen, QBrush, QPainter, QPainterPath,
)
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsTextItem

from ui.components.flow_chart.flow_node import FlowNode, NODE_STYLE


# 分支标签颜色
BRANCH_LABEL_TEXT = {
    "then": ("满足", "#3fb950"),
    "body": ("循环体", "#8957e5"),
    "else": ("不满足", "#f85149"),
}


class FlowNodeItem(QGraphicsItem):
    """流程图节点图元。

    通过 setPos() 定位，boundingRect() 返回自身包围盒。
    选中时边框加粗高亮。
    """

    def __init__(self, node: FlowNode, parent=None):
        super().__init__(parent)
        self._node = node
        self._style = NODE_STYLE.get(node.node_type, NODE_STYLE["default"])
        self._w = self._style["w"]
        self._h = self._style["h"]
        self._color = QColor(self._style["color"])
        self._selected = False
        self._branch_key: Optional[str] = None  # 用于分支标签
        self._branch_text = ""
        self._branch_color = QColor("#8b949e")

        # 启用悬停与选中
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        # 文字图元（作为子项，简化文字绘制）
        self._text_item = QGraphicsTextItem(self)
        self._text_item.setDefaultTextColor(QColor("#e6edf3"))
        self._text_item.setFont(QFont("Microsoft YaHei", 9))
        self._update_text()

    def _update_text(self):
        """更新文字内容与居中位置。"""
        if self._node.node_type == "branch_label":
            self._text_item.setPlainText(self._branch_text)
            self._text_item.setDefaultTextColor(self._branch_color)
            self._text_item.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
        else:
            self._text_item.setPlainText(self._node.label)
        # 居中
        text_w = self._text_item.boundingRect().width()
        text_h = self._text_item.boundingRect().height()
        self._text_item.setPos(
            (self._w - text_w) / 2,
            (self._h - text_h) / 2,
        )

    def set_branch_label(self, branch_key: str):
        """设置为分支标签节点。"""
        text, color = BRANCH_LABEL_TEXT.get(branch_key, ("", "#8b949e"))
        self._branch_text = text
        self._branch_color = QColor(color)
        self._branch_key = branch_key
        self._update_text()

    @property
    def node(self) -> FlowNode:
        return self._node

    @property
    def node_id(self) -> str:
        return self._node.node_id

    @property
    def width(self) -> float:
        return self._w

    @property
    def height(self) -> float:
        return self._h

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def shape(self) -> QPainterPath:
        """用于精确命中测试（菱形按菱形命中）。"""
        path = QPainterPath()
        shape_type = self._style["shape"]
        if shape_type == "diamond":
            path.moveTo(self._w / 2, 0)
            path.lineTo(self._w, self._h / 2)
            path.lineTo(self._w / 2, self._h)
            path.lineTo(0, self._h / 2)
            path.closeSubpath()
        else:
            path.addRoundedRect(0, 0, self._w, self._h, 6, 6)
        return path

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        shape_type = self._style["shape"]

        # 填充
        if self._selected:
            fill_color = self._color.lighter(130)
            border_color = QColor("#ffffff")
            border_width = 2.5
        else:
            fill_color = self._color
            border_color = self._color.lighter(150)
            border_width = 1.5

        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(border_color, border_width))

        if shape_type == "diamond":
            self._paint_diamond(painter)
        elif shape_type == "label":
            self._paint_label(painter)
        else:
            painter.drawRoundedRect(0, 0, self._w, self._h, 6, 6)

    def _paint_diamond(self, painter: QPainter):
        """绘制菱形。"""
        w, h = self._w, self._h
        path = QPainterPath()
        path.moveTo(w / 2, 0)
        path.lineTo(w, h / 2)
        path.lineTo(w / 2, h)
        path.lineTo(0, h / 2)
        path.closeSubpath()
        painter.drawPath(path)

    def _paint_label(self, painter: QPainter):
        """绘制小标签（无边框，仅背景）。"""
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._branch_color.darker(200)))
        painter.drawRoundedRect(0, 0, self._w, self._h, 4, 4)
        # 顶部彩色细条
        painter.setBrush(QBrush(self._branch_color))
        painter.drawRect(0, 0, self._w, 3)

    def set_selected_highlight(self, selected: bool):
        """设置选中高亮状态（不触发场景选中机制）。"""
        self._selected = selected
        self.update()

    def hoverEnterEvent(self, event):
        self._selected = True
        self.update()
        # Tooltip 显示步骤 JSON
        import json
        if self._node.step:
            tip = json.dumps(self._node.step, ensure_ascii=False, indent=2)
            self.setToolTip(tip[:500])  # 限制长度
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._selected = False
        self.update()
        super().hoverLeaveEvent(event)
