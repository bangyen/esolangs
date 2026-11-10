"""Compile the ledger's arithmetic notation without reading prose."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
from fractions import Fraction

Formula = Callable[[int, str], int | Fraction]
type ArityCases = tuple[tuple[int | None, str], ...]
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
    reads_table_size = "T" in code.co_names

    def formula(n: int, program: str) -> int | Fraction:
        names = {
            "n": Fraction(n),
            "T": Fraction(2**n) if reads_table_size else None,
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


def arity_cases(value: object) -> ArityCases:
    """Validate contiguous positive arities with an unbounded final case."""
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("resource cases require at least two expressions")
    cases: list[tuple[int | None, str]] = []
    previous = 0
    for index, row in enumerate(value):
        last = index == len(value) - 1
        fields = {"expression"} if last else {"through", "expression"}
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("invalid resource case fields")
        through = row.get("through")
        if not last:
            if type(through) is not int or through <= previous:
                raise ValueError("resource case endpoints must increase")
            previous = through
        expression = row["expression"]
        if not isinstance(expression, str) or _python(expression) is None:
            raise ValueError("invalid resource case expression")
        cases.append((through, expression))
    return tuple(cases)


def describe_cases(cases: ArityCases, first: int, unit: str) -> str:
    """Render the same arity boundaries used for evaluation."""
    parts = []
    for through, expression in cases:
        if through is not None and through < first:
            continue
        if through is None:
            scope = f"n≥{first}"
        else:
            scope = f"n={first}" if first == through else f"n={first}..{through}"
            first = through + 1
        parts.append(f"{expression} {unit} for {scope}")
    return ", ".join(parts)


def case_formula(cases: ArityCases) -> Formula:
    """Select an expression by arity, then evaluate only that expression."""
    compiled = tuple(
        (through, expression_formula(expression)) for through, expression in cases
    )

    def formula(n: int, program: str) -> int | Fraction:
        for through, evaluate in compiled:
            if through is None or n <= through:
                return evaluate(n, program)
        raise AssertionError("validated resource cases have a final expression")

    return formula
