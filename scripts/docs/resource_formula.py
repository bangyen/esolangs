"""Compile the ledger's arithmetic notation without reading prose."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from fractions import Fraction
from functools import partial

from esolangs.generation.decision import residual_count_bound

Formula = Callable[[int, str], int | Fraction]
TermProvider = Callable[[int, str], Mapping[str, int | Fraction]]
type SourceTerms = tuple[frozenset[str], TermProvider]
type ArityCases = tuple[tuple[int | None, str], ...]
_FUNCTIONS = {
    "bl",
    "bit_sum",
    "digits",
    "digits_sum",
    "max",
    "min",
    "ceil",
    "floor",
    "power2_digits_sum",
    "weighted_bit_sum",
    "weighted_decimal_sum",
    "isqrt",
    "residuals",
    "residuals_without_constants",
}
_NAMES = {"n", "T", "L"} | _FUNCTIONS


def bl(value: Fraction | int) -> int:
    """Bit length of a non-negative integer, as the ledger uses it."""
    return int(value).bit_length()


def _bit_sum(value: int | Fraction) -> int:
    """Sum the bit lengths of the non-negative integers below value."""
    count = int(value)
    if count < 0 or count != value:
        raise ValueError("resource bit sum requires a non-negative integer")
    if count == 0:
        return 0
    # Each power of two below count contributes one bit to the rest of the range.
    width = (count - 1).bit_length()
    return count * width - (1 << width) + 1


def _digits(value: int | Fraction) -> int:
    """Count decimal digits without consulting the process's int/str cap."""
    integer = int(value)
    if integer < 0 or integer != value:
        raise ValueError("resource digit count requires a non-negative integer")
    return Decimal(integer).adjusted() + 1


def _digits_sum(value: int | Fraction) -> int:
    """Count the decimal digits of all non-negative integers below value."""
    count = int(value)
    if count < 0 or count != value:
        raise ValueError("resource digit sum requires a non-negative integer")
    if count == 0:
        return 0
    # Start with the widest term's width, then subtract each shorter band.
    width = _digits(count - 1)
    return count * width - (int(10**width) - 10) // 9


def _power2_digits_sum(value: int | Fraction) -> int:
    """Count decimal digits of 2^k for k from zero to count minus one."""
    count = int(value)
    if count < 0 or count != value:
        raise ValueError("resource power-of-two digit sum needs a non-negative integer")
    if not count:
        return 0
    # 10^d is never a power of two. Its bit length is the first k
    # for which 2^k has more than d digits.
    width = _digits(1 << (count - 1))
    total, threshold = count, 10
    for _ in range(1, width):
        total += count - threshold.bit_length()
        threshold *= 10
    return total


def _weighted_bit_sum(value: int | Fraction) -> int:
    """Sum bl(k) for k=1..n, with weight 2^(n-k) for k."""
    count = int(value)
    if count < 0 or count != value:
        raise ValueError("resource weighted bit sum needs a non-negative integer")
    # Each bit threshold 2^d contributes one across the rest of the
    # interval. Its weight sum is geometric.
    return sum((1 << (count - (1 << d) + 1)) - 1 for d in range(count.bit_length()))


def _weighted_decimal_sum(value: int | Fraction) -> int:
    """Sum digits(k) for k=1..n, with weight 2^(n-k) for k."""
    count = int(value)
    if count < 0 or count != value:
        raise ValueError("resource weighted decimal sum needs a non-negative integer")
    if not count:
        return 0
    # Every decimal threshold 10^d contributes a geometric tail.
    return sum((1 << (count - int(10**d) + 1)) - 1 for d in range(_digits(count)))


def _isqrt(value: int | Fraction) -> int:
    """Evaluate the integer square root of a non-negative count."""
    integer = int(value)
    if integer < 0 or integer != value:
        raise ValueError("resource square root needs a non-negative integer")
    return math.isqrt(integer)


def _residuals(value: int | Fraction, *, include_constants: bool = True) -> int:
    """Count the maximum distinct subtables across the internal levels."""
    arity = int(value)
    if arity < 0 or arity != value:
        raise ValueError("resource residual count requires a non-negative integer")
    return residual_count_bound(arity, include_constants=include_constants)


def _parse_expression(
    expression: str, source_names: frozenset[str] = frozenset()
) -> ast.Expression | None:
    """Parse and validate the arithmetic notation as a Python expression."""
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
        ast.Mod,
        ast.Pow,
        ast.USub,
    )
    names = _NAMES | source_names
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return None
        if isinstance(node, ast.Name) and node.id not in names:
            return None
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS
        ):
            return None
        if isinstance(node, ast.Constant) and type(node.value) is not int:
            return None
    return tree


