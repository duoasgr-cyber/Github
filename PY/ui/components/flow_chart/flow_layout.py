"""分层布局算法（Sugiyama 简化版）。

将 FlowNode 节点树分配到二维坐标：
1. 分层：BFS 按 depth 分配 Y
2. 同层排列：按执行顺序从左到右分配 X
3. 居中对齐：父节点 X = 所有子节点 X 的中位数
4. 碰撞避让：同层节点 X 重叠时整体右移

输出 LayoutResult，包含每个 node_id 的 (x, y) 坐标和边列表。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from ui.components.flow_chart.flow_node import FlowNode, NODE_STYLE


# 布局间距常量
LAYER_GAP_Y = 140          # 层间垂直间距
NODE_GAP_X = 50            # 同层节点水平间距
BRANCH_GAP_Y = 80          # 分支标签到子节点的垂直间距
BRANCH_LABEL_H = 22        # 分支标签高度


@dataclass
class EdgeSpec:
    """布局计算的边规格（节点 id 对）。"""
    source_id: str
    target_id: str
    edge_type: str = "default"  # default / then / else / body


@dataclass
class LayoutResult:
    """布局结果。"""
    positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # node_id -> (x, y)
    edges: List[EdgeSpec] = field(default_factory=list)
    branch_label_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # "node_id:branch_key" -> (x, y)
    width: float = 0.0
    height: float = 0.0


def _get_node_size(node: FlowNode) -> Tuple[float, float]:
    """从 NODE_STYLE 获取节点宽高（与 flow_node_item.py 保持一致）。"""
    style = NODE_STYLE.get(node.node_type, NODE_STYLE["default"])
    return style["w"], style["h"]


def _assign_layers(
    nodes: List[FlowNode],
) -> Dict[int, List[FlowNode]]:
    """BFS 分层：按 depth 分组。"""
    layers: Dict[int, List[FlowNode]] = {}
    for node in nodes:
        layers.setdefault(node.depth, []).append(node)
    return dict(sorted(layers.items()))


def _collect_subtree_widths(
    node: FlowNode,
    width_cache: Dict[str, float],
) -> float:
    """递归计算节点子树的视觉宽度（用于初始 X 分配）。

    叶子节点宽度 = 自身宽度 + NODE_GAP_X
    分支节点宽度 = max(then 子树宽度, else 子树宽度, body 子树宽度) + 自身宽度
    """
    if node.node_id in width_cache:
        return width_cache[node.node_id]

    own_w, _ = _get_node_size(node)
    if not node.children:
        width_cache[node.node_id] = own_w + NODE_GAP_X
        return width_cache[node.node_id]

    # 各分支子树宽度
    branch_widths = []
    for branch_key in ("then", "body", "else"):
        children = node.children.get(branch_key, [])
        if not children:
            continue
        branch_w = sum(_collect_subtree_widths(c, width_cache) for c in children)
        branch_widths.append(branch_w)

    subtree_w = max(branch_widths) if branch_widths else 0
    # 节点自身宽度与子树宽度的较大者
    total_w = max(own_w + NODE_GAP_X, subtree_w)
    width_cache[node.node_id] = total_w
    return total_w


def _assign_initial_x(
    nodes: List[FlowNode],
    current_x: List[float],
    positions: Dict[str, Tuple[float, float]],
    branch_positions: Dict[str, Tuple[float, float]],
):
    """深度优先分配初始 X 坐标。

    策略：先递归子节点，然后父节点 X = 子节点 X 范围的中点。
    同层兄弟节点从左到右排列。
    """
    for node in nodes:
        _, own_h = _get_node_size(node)

        if not node.children:
            # 叶子节点：用 current_x，然后推进
            x = current_x[0]
            positions[node.node_id] = (x, node.depth * LAYER_GAP_Y)
            own_w, _ = _get_node_size(node)
            current_x[0] = x + own_w + NODE_GAP_X
            continue

        # 有子节点：先记录起始 X，递归子节点，再回中
        start_x = current_x[0]

        # 按 then/body/else 顺序处理分支
        branch_keys = []
        if "then" in node.children:
            branch_keys.append("then")
        if "body" in node.children:
            branch_keys.append("body")
        if "else" in node.children:
            branch_keys.append("else")

        child_x_ranges = []  # 记录每个分支的 [min_x, max_x]
        for branch_key in branch_keys:
            children = node.children[branch_key]
            branch_start = current_x[0]
            _assign_initial_X_for_branch(
                node, branch_key, children, current_x, positions, branch_positions
            )
            branch_end = current_x[0] - NODE_GAP_X
            child_x_ranges.append((branch_start, branch_end))

        # 父节点 X = 子节点包围盒中心 - 自身宽度的一半（X 是左上角）
        if child_x_ranges:
            all_min = min(r[0] for r in child_x_ranges)
            all_max = max(r[1] for r in child_x_ranges)
            center_x = (all_min + all_max) / 2
            own_w, _ = _get_node_size(node)
            parent_x = center_x - own_w / 2
        else:
            parent_x = start_x

        positions[node.node_id] = (parent_x, node.depth * LAYER_GAP_Y)


def _assign_initial_X_for_branch(
    parent_node: FlowNode,
    branch_key: str,
    children: List[FlowNode],
    current_x: List[float],
    positions: Dict[str, Tuple[float, float]],
    branch_positions: Dict[str, Tuple[float, float]],
):
    """处理单个分支的子节点 + 分支标签。"""
    if not children:
        return

    # 分支标签位置：在父节点下方、子节点上方
    parent_pos = positions.get(parent_node.node_id)
    # 分支标签 X = 该分支子节点的中心 X（先递归子节点再回填）
    branch_label_key = "{}:{}".format(parent_node.node_id, branch_key)

    # 递归子节点
    _assign_initial_x(children, current_x, positions, branch_positions)

    # 计算分支标签位置
    child_xs = [positions[c.node_id][0] for c in children]
    if child_xs:
        label_x = sum(child_xs) / len(child_xs) - 35  # 标签宽 70 的一半
        label_y = children[0].depth * LAYER_GAP_Y - BRANCH_LABEL_H - 10
        branch_positions[branch_label_key] = (label_x, label_y)


def _resolve_collisions(layers: Dict[int, List[FlowNode]], positions: Dict[str, Tuple[float, float]]):
    """同层节点碰撞避让：从左到右扫描，重叠则右移。"""
    for depth in sorted(layers.keys()):
        layer_nodes = sorted(
            layers[depth],
            key=lambda n: positions[n.node_id][0],
        )
        min_gap = NODE_GAP_X
        prev_max_x = None
        for node in layer_nodes:
            x, y = positions[node.node_id]
            own_w, _ = _get_node_size(node)
            if prev_max_x is not None and x < prev_max_x + min_gap:
                new_x = prev_max_x + min_gap
                positions[node.node_id] = (new_x, y)
                x = new_x
            prev_max_x = x + own_w


def _build_edges(
    nodes: List[FlowNode],
) -> List[EdgeSpec]:
    """构建边列表。

    - 顶层节点间：顺序流转边（default）
    - 父→子分支：then/else/body 边
    - 分支内子节点间：顺序流转边
    """
    edges = []

    # 递归处理每个节点
    def process(node: FlowNode):
        # 该节点所属数组的兄弟顺序边
        # （在外层按数组处理）
        for branch_key, edge_type in [("then", "then"), ("body", "body"), ("else", "else")]:
            children = node.children.get(branch_key, [])
            if not children:
                continue
            # 父→第一个子节点
            edges.append(EdgeSpec(node.node_id, children[0].node_id, edge_type))
            # 子节点间顺序边
            for i in range(len(children) - 1):
                edges.append(EdgeSpec(children[i].node_id, children[i + 1].node_id, "default"))
            # 递归
            for c in children:
                process(c)

    # 顶层节点间顺序边
    for i in range(len(nodes) - 1):
        edges.append(EdgeSpec(nodes[i].node_id, nodes[i + 1].node_id, "default"))

    # 递归处理每个顶层节点的子树
    for node in nodes:
        process(node)

    return edges


def layout(nodes: List[FlowNode]) -> LayoutResult:
    """对节点树执行分层布局，返回 LayoutResult。

    Args:
        nodes: 顶层 FlowNode 列表（来自 build_node_tree）

    Returns:
        LayoutResult 含 positions/edges/branch_label_positions/width/height
    """
    if not nodes:
        return LayoutResult()

    result = LayoutResult()
    positions: Dict[str, Tuple[float, float]] = {}
    branch_positions: Dict[str, Tuple[float, float]] = {}

    # 第 1 步：分层
    all_nodes = _flatten_with_children(nodes)
    layers = _assign_layers(all_nodes)

    # 第 2 步：初始 X 分配（深度优先，父居中）
    current_x = [0.0]
    _assign_initial_x(nodes, current_x, positions, branch_positions)

    # 第 3 步：碰撞避让
    _resolve_collisions(layers, positions)

    # 第 4 步：构建边
    result.edges = _build_edges(nodes)

    result.positions = positions
    result.branch_label_positions = branch_positions

    # 计算整体尺寸
    if positions:
        max_x = max(x + _get_node_size(_find_node_by_id(nodes, nid))[0]
                     for nid, (x, y) in positions.items())
        max_y = max(y + _get_node_size(_find_node_by_id(nodes, nid))[1]
                     for nid, (x, y) in positions.items())
        result.width = max_x + NODE_GAP_X
        result.height = max_y + LAYER_GAP_Y

    return result


def _flatten_with_children(nodes: List[FlowNode]) -> List[FlowNode]:
    """扁平化所有节点（含子节点）。"""
    result = []
    for node in nodes:
        result.append(node)
        for child_list in node.children.values():
            result.extend(_flatten_with_children(child_list))
    return result


def _find_node_by_id(nodes: List[FlowNode], node_id: str) -> Optional[FlowNode]:
    """在节点树中按 id 查找节点。"""
    for node in nodes:
        if node.node_id == node_id:
            return node
        for child_list in node.children.values():
            found = _find_node_by_id(child_list, node_id)
            if found:
                return found
    return None
