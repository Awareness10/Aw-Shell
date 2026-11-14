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


def test_names_are_left_whole():
    assert to_python("exp(1)") == "exp(1)"
    assert to_python("1e3+e") == "1e3+e"
    assert to_python("2^3×4÷π") == "2**3*4/pi"
    assert to_python("[1]+{5!}") == "(1)+(math.factorial(5))"


@pytest.mark.parametrize("expr, result", [
    ("1e3+e", "1002.718282"),
    ("asin(1)", "Error: name 'asin' is not defined"),  # not a supported function
    ("tan(pi/4)", "1"),
    ("cos(pi)", "-1"),
    ("log(2)", "0.3010299957"),
    ("ln(e)", "1"),
    ("abs(-2.5)", "2.5"),
    ("math.floor(2.5)", "2"),
    ("10^20", "100000000000000000000"),
    ("2>1", "1"),
])
def test_functions_and_constants(expr, result):
    assert evaluate(expr) == result


@pytest.mark.parametrize("expr, result", [
    ("sqrt(-1)", "nan"),
    ("log(-1)", "nan"),
    ("ln(0)", "-inf"),
    ("exp(1000)", "inf"),
])
def test_outside_the_reals_is_nan_or_inf(expr, result):
    assert evaluate(expr) == result


@pytest.mark.parametrize("expr, result", [
    ("arange(1, 4)", "[1 2 3]"),
    ("arange(0, 1, 0.25)", "[0 0.25 0.5 0.75]"),
    ("arange(5, 0, -2)", "[5 3 1]"),
    ("arange(0)", "[]"),
    ("linspace(0, 1, 3)", "[0 0.5 1]"),
    ("linspace(0, 1, 4, False)", "[0 0.25 0.5 0.75]"),
    ("linspace(2, 2, 1)", "[2]"),
    ("linspace(0, 10)", "Array of shape (50,)"),
    ("array([1, 2, 3])", "[1 2 3]"),
    ("array([[1, 2], [3, 4]])", "[[1 2] [3 4]]"),
    ("array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]])", "Array of shape (3, 4)"),
])
def test_arrays(expr, result):
    assert evaluate(expr) == result


@pytest.mark.parametrize("expr, result", [
    ("arange(3)*2", "[0 2 4]"),     # element by element, not the list repeated
    ("2*arange(3)", "[0 2 4]"),
    ("arange(3)+arange(3)", "[0 2 4]"),
    ("arange(3)+1", "[1 2 3]"),
    ("10-arange(3)", "[10 9 8]"),
    ("arange(3)/2", "[0 0.5 1]"),
    ("arange(3)^2", "[0 1 4]"),
    ("-arange(3)", "[0 -1 -2]"),
    ("array([[1, 2], [3, 4]])*2", "[[2 4] [6 8]]"),
    ("sin(arange(2))", "[0 0.8414709848]"),
    ("sqrt([4, 9])", "[2 3]"),
    ("abs(array([-1, 2]))", "[1 2]"),
])
def test_array_arithmetic(expr, result):
    assert evaluate(expr) == result


def test_arrays_of_different_lengths():
    assert evaluate("arange(2)+arange(3)").startswith("Error: ")


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
