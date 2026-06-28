import ast
import logging
import operator

logger = logging.getLogger(__name__)

# 安全的二元运算映射
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 安全的一元运算映射
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 安全的比较运算映射
_SAFE_CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class _SafeExprVisitor(ast.NodeVisitor):
    """AST 访问器，检查表达式是否只包含安全节点。"""

    _ALLOWED_NODES = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare,
        ast.Constant, ast.Name, ast.Load,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.UAdd, ast.USub,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    )

    def generic_visit(self, node):
        if not isinstance(node, self._ALLOWED_NODES):
            raise ValueError(f"不支持的表达式节点: {type(node).__name__}")
        super().generic_visit(node)


def _eval_node(node, variables: dict):
    """递归求值 AST 节点。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        raise ValueError(f"未定义的变量: {node.id}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return _SAFE_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_UNARYOPS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        operand = _eval_node(node.operand, variables)
        return _SAFE_UNARYOPS[op_type](operand)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _SAFE_CMPOPS:
                raise ValueError(f"不支持的比较运算符: {op_type.__name__}")
            right = _eval_node(comparator, variables)
            if not _SAFE_CMPOPS[op_type](left, right):
                return False
            left = right
        return True
    raise ValueError(f"不支持的节点类型: {type(node).__name__}")


def evaluate_expression(expression: str, variables: dict = None) -> object:
    """安全求值简单表达式，支持变量、算术和比较运算。

    支持的语法：
    - 数字和字符串字面量
    - 变量引用（从 variables 字典查找）
    - 算术运算: +, -, *, /, //, %, **
    - 比较运算: ==, !=, <, <=, >, >=

    不支持：函数调用、属性访问、下标、列表/字典推导等。
    """
    if variables is None:
        variables = {}
    try:
        tree = ast.parse(expression, mode='eval')
        _SafeExprVisitor().visit(tree)
        return _eval_node(tree.body, variables)
    except Exception as e:
        logger.warning("Expression evaluation failed: %s -> %s", expression, e)
        raise ValueError(f"Expression evaluation failed: {e}")
