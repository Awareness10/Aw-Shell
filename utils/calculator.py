"""The launcher's calculator: evaluates the text after `=`."""

import math
import operator
import re
from collections.abc import Callable
from typing import Any

# Calculator values: numbers, or (nested) lists of them
Op = Callable[[Any, Any], Any]


class _Array(list[Any]):
    """A list whose arithmetic works element by element (arange(3)*2 is
    [0 2 4], not the list repeated), with a scalar or a same-length list."""

    def _apply(self, other: Any, op: Op) -> "_Array":
        if isinstance(other, (list, tuple)):
            if len(other) != len(self):
                raise ValueError(f"operands could not be broadcast together with lengths "
                                 f"{len(self)} and {len(other)}")
            return _Array(op(a, b) for a, b in zip(self, other, strict=False))
        return _Array(op(a, other) for a in self)

    def __neg__(self) -> "_Array":
        return _Array(-a for a in self)

    def __pos__(self) -> "_Array":
        return self

    def __abs__(self) -> "_Array":
        return _Array(abs(a) for a in self)


def _binary(op: Op) -> tuple[Callable[[_Array, Any], _Array], Callable[[_Array, Any], _Array]]:
    return (lambda self, other: self._apply(other, op),
            lambda self, other: self._apply(other, lambda a, b: op(b, a)))


for _name, _op in {"add": operator.add, "sub": operator.sub, "mul": operator.mul,
                   "truediv": operator.truediv, "floordiv": operator.floordiv,
                   "mod": operator.mod, "pow": operator.pow}.items():
    _forward, _reflected = _binary(_op)
    setattr(_Array, f"__{_name}__", _forward)
    setattr(_Array, f"__r{_name}__", _reflected)


def _elementwise(function: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """function on a number, or on each element of a list; results outside
    the real numbers are nan or ±inf, not errors (sqrt(-1) is nan, ln(0)
    is -inf)."""
    def apply(x: Any) -> Any:
        if isinstance(x, (list, tuple)):
            return _Array(apply(v) for v in x)
        try:
            return function(x)
        except ValueError:
            return -math.inf if x == 0 else math.nan
        except OverflowError:
            return math.inf
    apply.__name__ = getattr(function, "__name__", apply.__name__)
    return apply


def arange(start: Any, stop: Any = None, step: Any = 1) -> _Array:
    """[start, stop) in steps; whole numbers stay whole."""
    if stop is None:
        start, stop = 0, start
    if step == 0:
        raise ValueError("step must not be zero")
    count = max(0, math.ceil((stop - start) / step))
    if all(isinstance(v, int) for v in (start, stop, step)):
        return _Array(start + i * step for i in range(count))
    return _Array(float(start + i * step) for i in range(count))


def linspace(start: Any, stop: Any, num: Any = 50, endpoint: bool = True) -> _Array:
    """num evenly spaced numbers from start to stop."""
    num = operator.index(num)
    if num < 0:
        raise ValueError(f"Number of samples, {num}, must be non-negative.")
    if num == 1:
        return _Array([float(start)])
    step = (stop - start) / ((num - 1) if endpoint else num)
    values = _Array(float(start + i * step) for i in range(num))
    if endpoint and num:
        values[-1] = float(stop)
    return values


def array(values: Any) -> Any:
    """values (nested lists or tuples) as an array."""
    if isinstance(values, (list, tuple)):
        return _Array(array(v) for v in values)
    return values


_NAMESPACE = {
    "sin": _elementwise(math.sin), "cos": _elementwise(math.cos),
    "tan": _elementwise(math.tan), "sqrt": _elementwise(math.sqrt),
    "abs": _elementwise(abs), "exp": _elementwise(math.exp),
    "log": _elementwise(math.log10), "ln": _elementwise(math.log),
    "pi": math.pi, "e": math.e,
    "math": math, "arange": arange, "linspace": linspace, "array": array,
}


def to_python(expr: str) -> str:
    """Calculator syntax (^, ×, ÷, π, 5!, [..]) to a Python expression.
    Functions and constants (exp, ln, e) are plain names in the namespace,
    so exp() and 1e3 survive."""
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace("π", "pi")
    expr = re.sub(r"(\d+)!", r"math.factorial(\1)", expr)
    return expr.translate(str.maketrans("[]{}", "()()"))


def _shape(values: Any) -> tuple[int, ...]:
    if not isinstance(values, list):
        return ()
    return (len(values),) + (_shape(values[0]) if values else ())


def format_result(result: Any) -> str:
    if isinstance(result, list):
        size = math.prod(_shape(result))
        if size > 10:
            return f"Array of shape {_shape(result)}"
        return "[" + " ".join(format_result(v) for v in result) + "]"
    if isinstance(result, (int, float)):
        if isinstance(result, int) or result.is_integer():
            return str(int(result))
        return f"{result:.10g}"
    return str(result)


def evaluate(expr: str) -> str:
    """Result of expr as display text, or "Error: ..."."""
    try:
        result = eval(to_python(expr), {"__builtins__": {}}, _NAMESPACE)
        if callable(result):  # a bare function name ("sin") isn't a result
            raise NameError(f"name '{expr.strip()}' is not defined")
        return format_result(result)
    except Exception as e:
        return f"Error: {e}"
