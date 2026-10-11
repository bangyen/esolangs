"""Read a ledger cell's stated bound as a formula the tests can evaluate.

A ``worst`` or ``at most`` clause states its bound in the notation of
docs/proofs/index.md's Symbols: ``69n + 44``, ``2T + 3n - 2``,
``n^2 + 8n + 5``, ``bl(3T+6n+5)``.  When the bound uses only ``n``, ``T``
(``2^n``), ``L`` (the program's length), integers and ``bl``, ``max``,
``min``, ``⌈⌉``, ``⌊⌋``, the clause itself is the formula: the test
measures against what the ledger says, so the two cannot drift.  Anything
else (a definition such as ``M = ...``, a sum, a case split) returns None,
and the test file spells that formula by hand.
"""

from __future__ import annotations

import ast
import importlib
import math
import re
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

from esolangs.registry._slug import canonical_id

if TYPE_CHECKING:
    from tests.proofs._ledger import Row as LedgerRow

#: The words a bound ends on: its unit.
_UNITS = r"(?:commands|steps|rewrites|nodes|instructions|lines|bits)"
_BOUND = re.compile(rf"^(worst|at most) (.+?) {_UNITS}\b(.*)$")
#: ``past n = k``: the bound holds from k + 1 inputs.
_PAST = re.compile(r"^,? past n ?= ?(\d+)(?=$|[:;,])")
_NAMES = {"n", "T", "L", "bl", "max", "min", "ceil", "floor"}

Formula = Callable[[int, str], int | Fraction]


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
        if isinstance(node, ast.Constant) and type(node.value) is not int:
            return None
    return text


def parse(clause: str) -> tuple[Formula, bool, int] | None:
    """Return ``(formula(n, program), exact, first n)``, or None.

    ``exact`` is a ``worst`` bound, which some table must reach; ``at most``
    need only never be exceeded.  ``first n`` is 3, or one past ``past n``.
    """
    match = _BOUND.match(clause)
    if match is None:
        return None
    kind, expression, rest = match.groups()
    past = _PAST.match(rest)
    tail = rest[past.end() :] if past else rest
    # A colon explains the bound; a comma or semicolon may start a second
    # case ("; 2n + 2 past n = 7", ", else 15T/2 - 4"), so one with figures
    # is left to a hand-written formula.
    second = not tail.startswith((",", ";")) or re.search(r"\d|else|after", tail)
    if tail and not tail.startswith(":") and second:
        return None
    python = _python(expression)
    if python is None:
        return None
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

    return formula, kind == "worst", max(3, int(past.group(1)) + 1) if past else 3


def ledger_formulas(
    clause: Callable[[LedgerRow], str],
    hand: dict[str, tuple[Formula, bool, tuple[int, ...]]],
    arities: dict[str, tuple[int, ...]],
    *,
    column: str | None = None,
) -> dict[str, tuple[Formula, bool, tuple[int, ...]]]:
    """Return parsed bounds, handwritten fallbacks, then language-owned overrides.

    Arities run from the first n through three more for a ``poly n`` row,
    two more otherwise (each rung of a linear row costs twice the last),
    unless ``arities`` names them. ``column`` loads language-owned formulas
    from ``tests/<language id>/formulas.py`` when present.
    """
    from tests.proofs._ledger import load

    table: dict[str, tuple[Formula, bool, tuple[int, ...]]] = {}
    local: dict[str, tuple[Formula, bool, tuple[int, ...]]] = {}
    for row in load().rows:
        if column is not None:
            stem = canonical_id(row.generator)
            path = Path(__file__).resolve().parents[1] / stem / "formulas.py"
            if path.is_file():
                owner = importlib.import_module(f"tests.{stem}.formulas")
                if formula := owner.FORMULAS.get(column):
                    local[row.generator] = formula
                    continue
        parsed = parse(clause(row)) if row.generator not in hand else None
        if parsed is not None:
            formula, exact, start = parsed
            span = 3 if row.execution_class.startswith("poly") else 2
            table[row.generator] = (
                formula,
                exact,
                arities.get(row.generator, (start, start + span)),
            )
    return {**table, **hand, **local}
