"""The launcher's calculator: evaluates the text after `=`."""

import math
import re

import numpy as np

_FUNCTIONS = {
    "sin": "np.sin", "cos": "np.cos", "tan": "np.tan", "sqrt": "np.sqrt",
    "abs": "np.abs", "exp": "np.exp", "log": "np.log10", "ln": "np.log",
}
_FUNCTION_CALL = re.compile(r"\b(" + "|".join(_FUNCTIONS) + r")\(")
# The constant e, not the e in 1e3 or in a name like np.exp
_E = re.compile(r"(?<![\w.])e\b")
_NAMESPACE = {
    "np": np, "math": math, "arange": np.arange, "linspace": np.linspace, "array": np.array,
}


def to_python(expr: str) -> str:
    """Calculator syntax (^, ×, ÷, π, ln, 5!, [..]) to a Python expression.
    Names are matched as whole words, so exp() and 1e3 survive."""
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace("π", "pi")
    expr = _FUNCTION_CALL.sub(lambda m: _FUNCTIONS[m.group(1)] + "(", expr)
    expr = re.sub(r"\bpi\b", "np.pi", expr)
    expr = _E.sub("np.e", expr)
    expr = re.sub(r"(\d+)!", r"math.factorial(\1)", expr)
    return expr.translate(str.maketrans("[]{}", "()()"))


def format_result(result) -> str:
    if isinstance(result, np.ndarray):
        return f"Array of shape {result.shape}" if result.size > 10 else str(result)
    if isinstance(result, (int, float, np.number)):
        if isinstance(result, (int, np.integer)) or float(result).is_integer():
            return str(int(result))
        return f"{float(result):.10g}"
    return str(result)


def evaluate(expr: str) -> str:
    """Result of expr as display text, or "Error: ..."."""
    try:
        return format_result(eval(to_python(expr), {"__builtins__": {}}, _NAMESPACE))
    except Exception as e:
        return f"Error: {e}"
