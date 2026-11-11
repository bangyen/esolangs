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
pushes its bit, ``(0)`` or ``(1)``. Named AND/OR and threshold-2 tails,
their duals and complements retain unused selectors beneath the answer.

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
    SubtreeDiagram,
    _validate_truth_table,
    reflected_table,
    same_up_to_wrapping,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments
from esolangs.generation.wrap import TokenWrapper

# A zero duplicates the returned bit, giving both selectors five characters.
PAIR = ("(!^:)", "(~!^)")
_BIT_PAIR = ("!", "*")

#: How many levels below a node a carried subtree may sit; bounds the
#: candidates per node (``repeated_near``) so the build visits O(T) nodes.
_REACH = 4
#: Inert prefix that marks the narrow (``short``) layouts.
_PREFIX = "()!"


_WRAPPER = TokenWrapper(r"\(\)!|\([01]\)|.")


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

    body = tree(0, diagram.root, None).replace("\ue000", "")
    return "(" + body + ")^S"


def underload(truth_table: str, width: int | None = None) -> str:
    """Return a promise tree; narrow selectors defer execution to their node."""
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        layout = layout_fragments(
            (f"({truth_table[0]})", *(InputSlot(3),) * n, "!" * n + "S")
        )
    elif width is not None and width < 5:
        # The node runs the chosen selector; neither fill needs padding.
        selectors = ("()(~)", InputSlot(1), "(!)*") * n
        layout = layout_fragments(
            (_PREFIX, *selectors, _shared(truth_table, short=True))
        )
    else:
        layout = layout_fragments(
            (*(InputSlot(len(PAIR[0])),) * n, _shared(truth_table))
        )
    return layout if width is None else _WRAPPER.wrap_template(layout, width)


def underload_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform selector pair distinguished by its inert prefix."""
    clean = template.replace("\n", "")
    if clean.startswith(("(0)", "(1)")):
        pair = ("(0)", "(1)")
    elif clean.startswith(_PREFIX):
        pair = _BIT_PAIR
    else:
        pair = PAIR
    return (pair,) * n


def _underload_layout_tokens(template: str) -> list[str]:
    """Ignore layout LF while retaining whole output literals as atoms."""
    return re.findall(r"\${3,4}|\([01]\)|[^\n]", template)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Compare the narrow layouts token by token."""
    if plain.startswith(("(0)", "(1)")):
        return _underload_layout_tokens(template) == _underload_layout_tokens(plain)
    for width in (1, 4):
        narrow = str(layout(width))
        if _underload_layout_tokens(template) == _underload_layout_tokens(narrow):
            return True
    return same_up_to_wrapping(template, plain)


def underload_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def underload_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Balance the default selector layout at its whole-token fit."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    return _WRAPPER.fit_template(request.source, minimum=5)
