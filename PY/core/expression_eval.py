"""Safe expression evaluator for workflow variable steps.

Only allows whitelisted functions and operators to prevent code injection.
Supports arithmetic, string operations, and conditional expressions on
workflow variables.
"""
import ast
import operator
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: operator.not_,
}

SAFE_FUNCTIONS = {
    "abs": abs,
    "int": int,
    "float": float,
    "str": str,
    "len": len,
    "min": min,
    "max": max,
    "round": round,
    "bool": bool,
}


class ExpressionError(Exception):
    pass


def evaluate_expression(expr: str, variables: Optional[Dict[str, Any]] = None) -> Any:
    """Safely evaluate an expression string with given variables.

    Args:
        expr: Expression string like "price * 2 + 100" or "count > 5"
        variables: Dict of variable names to values

    Returns:
        The evaluated result

    Raises:
        ExpressionError: If the expression is invalid or uses disallowed operations
    """
    if not expr or not expr.strip():
        raise ExpressionError("Empty expression")

    variables = variables or {}

    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ExpressionError(f"Syntax error in expression: {e}") from e

    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: Dict[str, Any]) -> Any:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool)):
            return node.value
        raise ExpressionError(f"Unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.Name):
        name = node.id
        if name in variables:
            return variables[name]
        if name in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[name]
        raise ExpressionError(f"Undefined variable: {name}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ExpressionError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return SAFE_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ExpressionError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _eval_node(node.operand, variables)
        return SAFE_OPERATORS[op_type](operand)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in SAFE_OPERATORS:
                raise ExpressionError(f"Unsupported comparison: {op_type.__name__}")
            right = _eval_node(comparator, variables)
            result = SAFE_OPERATORS[op_type](left, right)
            if not result:
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ExpressionError(f"Unsupported boolean op: {op_type.__name__}")
        fn = SAFE_OPERATORS[op_type]
        values = [_eval_node(v, variables) for v in node.values]
        result = values[0]
        for v in values[1:]:
            result = fn(result, v)
        return result

    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, variables)
        if test:
            return _eval_node(node.body, variables)
        return _eval_node(node.orelse, variables)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only simple function calls are allowed")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ExpressionError(f"Unsupported function: {func_name}")
        args = [_eval_node(arg, variables) for arg in node.args]
        return SAFE_FUNCTIONS[func_name](*args)

    if isinstance(node, ast.JoinedStr):
        # f-string support
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                val = _eval_node(value.value, variables)
                parts.append(str(val))
        return "".join(parts)

    raise ExpressionError(f"Unsupported expression node: {type(node).__name__}")


def step_expression(step: dict, variables: Dict[str, Any]) -> bool:
    """Execute an expression step: evaluate and optionally assign result to a variable.

    Step fields:
        expression: The expression to evaluate
        assign_variable: (optional) Variable name to store the result
    """
    expr = step.get("expression", "")
    if not expr:
        logger.error("expression step missing 'expression' field")
        return False

    try:
        result = evaluate_expression(expr, variables)
    except ExpressionError as e:
        logger.error("Expression evaluation failed: %s", e)
        return False

    assign_var = step.get("assign_variable", "")
    if assign_var:
        variables[assign_var] = result
        logger.info("Expression result: %s = %s", assign_var, result)
    else:
        logger.info("Expression result: %s", result)

    return True
