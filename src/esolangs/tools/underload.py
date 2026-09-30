"""Underload boolean generator: equal-width selectors force a promise tree.

A node ``(A)~(B)~^`` tucks its halves under the input block on top, and the
input's ``^`` keeps one and runs it.  A repeated subtree ``X`` is pushed once
as ``(X)`` at a node above its copies and *carried*: kept on top, with the
next input block right below it.  A carrying node opens with ``~`` to put
that input back on top, and its selector leaves ``X`` on top again for the
half it runs, so only one half ever needs it and nothing is duplicated.  A
copy of ``X`` is then ``^``, and a half without one drops it with ``!``.
"""

import re
from functools import cache

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    SubtreeDiagram,
    _validate_truth_table,
)
from esolangs.tools.wrap import wrap_tokens

# Zero drops the upper promise; one swaps before dropping.  Pad zero
# outside its pushed code so both setters occupy five characters.
PAIR = ("(!^) ", "(~!^)")
_SHORT_PAIR = ("(!) ", "(~!)")
_BIT_PAIR = (" ", "~")

#: How many levels below a node a carried subtree may sit: 2**4 candidates a
#: node keeps the build O(T).
_REACH = 4
#: ``(A)~(B)~^`` less its halves.
_NODE = 7


def _reflected(truth_table: str, n: int) -> str:
    """Reorder rows so the tree's first test is the last-pushed input."""
    return "".join(truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(1 << n))


def _shared(truth_table: str, *, short: bool = False) -> str:
    """Return the tree over the reduced diagram, carrying repeated subtrees.

    Subtrees are named by :class:`~esolangs.tools.helpers.SubtreeDiagram`.  A
    node whose halves agree is ``!`` and the half, a leaf pushes its bit and
    one ``S`` after the tree prints it, and each node carries the one
    subtree within :data:`_REACH` levels that shortens it most, if any does.
    """
    n = _validate_truth_table(truth_table)
    diagram = SubtreeDiagram(_reflected(truth_table, n))
    halves, level_of, reaches = diagram.halves, diagram.level, diagram.reaches

    @cache
    def size(level: int, key: int, carry: int | None) -> int:
        if carry is not None and key == carry:
            return 1
        if carry is not None and not reaches(key, carry):
            return 1 + size(level, key, None)
        if key < 2:
            return n - level + 3
        if carry is None:
            return choice(level, key)[0]
        return node(level, key, carry)

    def node(level: int, key: int, carry: int | None) -> int:
        zero, one = halves[key]
        opening = carry is not None
        if zero == one:
            return 1 + opening + size(level + 1, zero, carry)
        halves_size = size(level + 1, zero, carry) + size(level + 1, one, carry)
        return opening + _NODE + short + halves_size

    @cache
    def choice(level: int, key: int) -> tuple[int, int | None]:
        best: tuple[int, int | None] = (node(level, key, None), None)
        for name in diagram.repeated_near(key, _REACH):
            pushed = size(level_of[name], name, None) + 2
            carried = pushed + size(level, key, name)
            if carried < best[0]:
                best = (carried, name)
        return best

    pieces: list[str] = []

    def write(level: int, key: int, carry: int | None) -> None:
        if carry is not None and key == carry:
            pieces.append("^")
            return
        if carry is not None and not reaches(key, carry):
            pieces.append("!")
            carry = None
        if key < 2:
            pieces.append("!" * (n - level) + f"({key})")
            return
        if carry is None and (carry := choice(level, key)[1]) is not None:
            pieces.append("(")
            write(level_of[carry], carry, None)
            pieces.append(")")
        zero, one = halves[key]
        if carry is not None:
            pieces.append("~")
        if zero == one:
            pieces.append("!")
            write(level + 1, zero, carry)
            return
        pieces.append("(")
        write(level + 1, zero, carry)
        pieces.append(")~(")
        write(level + 1, one, carry)
        pieces.append(")~^^" if short else ")~^")

    write(0, diagram.ids[0][0], None)
    slots = TEMPLATE_CHAR * (len((_SHORT_PAIR if short else PAIR)[0]) * n)
    return slots + "(" + "".join(pieces) + ")^S"


def underload(truth_table: str, width: int | None = None) -> str:
    """Return a promise tree; narrow selectors defer execution to their node."""
    short = width is not None and 0 < width < 5
    program = _shared(truth_table, short=short)
    if width is None or width <= 0:
        return program
    # Only bit literals reach S; every other pushed string is executable code.
    if short:
        # The inert prefix distinguishes the four-character uniform setters.
        program = "()!" + program
    if short and width < 4:
        n = _validate_truth_table(truth_table)
        # Build both selector strings, then keep one with a single swap bit.
        program = "()!" + "(!)(~)(!)*$!" * n + program[3 + 4 * n :]
    slots = 1 if short and width < 4 else (4 if short else 5)
    return wrap_tokens(program, width, rf"\${{{slots}}}|\(\)!|\([01]\)|.")


def underload_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform selector pair distinguished by its inert prefix."""
    clean = template.replace("\n", "")
    pair = (
        _BIT_PAIR
        if clean.startswith("()!(!)")
        else (_SHORT_PAIR if template.startswith("()!") else PAIR)
    )
    return (pair,) * n


def _underload_layout_tokens(template: str) -> list[str]:
    """Ignore layout LF while retaining whole output literals as atoms."""
    return re.findall(r"\${4}|\([01]\)|[^\n]", template)
