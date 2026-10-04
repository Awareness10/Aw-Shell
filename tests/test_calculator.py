"""The launcher calculator (`=` queries, utils/calculator.py)."""

import pytest

from utils.calculator import evaluate, to_python


@pytest.mark.parametrize("expr, result", [
    ("2+2", "4"),
    ("2^10", "1024"),
    ("3×4", "12"),
    ("8÷2", "4"),
    ("7/2", "3.5"),
    ("1/3", "0.3333333333"),
    ("sqrt(16)", "4"),
    ("abs(-3)", "3"),
    ("sin(0)", "0"),
    ("cos(0)", "1"),
    ("log(100)", "2"),
    ("ln(1)", "0"),
    ("pi", "3.141592654"),
    ("π", "3.141592654"),
    ("2*pi", "6.283185307"),
    ("e", "2.718281828"),
    ("[2+3]*{4}", "20"),
    ("arange(3)", "[0 1 2]"),
    ("arange(20)", "Array of shape (20,)"),
])
def test_evaluate(expr, result):
    assert evaluate(expr) == result


@pytest.mark.parametrize("expr, result", [
    ("exp(0)", "1"),      # was "module 'numpy' has no attribute 'np'"
    ("exp(1)", "2.718281828"),
    ("5!", "120"),        # numpy has no factorial
    ("3!+1", "7"),
    ("1e3", "1000"),      # the e was replaced by np.e
    ("2.5e-1", "0.25"),
    ("e^2", "7.389056099"),
])
def test_regressions(expr, result):
    assert evaluate(expr) == result


def test_names_are_replaced_as_whole_words():
    assert to_python("exp(1)") == "np.exp(1)"
    assert to_python("asin(1)") == "asin(1)"  # not a supported function, left alone
    assert to_python("1e3+e") == "1e3+np.e"


@pytest.mark.parametrize("expr, error", [
    ("1/0", "division by zero"),
    ("foo", "name 'foo' is not defined"),
    ("2+", "invalid syntax"),
])
def test_errors(expr, error):
    result = evaluate(expr)
    assert result.startswith("Error: ") and error in result


def test_no_builtins():
    assert evaluate("__import__('os')").startswith("Error: ")
    assert evaluate("open('/etc/passwd')").startswith("Error: ")
