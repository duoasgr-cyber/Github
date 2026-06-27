"""流程图连线图元。

基于 QGraphicsPathItem 绘制带箭头的正交折线（非直线），避免连线交叉。
- 顺序流转: 灰色实线箭头
- 条件分支: then=绿色，else=红色
- 循环体: 紫色
"""

from typing import Optional

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPen, QPainterPath, QPainter, QPolygonF
from PyQt5.QtWidgets import QGraphicsPathItem


# 连线颜色
EDGE_COLOR_DEFAULT = QColor("#8b949e")
EDGE_COLOR_THEN = QColor("#3fb950")
EDGE_COLOR_ELSE = QColor("#f85149")
EDGE_COLOR_BODY = QColor("#8957e5")

# 箭头大小
ARROW_SIZE = 8.0


class FlowEdgeItem(QGraphicsPathItem):
    """流程图连线图元。

    连接两个节点的边缘点，绘制正交折线 + 箭头。
    """

    def __init__(
        self,
        source_pos: QPointF,
        target_pos: QPointF,
        edge_type: str = "default",
        source_node_id: str = "",
        target_node_id: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._source = source_pos
        self._target = target_pos
        self._edge_type = edge_type
        self._source_node_id = source_node_id
        self._target_node_id = target_node_id

        self._color = self._resolve_color(edge_type)
        self._build_path()
        self._apply_style()

    def _resolve_color(self, edge_type: str) -> QColor:
        if edge_type == "then":
            return EDGE_COLOR_THEN
        if edge_type == "else":
            return EDGE_COLOR_ELSE
        if edge_type == "body":
            return EDGE_COLOR_BODY
        return EDGE_COLOR_DEFAULT

    def _build_path(self):
        """构建正交折线路径。

        策略：从源点垂直向下走一段，再水平到目标 X，最后垂直到目标点。
        这样形成 L 型或 Z 型折线，避免直线穿过节点。
        """
        path = QPainterPath()
        path.moveTo(self._source)

        dx = self._target.x() - self._source.x()
        dy = self._target.y() - self._source.y()

        # 纯垂直或纯水平：直接连线
        if abs(dx) < 1:
            path.lineTo(self._target)
        elif abs(dy) < 1:
            path.lineTo(self._target)
        else:
            # Z 型折线：先垂直走一半，再水平，再垂直到目标
            mid_y = self._source.y() + dy / 2
            path.lineTo(QPointF(self._source.x(), mid_y))
            path.lineTo(QPointF(self._target.x(), mid_y))
            path.lineTo(self._target)

        self.setPath(path)

    def _apply_style(self):
        pen = QPen(self._color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(-1)  # 连线在节点下方

    def boundingRect(self) -> QRectF:
        # 扩大包围盒以容纳箭头
        rect = super().boundingRect()
        return rect.adjusted(-ARROW_SIZE, -ARROW_SIZE, ARROW_SIZE, ARROW_SIZE)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        super().paint(painter, option, widget)
        # 绘制箭头
        self._draw_arrow(painter)

    def _draw_arrow(self, painter: QPainter):
        """在目标点绘制箭头三角。"""
        # 计算箭头方向：取路径最后一段的方向
        path = self.path()
        if path.elementCount() < 2:
            return
        # 取倒数第二个点作为箭头起点
        last_elem = path.elementAt(path.elementCount() - 1)
        prev_elem = path.elementAt(path.elementCount() - 2)
        p_end = QPointF(last_elem.x, last_elem.y)
        p_prev = QPointF(prev_elem.x, prev_elem.y)

        dx = p_end.x() - p_prev.x()
        dy = p_end.y() - p_prev.y()
        length = (dx * dx + dy * dy) ** 0.5
        if length < 0.1:
            return
        ux = dx / length
        uy = dy / length

        # 箭头三角的三个点
        p1 = p_end
        p2 = QPointF(
            p_end.x() - ux * ARROW_SIZE - uy * ARROW_SIZE * 0.5,
            p_end.y() - uy * ARROW_SIZE + ux * ARROW_SIZE * 0.5,
        )
        p3 = QPointF(
            p_end.x() - ux * ARROW_SIZE + uy * ARROW_SIZE * 0.5,
            p_end.y() - uy * ARROW_SIZE - ux * ARROW_SIZE * 0.5,
        )
        arrow = QPolygonF([p1, p2, p3])
        painter.setBrush(self._color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(arrow)

    @property
    def edge_type(self) -> str:
        return self._edge_type

    @property
    def source_node_id(self) -> str:
        return self._source_node_id

    @property
    def target_node_id(self) -> str:
        return self._target_node_id


def make_edge(
    source_item,
    target_item,
    edge_type: str = "default",
    parent=None,
) -> FlowEdgeItem:
    """根据两个节点图元创建连线。

    自动计算源节点底部中点和目标节点顶部中点作为连接锚点。
    """
    from ui.components.flow_chart.flow_node_item import FlowNodeItem

    if not isinstance(source_item, FlowNodeItem) or not isinstance(target_item, FlowNodeItem):
        raise TypeError("source_item 和 target_item 必须是 FlowNodeItem")

    src_pos = source_item.pos()
    tgt_pos = target_item.pos()

    # 源点：源节点底部中点
    source_anchor = QPointF(
        src_pos.x() + source_item.width / 2,
        src_pos.y() + source_item.height,
    )
    # 目标点：目标节点顶部中点
    target_anchor = QPointF(
        tgt_pos.x() + target_item.width / 2,
        tgt_pos.y(),
    )

    return FlowEdgeItem(
        source_pos=source_anchor,
        target_pos=target_anchor,
        edge_type=edge_type,
        source_node_id=source_item.node_id,
        target_node_id=target_item.node_id,
        parent=parent,
    )
