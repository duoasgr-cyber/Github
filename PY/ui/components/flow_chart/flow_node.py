"""主流程编排可视化的数据模型。

将 ConfigManager.get_main_flow() 返回的 main_flow dict 递归转换为 FlowNode 节点树，
供布局算法和图元渲染使用。

main_flow 结构示例:
    {
        "description": "主流程说明",
        "steps": [
            {"type": "call_workflow", "workflow": "refresh_price"},
            {"type": "condition", "check": {...},
             "then_mode": "调用工作流", "then_workflow": "buy",
             "else_mode": "内嵌步骤", "else_steps": [{"type": "wait", "seconds": 2}]}
        ]
    }
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# 节点类型常量
NODE_CALL_WORKFLOW = "call_workflow"
NODE_CONDITION = "condition"
NODE_LOOP = "loop"
NODE_WAIT = "wait"
# 虚拟节点类型（仅用于流程图展示，不对应真实步骤）
NODE_BRANCH_LABEL = "branch_label"   # 分支标签（满足/不满足）
NODE_COLLAPSED = "collapsed"          # 折叠节点（超出最大深度）

# 限制可视深度，避免深层嵌套导致布局爆炸
MAX_RENDER_DEPTH = 4


# 节点视觉规范（颜色与尺寸）——纯数据，不依赖 PyQt5
# 供 flow_layout.py 和 flow_node_item.py 共享
NODE_STYLE = {
    "call_workflow": {"color": "#238636", "shape": "rect", "w": 170, "h": 44},
    "condition":      {"color": "#d29922", "shape": "diamond", "w": 180, "h": 90},
    "loop":           {"color": "#8957e5", "shape": "rect", "w": 170, "h": 44},
    "wait":           {"color": "#6e7681", "shape": "rect", "w": 130, "h": 44},
    "branch_label":   {"color": "#8b949e", "shape": "label", "w": 70, "h": 22},
    "collapsed":      {"color": "#6e7681", "shape": "rect", "w": 120, "h": 36},
    # 未知类型回退
    "default":        {"color": "#6e7681", "shape": "rect", "w": 150, "h": 44},
}


@dataclass
class FlowNode:
    """流程图节点。

    Attributes:
        node_id: 唯一标识，如 "step_0", "then_1_0"
        node_type: 节点类型（见上方常量）
        label: 显示文本
        step: 原始步骤数据（虚拟节点为 None）
        depth: 嵌套深度（顶层为 0）
        parent_id: 父节点 ID（顶层为 None）
        children: 子节点分组。condition: {"then": [...], "else": [...]}；
                  loop: {"body": [...]}；其他: {}
        step_index: 在同层数组中的索引（用于定位编辑）
    """
    node_id: str
    node_type: str
    label: str
    step: Optional[Dict[str, Any]] = None
    depth: int = 0
    parent_id: Optional[str] = None
    children: Dict[str, List["FlowNode"]] = field(default_factory=dict)
    step_index: int = 0

    def is_virtual(self) -> bool:
        """是否为虚拟节点（分支标签/折叠节点）。"""
        return self.node_type in (NODE_BRANCH_LABEL, NODE_COLLAPSED)

    def all_children(self) -> List["FlowNode"]:
        """按 then/else/body 顺序返回所有子节点。"""
        result = []
        for key in ("then", "body", "else"):
            result.extend(self.children.get(key, []))
        return result


def _make_label(step: Dict[str, Any]) -> str:
    """根据步骤类型生成显示标签。"""
    step_type = step.get("type", "")
    if step_type == NODE_CALL_WORKFLOW:
        wf = step.get("workflow", "")
        return "调用: {}".format(wf) if wf else "调用工作流(未设置)"
    if step_type == NODE_CONDITION:
        check = step.get("check", {})
        check_type = check.get("type", "") if isinstance(check, dict) else ""
        if check_type:
            return "条件: {}".format(check_type)
        return "条件判断"
    if step_type == NODE_LOOP:
        max_count = step.get("max_count", 0)
        return "循环 ×{}".format(max_count) if max_count else "循环"
    if step_type == NODE_WAIT:
        seconds = step.get("seconds", 0)
        return "等待 {}s".format(seconds)
    comment = step.get("comment", "")
    return comment or step_type


def _build_steps_tree(
    steps: List[Dict[str, Any]],
    depth: int,
    parent_id: Optional[str],
    id_prefix: str,
) -> List[FlowNode]:
    """递归将步骤数组转换为 FlowNode 列表。"""
    nodes = []
    for i, step in enumerate(steps):
        node_id = "{}{}".format(id_prefix, i)
        step_type = step.get("type", "")
        node = FlowNode(
            node_id=node_id,
            node_type=step_type,
            label=_make_label(step),
            step=step,
            depth=depth,
            parent_id=parent_id,
            step_index=i,
        )

        # 超出最大深度时折叠
        if depth >= MAX_RENDER_DEPTH:
            node.node_type = NODE_COLLAPSED
            node.label = "... (已折叠)"
            nodes.append(node)
            continue

        # condition: then/else 分支
        if step_type == NODE_CONDITION:
            then_children = _build_branch(
                step, "then", depth, node_id
            )
            else_children = _build_branch(
                step, "else", depth, node_id
            )
            node.children = {"then": then_children, "else": else_children}
        # loop: body 分支
        elif step_type == NODE_LOOP:
            body_steps = step.get("steps", [])
            body_children = _build_steps_tree(
                body_steps, depth + 1, node_id, node_id + "_body_"
            )
            node.children = {"body": body_children}

        nodes.append(node)
    return nodes


def _build_branch(
    step: Dict[str, Any],
    branch_key: str,
    depth: int,
    parent_id: str,
) -> List[FlowNode]:
    """构建 condition 的某个分支（then 或 else）。

    支持两种模式：
    - 内嵌步骤: branch_key + "_steps" 是步骤数组
    - 调用工作流: branch_key + "_workflow" 是工作流名，转换为 call_workflow 子节点
    """
    mode = step.get("{}_mode".format(branch_key), "内嵌步骤")
    children = []

    if mode == "调用工作流":
        wf_name = step.get("{}_workflow".format(branch_key), "")
        if wf_name:
            wf_node = FlowNode(
                node_id="{}_{}_wf".format(parent_id, branch_key),
                node_type=NODE_CALL_WORKFLOW,
                label="调用: {}".format(wf_name),
                step={"type": NODE_CALL_WORKFLOW, "workflow": wf_name},
                depth=depth + 1,
                parent_id=parent_id,
                step_index=0,
            )
            children.append(wf_node)
    else:
        steps = step.get("{}_steps".format(branch_key), [])
        children = _build_steps_tree(
            steps, depth + 1, parent_id, "{}_{} ".format(parent_id, branch_key)
        )

    return children


def build_node_tree(main_flow: Dict[str, Any]) -> List[FlowNode]:
    """将 main_flow dict 转换为顶层 FlowNode 列表。

    Args:
        main_flow: ConfigManager.get_main_flow() 返回的 dict

    Returns:
        顶层节点列表（每个节点可能含 children 子树）
    """
    if not main_flow:
        return []
    steps = main_flow.get("steps", [])
    if not steps:
        return []
    return _build_steps_tree(steps, depth=0, parent_id=None, id_prefix="step_")


def flatten_nodes(nodes: List[FlowNode]) -> List[FlowNode]:
    """深度优先遍历，返回所有节点（含嵌套）的扁平列表。"""
    result = []
    for node in nodes:
        result.append(node)
        for child_list in node.children.values():
            result.extend(flatten_nodes(child_list))
    return result


def find_node_by_step_index(
    nodes: List[FlowNode],
    top_index: int,
) -> Optional[FlowNode]:
    """根据顶层步骤索引查找节点（用于列表选中联动流程图）。"""
    if 0 <= top_index < len(nodes):
        return nodes[top_index]
    return None
