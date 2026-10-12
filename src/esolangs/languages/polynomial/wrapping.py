"""Polynomial source wrapping and balancing."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from math import isqrt
from typing import Any

from esolangs.generation.wrap import balance_score


def _polynomial(program: str, width: int) -> str:
    """Lay a Polynomial program out one signed term to a line.

    The space wrapper stranded every sign alone between wide terms.  One
    term to a line, not packed, so the exponents read as a column; the term
    itself folds too (a coefficient is 5950 digits on the dense eight-input
    table).  Folding inside a number is safe: ``_parse_program`` deletes
    every non-digit non-operator character before parsing, and ``sanitize``
    sizes its digit cap from the cleaned text (checked on that table).
    """
    return "\n".join(_folded_term(term, width) for term in _polynomial_terms(program))


def _polynomial_terms(program: str) -> list[str]:
    """Return signed terms, retaining the leading function declaration."""
    terms: list[str] = []
    pending = ""
    for token in program.split():
        if token in ("+", "-"):
            # A held sign with no term becomes its own line; ``format_coeffs``
            # never emits two in a row, so this only keeps the helper total.
            if pending:
                terms.append(pending)
            pending = token
        elif pending:
            terms.append(f"{pending} {token}")
            pending = ""
        else:
            terms.append(token)
    if pending:
        terms.append(pending)
    # ``f(x)``, ``=`` and the leading term are three tokens of one line.
    if len(terms) >= 3 and terms[0] == "f(x)" and terms[1] == "=":
        terms[:3] = [" ".join(terms[:3])]
    return terms


def _balance_polynomial(program: str) -> str:
    """Balance term folds at their integer-division transitions."""
    terms = _polynomial_terms(program)
    if not terms:
        return program
    lengths = list(map(len, terms))
    total = sum(lengths)
    widest = max(lengths)
    events = {1: 0, widest + 1: 0}
    for length in lengths:
        remainder = length - 1
        # ceil(length/w) = 1+floor(remainder/w). Its distinct quotient
        # endpoints are divisor pairs through sqrt(remainder).
        for divisor in range(1, isqrt(remainder) + 1):
            for boundary in {divisor + 1, remainder // divisor + 1}:
                change = remainder // boundary - remainder // (boundary - 1)
                events[boundary] = events.get(boundary, 0) + change
    height = total
    choices: list[tuple[tuple[int, int, int], int]] = []
    for lower, stop in pairwise(sorted(events)):
        height += events[lower]
        width = min(stop - 1, max(lower, height))
        choices.append(((abs(width - height), total + height - 1, width), width))
    _, width = min(choices)
    return min(program, _polynomial(program, width), key=balance_score)


def _folded_term(term: str, width: int) -> str:
    """Break one Polynomial term across rows of at most ``width``.

    Not indented: that would be invented whitespace, and the suite's
    invariant is that deleting what the wrapper inserted gives the program back.
    """
    rows = [term[i : i + width] for i in range(0, len(term), max(1, width))]
    return "\n".join(rows)


def same_layout(template: str, plain: str, _layout: Callable[[int], Any]) -> bool:
    """Whether the command text agrees after discarding whitespace."""
    return "".join(template.split()) == "".join(plain.split())
