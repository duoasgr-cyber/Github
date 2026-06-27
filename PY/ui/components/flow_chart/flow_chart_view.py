"""流程图主视图。

基于 QGraphicsView + QGraphicsScene 组装节点图元和连线图元，
提供缩放/平移/选中/自适应/刷新功能。

空状态：显示「暂无主流程步骤」占位文字。
"""

from typing import Optional, Dict, List

from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QBrush
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsTextItem, QGraphicsView,
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel,
)

from ui.components.flow_chart.flow_node import (
    FlowNode, build_node_tree, flatten_nodes, NODE_BRANCH_LABEL,
)
from ui.components.flow_chart.flow_node_item import FlowNodeItem
from ui.components.flow_chart.flow_edge_item import FlowEdgeItem
from ui.components.flow_chart.flow_layout import layout


class _ZoomableGraphicsView(QGraphicsView):
    """支持 Ctrl+滚轮缩放的 QGraphicsView。"""

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setMinimumSize(200, 200)

    def wheelEvent(self, event):
        """Ctrl+滚轮缩放（0.3x ~ 3x），普通滚轮平移。"""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            new_zoom = self.transform().m11() * factor
            if 0.3 <= new_zoom <= 3.0:
                self.scale(factor, factor)
        else:
            super().wheelEvent(event)


