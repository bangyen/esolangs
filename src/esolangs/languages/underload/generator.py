"""Underload Boolean program generator: each input picks a half of a promise tree.

The template opens with one five-character slot per input, filled with a
selector: ``(!^:)`` for 0 or ``(~!^)`` for 1.  The rest pushes the
decision tree as one string, runs it with ``^``, and ``S`` prints the bit
it leaves.  ``0110`` (exclusive or) on inputs 1, 0 runs as

    (~!^)(!^:)((((0))~((1))~^)~(((1))~((0))~^)~^)^S

and prints 1.  A node ``(A)~(B)~^`` tucks its halves under the input block
on top, and the input's ``^`` keeps one and runs it: 0 drops ``B``, runs
``A`` and duplicates its answer; 1 swaps first.
Both selectors have one width and the template one shape per table.  A leaf
pushes its bit, ``(0)`` or ``(1)``. Named AND/OR and threshold-2 tails
leave unused selectors below the answer instead of dropping them.

A repeated subtree ``X`` is pushed once as ``(X)`` at a node above its copies
and *carried*: kept on top, with the next input block right below it.  A
carrying node opens with ``~`` to put that input back on top, and its selector
leaves ``X`` on top again for the half it runs, so only one half ever needs it
and nothing is duplicated. A copy of ``X`` is ``^``; other halves drop it,
except the named terminal tails that retain it beneath the answer.

Size:
    Carries are priced before terminal drops are erased; halves are copied
    into enclosing nodes, O(T * n) construction work. n=10 parity: 3,675
    chars, n=10 and: 157 chars, n=10 random 1847: 6,118 chars.
    Constants push/drop each literal input: 4n+4 chars, 2n+2 commands;
    written workspace 8(n+1)+bl(4n+4) bits.

Decisions:
    A cost model plus writer was no faster than building text to n=18.
"""

import re
from collections.abc import Callable
from functools import cache
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    SubtreeDiagram,
    _validate_truth_table,
    reflected_table,
    same_up_to_wrapping,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import wrap_tokens
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

# A zero duplicates the returned bit, giving both selectors five characters.
PAIR = ("(!^:)", "(~!^)")
_SHORT_PAIR = ("(!) ", "(~!)")
_BIT_PAIR = (" ", "~")

#: How many levels below a node a carried subtree may sit; bounds the
#: candidates per node (``repeated_near``) so the build visits O(T) nodes.
_REACH = 4
#: Inert prefix that marks the narrow (``short``) layouts.
_PREFIX = "()!"


def _token_pattern(slots: int) -> str:
    """Return the wrap pattern: ``slots`` slot run, inert prefix, literal, char."""
    return rf"\${{{slots}}}|\(\)!|\([01]\)|."


def _terminal_family(table: str, n: int) -> bool:
    """Recognize AND/OR, threshold-2, their duals and output complements."""
    ones = table.count("1")
    minority = min(ones, len(table) - ones)
    if minority == 1:
        return table.find("1" if ones == 1 else "0") in (0, len(table) - 1)
    if minority != n + 1:
        return False
    bit = "1" if ones <= len(table) // 2 else "0"
    positions = [i for i, value in enumerate(table) if value == bit]
    return all(i.bit_count() <= 1 for i in positions) or all(
        i.bit_count() >= n - 1 for i in positions
    )