def _power(base: int | Fraction, exponent: int | Fraction) -> int | Fraction:
    """Evaluate an integral power without leaving rational arithmetic."""
    power = int(exponent)
    if power != exponent:
        raise ValueError("resource exponent must be an integer")
    return Fraction(base) ** power if power < 0 else base**power


class _ExactArithmetic(ast.NodeTransformer):
    """Replace operators that can return a float on integer operands."""

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.op, ast.Div):
            name = "_divide"
        elif isinstance(node.op, ast.Pow):
            name = "_power"
        else:
            return node
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id=name, ctx=ast.Load()),
                args=[node.left, node.right],
                keywords=[],
            ),
            node,
        )


def expression_formula(
    expression: str,
    source_terms: SourceTerms | None = None,
    *,
    allow_unused_terms: bool = False,
) -> Formula:
    """Return the checked arithmetic formula, rejecting unknown syntax."""
    source_names = source_terms[0] if source_terms is not None else frozenset()
    tree = _parse_expression(expression, source_names)
    if tree is None:
        raise ValueError(f"invalid resource expression: {expression}")
    code = compile(
        ast.fix_missing_locations(_ExactArithmetic().visit(tree)), "<ledger>", "eval"
    )
    # A raster program has no length; only a bound that reads L asks.
    reads_length = "L" in code.co_names
    reads_table_size = "T" in code.co_names
    used_terms = source_names.intersection(code.co_names)
    if not allow_unused_terms and source_names != used_terms:
        raise ValueError("resource expression has unused source terms")

    def formula(n: int, program: str) -> int | Fraction:
        names = {
            "n": n,
            "T": 2**n if reads_table_size else None,
            "L": len(program) if reads_length else None,
            "bl": bl,
            "bit_sum": _bit_sum,
            "digits": _digits,
            "digits_sum": _digits_sum,
            "power2_digits_sum": _power2_digits_sum,
            "weighted_bit_sum": _weighted_bit_sum,
            "weighted_decimal_sum": _weighted_decimal_sum,
            "isqrt": _isqrt,
            "residuals": _residuals,
            "residuals_without_constants": partial(_residuals, include_constants=False),
            "max": max,
            "min": min,
            "ceil": math.ceil,
            "floor": math.floor,
            "_divide": Fraction,
            "_power": _power,
        }
        if source_terms is not None and used_terms:
            terms = source_terms[1](n, program)
            if (
                not isinstance(terms, Mapping)
                or terms.keys() != source_names
                or any(
                    type(value) is not int and not isinstance(value, Fraction)
                    for value in terms.values()
                )
            ):
                raise ValueError("resource provider returned invalid source terms")
            names.update(terms)
        value = Fraction(eval(code, {"__builtins__": {}}, names))
        return value.numerator if value.denominator == 1 else value

    return formula


def source_term_names(value: object) -> frozenset[str]:
    """Validate symbolic names independently of their language provider."""
    if not isinstance(value, list) or not value:
        raise ValueError("resource source terms require names")
    if any(
        not isinstance(name, str)
        or not name.isidentifier()
        or not name.isupper()
        or name in _NAMES
        for name in value
    ) or len(set(value)) != len(value):
        raise ValueError("invalid resource source term name")
    return frozenset(value)


def arity_cases(
    value: object, source_names: frozenset[str] = frozenset()
) -> ArityCases:
    """Validate contiguous positive arities with an unbounded final case."""
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("resource cases require at least two expressions")
    cases: list[tuple[int | None, str]] = []
    used: set[str] = set()
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
        if (
            not isinstance(expression, str)
            or (tree := _parse_expression(expression, source_names)) is None
        ):
            raise ValueError("invalid resource case expression")
        used.update(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))
        cases.append((through, expression))
    if source_names - used:
        raise ValueError("resource cases have unused source terms")
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
        parts.append(f"{expression} ({scope})")
    return ", ".join(parts) + f" {unit}"


def case_formula(cases: ArityCases, source_terms: SourceTerms | None = None) -> Formula:
    """Select an expression by arity, then evaluate only that expression."""
    compiled = tuple(
        (through, expression_formula(expression, source_terms, allow_unused_terms=True))
        for through, expression in cases
    )

    def formula(n: int, program: str) -> int | Fraction:
        for through, evaluate in compiled:
            if through is None or n <= through:
                return evaluate(n, program)
        raise AssertionError("validated resource cases have a final expression")

    return formula