class FlowChartView(QWidget):
    """流程图视图组件（含工具栏 + 画布）。

    信号:
        node_selected(str): 节点被选中时发射，携带 node_id
                            （顶层节点 node_id 形如 "step_0"，可用于定位列表索引）
    """

    node_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor("#0d1117")))

        self._view = _ZoomableGraphicsView(self._scene, self)
        self._view.setBackgroundBrush(QBrush(QColor("#0d1117")))
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setDragMode(QGraphicsView.ScrollHandDrag)

        self._node_items: Dict[str, FlowNodeItem] = {}
        self._edge_items: List[FlowEdgeItem] = []
        self._empty_text: Optional[QGraphicsTextItem] = None
        self._top_nodes: List[FlowNode] = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout_ = QVBoxLayout(self)
        layout_.setContentsMargins(0, 0, 0, 0)
        layout_.setSpacing(0)

        # 工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet(
            "QWidget { background-color: #161b22; border-bottom: 1px solid #30363d; }"
            "QPushButton { background: transparent; border: 1px solid #30363d;"
            "  border-radius: 3px; color: #c9d1d9; padding: 2px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #21262d; color: #e6edf3; }"
        )
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 0, 8, 0)
        toolbar_layout.setSpacing(6)

        btn_fit = QPushButton("自适应")
        btn_fit.setFixedHeight(24)
        btn_fit.setCursor(Qt.PointingHandCursor)
        btn_fit.clicked.connect(self.fit_to_viewport)
        toolbar_layout.addWidget(btn_fit)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(24, 24)
        btn_zoom_in.setCursor(Qt.PointingHandCursor)
        btn_zoom_in.clicked.connect(lambda: self._view.scale(1.2, 1.2))
        toolbar_layout.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedSize(24, 24)
        btn_zoom_out.setCursor(Qt.PointingHandCursor)
        btn_zoom_out.clicked.connect(lambda: self._view.scale(1 / 1.2, 1 / 1.2))
        toolbar_layout.addWidget(btn_zoom_out)

        btn_reset = QPushButton("100%")
        btn_reset.setFixedHeight(24)
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_zoom)
        toolbar_layout.addWidget(btn_reset)

        toolbar_layout.addStretch()

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 11px; border: none;")
        toolbar_layout.addWidget(self._status_label)

        layout_.addWidget(toolbar)
        layout_.addWidget(self._view)

    def _connect_signals(self):
        self._scene.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        selected = self._scene.selectedItems()
        for item in selected:
            if isinstance(item, FlowNodeItem):
                for ni in self._node_items.values():
                    ni.set_selected_highlight(False)
                item.set_selected_highlight(True)
                self.node_selected.emit(item.node_id)
                return
        for ni in self._node_items.values():
            ni.set_selected_highlight(False)

    def load_main_flow(self, main_flow: dict):
        """加载 main_flow 数据，重建流程图。"""
        self._clear_scene()

        nodes = build_node_tree(main_flow)
        self._top_nodes = nodes

        if not nodes:
            self._show_empty_state()
            self._status_label.setText("暂无主流程步骤")
            return

        layout_result = layout(nodes)

        # 节点图元
        all_nodes = flatten_nodes(nodes)
        for node in all_nodes:
            if node.node_id not in layout_result.positions:
                continue
            x, y = layout_result.positions[node.node_id]
            item = FlowNodeItem(node)
            item.setPos(x, y)
            self._scene.addItem(item)
            self._node_items[node.node_id] = item

        # 分支标签图元
        for label_key, (x, y) in layout_result.branch_label_positions.items():
            parts = label_key.split(":", 1)
            if len(parts) != 2:
                continue
            _, branch_key = parts
            label_node = FlowNode(
                node_id=label_key,
                node_type=NODE_BRANCH_LABEL,
                label="",
            )
            label_item = FlowNodeItem(label_node)
            label_item.set_branch_label(branch_key)
            label_item.setPos(x, y)
            label_item.setFlag(FlowNodeItem.ItemIsSelectable, False)
            self._scene.addItem(label_item)

        # 连线图元
        for edge_spec in layout_result.edges:
            src_item = self._node_items.get(edge_spec.source_id)
            tgt_item = self._node_items.get(edge_spec.target_id)
            if src_item is None or tgt_item is None:
                continue
            edge = FlowEdgeItem(
                source_pos=QPointF(
                    src_item.pos().x() + src_item.width / 2,
                    src_item.pos().y() + src_item.height,
                ),
                target_pos=QPointF(
                    tgt_item.pos().x() + tgt_item.width / 2,
                    tgt_item.pos().y(),
                ),
                edge_type=edge_spec.edge_type,
                source_node_id=edge_spec.source_id,
                target_node_id=edge_spec.target_id,
            )
            self._scene.addItem(edge)
            self._edge_items.append(edge)

        # 场景矩形
        margin = 40
        self._scene.setSceneRect(
            -margin, -margin,
            layout_result.width + margin * 2,
            layout_result.height + margin * 2,
        )

        self.fit_to_viewport()
        self._status_label.setText(
            "{} 节点 · {} 连线".format(len(all_nodes), len(self._edge_items))
        )

    def _clear_scene(self):
        self._node_items.clear()
        self._edge_items.clear()
        self._scene.clear()
        self._empty_text = None

    def _show_empty_state(self):
        self._empty_text = QGraphicsTextItem("暂无主流程步骤\n请在「列表视图」中添加步骤")
        self._empty_text.setDefaultTextColor(QColor("#8b949e"))
        self._empty_text.setFont(QFont("Microsoft YaHei", 14))
        self._empty_text.setPos(0, 0)
        self._scene.addItem(self._empty_text)
        self._scene.setSceneRect(QRectF(-200, -50, 400, 100))
        self.fit_to_viewport()

    def fit_to_viewport(self):
        """自适应视口。"""
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self._view.fitInView(rect, Qt.KeepAspectRatio)

    def _reset_zoom(self):
        self._view.resetTransform()

    def select_node_by_id(self, node_id: str):
        """程序化选中指定节点（列表→流程图联动）。"""
        for item in self._scene.selectedItems():
            item.setSelected(False)
        item = self._node_items.get(node_id)
        if item:
            item.setSelected(True)
            self._view.centerOn(item)

    def get_top_step_index(self, node_id: str) -> int:
        """根据 node_id 获取顶层步骤索引（流程图→列表联动）。

        顶层节点 node_id 形如 "step_0"，返回 0；非顶层返回 -1。
        """
        for i, node in enumerate(self._top_nodes):
            if node.node_id == node_id:
                return i
        return -1
