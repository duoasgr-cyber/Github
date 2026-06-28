"""变量与表达式类 step 处理器：variable/expression 及变量管理"""
import logging

from core.expression_eval import step_expression

logger = logging.getLogger(__name__)


class VarsMixin:
    """变量处理与表达式求值的混入。依赖主类的 _variables。"""

    def _step_variable(self, step: dict) -> bool:
        var_name = step.get("var_name", "")
        var_type = step.get("var_type", "string")
        var_value = step.get("var_value", "")
        if not var_name:
            logger.error("variable step missing var_name")
            return False
        try:
            if var_type == "bool":
                self._variables[var_name] = str(var_value).lower() in ("true", "1", "yes")
            elif var_type == "int":
                self._variables[var_name] = int(var_value)
            else:
                self._variables[var_name] = str(var_value)
            logger.info("Variable set: %s = %s (%s)", var_name, self._variables[var_name], var_type)
            return True
        except (ValueError, TypeError) as e:
            logger.error("Variable assignment failed: %s", e)
            return False

    def _step_expression(self, step: dict) -> bool:
        """Execute an expression step using the safe evaluator."""
        return step_expression(step, self._variables)

    def get_variable(self, name: str, default=None):
        return self._variables.get(name, default)

    def set_variable(self, name: str, value) -> None:
        self._variables[name] = value

    def clear_variables(self) -> None:
        self._variables.clear()
