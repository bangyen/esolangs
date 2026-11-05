"""Compile the ledger's arithmetic notation without reading prose."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
from fractions import Fraction

Formula = Callable[[int, str], int | Fraction]
_NAMES = {"n", "T", "L", "bl", "max", "min", "ceil", "floor"}


def bl(value: Fraction | int) -> int:
    """Bit length of a non-negative integer, as the ledger uses it."""
    return int(value).bit_length()


def _python(expression: str) -> str | None:
    """Return ``expression`` as Python, or None outside the notation."""
    text = expression.replace("·", "*").replace("²", "^2").replace("^", "**")
    text = re.sub(r"⌈([^⌈⌉]*)⌉", r"ceil(\1)", text)
    text = re.sub(r"⌊([^⌊⌋]*)⌋", r"floor(\1)", text)
    # Juxtaposition multiplies: 2n, 3T, 5bl(n), (n+1)T, 2(n+1).
    text = re.sub(r"(\d|\))\s*(?=[A-Za-z(])", r"\1*", text)
    text = re.sub(r"\b([nTL])\s*(?=[A-Za-z(\d])", r"\1*", text)
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return None
        if isinstance(node, ast.Name) and node.id not in _NAMES:
            return None
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name)
            or node.func.id not in {"bl", "max", "min", "ceil", "floor"}
        ):
            return None
        if isinstance(node, ast.Constant) and type(node.value) is not int:
            return None
    return text


def expression_formula(expression: str) -> Formula:
    """Return the checked arithmetic formula, rejecting unknown syntax."""
    python = _python(expression)
    if python is None:
        raise ValueError(f"invalid resource expression: {expression}")
    code = compile(python, "<ledger>", "eval")
    # A raster program has no length; only a bound that reads L asks.
    reads_length = "L" in code.co_names

    def formula(n: int, program: str) -> int | Fraction:
        names = {
            "n": Fraction(n),
            "T": Fraction(2**n),
            "L": Fraction(len(program)) if reads_length else None,
            "bl": bl,
            "max": max,
            "min": min,
            "ceil": math.ceil,
            "floor": math.floor,
        }
        value = Fraction(eval(code, {"__builtins__": {}}, names))
        return value.numerator if value.denominator == 1 else value

    return formula