def _shared(truth_table: str, *, short: bool = False) -> str:
    """Return the tree over the reduced diagram, carrying repeated subtrees.

    Subtrees are named by :class:`~esolangs.generation.helpers.SubtreeDiagram`.  A
    node whose halves agree is ``!`` and the half, a leaf pushes its bit and
    one ``S`` after the tree prints it, and each node carries the one
    subtree within :data:`_REACH` levels with the lowest pre-cleanup price.
    """
    n = _validate_truth_table(truth_table)
    # Bill elided drops while pricing carries, preserving the original tree.
    # The coupled runs bound peak stack growth by one answer byte.
    drop = "\ue000" if _terminal_family(truth_table, n) else "!"
    diagram = SubtreeDiagram(reflected_table(truth_table, n))
    halves, level_of, reaches = diagram.halves, diagram.level, diagram.reaches

    # Candidates are priced before terminal drops are erased. A half is
    # copied into every enclosing node: O(T * n) characters, no slower than
    # a cost model plus writer to n=18.
    @cache
    def tree(level: int, key: int, carry: int | None) -> str:
        if carry is not None and key == carry:
            return "^"
        if carry is not None and not reaches(key, carry):
            return (drop if key < 2 else "!") + tree(level, key, None)
        if key < 2:
            return drop * (n - level) + f"({key})"
        if carry is None:
            return min((node(level, key, None), *carried(level, key)), key=len)
        return node(level, key, carry)

    def node(level: int, key: int, carry: int | None) -> str:
        zero, one = halves[key]
        opening = "" if carry is None else "~"
        if zero == one:
            return opening + (drop if zero < 2 else "!") + tree(level + 1, zero, carry)
        closing = ")~^^" if short else ")~^"
        zero_text, one_text = tree(level + 1, zero, carry), tree(level + 1, one, carry)
        return opening + "(" + zero_text + ")~(" + one_text + closing

    @cache
    def carried(level: int, key: int) -> list[str]:
        """Return the shortest ``(X)`` push and carry over the ``X`` worth it."""
        candidates = (
            "(" + tree(level_of[name], name, None) + ")" + tree(level, key, name)
            for name in diagram.repeated_near(key, _REACH)
        )
        # Race kept: it saves 47-60% on majority (n=8,10), 41-49% on
        # threshold-3, 11% on random tables.
        return sorted(candidates, key=len)[:1]  # stable: the first shortest

    body = tree(0, diagram.ids[0][0], None).replace("\ue000", "")
    slots = TEMPLATE_CHAR * (len((_SHORT_PAIR if short else PAIR)[0]) * n)
    return slots + "(" + body + ")^S"


def underload(truth_table: str, width: int | None = None) -> str:
    """Return a promise tree; narrow selectors defer execution to their node."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        program = f"({truth_table[0]})" + TEMPLATE_CHAR * (3 * n) + "!" * n + "S"
        return (
            program if width is None else wrap_tokens(program, width, _token_pattern(3))
        )
    short = width is not None and width < 5
    program = _shared(truth_table, short=short)
    if width is None:
        return program
    # Only bit literals reach S; every other pushed string is executable code.
    if not short:
        return wrap_tokens(program, width, _token_pattern(len(PAIR[0])))
    # The inert prefix distinguishes the four-character uniform setters.
    program = _PREFIX + program
    if width < 4:
        n = _validate_truth_table(truth_table)
        # Build both selector strings, then keep one with a single swap bit.
        program = _PREFIX + "(!)(~)(!)*$!" * n + program[len(_PREFIX) + 4 * n :]
    return wrap_tokens(program, width, _token_pattern(1 if width < 4 else 4))


def underload_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform selector pair distinguished by its inert prefix."""
    clean = template.replace("\n", "")
    if clean.startswith(("(0)", "(1)")):
        pair = ("(0)", "(1)")
    elif clean.startswith(_PREFIX + "(!)"):
        pair = _BIT_PAIR
    elif template.startswith(_PREFIX):
        pair = _SHORT_PAIR
    else:
        pair = PAIR
    return (pair,) * n


def _underload_layout_tokens(template: str) -> list[str]:
    """Ignore layout LF while retaining whole output literals as atoms."""
    return re.findall(r"\${3,4}|\([01]\)|[^\n]", template)


def _balance(table: str, default: str) -> str:
    """Balance the selectors at their token fit; the default never won."""
    slots = 3 if len(set(table)) == 1 else len(PAIR[0])
    normal = re.findall(_token_pattern(slots), default)
    return underload(table, balanced_token_width(normal, minimum=5))


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Compare the narrow layouts token by token."""
    if plain.startswith(("(0)", "(1)")):
        return _underload_layout_tokens(template) == _underload_layout_tokens(plain)
    for width in (1, 4):
        narrow = str(layout(width))
        if _underload_layout_tokens(template) == _underload_layout_tokens(narrow):
            return True
    return same_up_to_wrapping(template, plain)


LANGUAGE = Language(
    "Underload",
    "underload",
    category="stack_based",
    boolean=underload,
    same_layout=_same_layout,
    contract=BooleanContract(),
    balance=_balance,
    no_wrap="a break inside a pushed element changes the string it contains",
    example=Example(setters=underload_setters),
)
