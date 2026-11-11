"""Crement Boolean program generator: a decision tree over shared testers.

Crement has no input instruction, so each input is embedded once as the
*data* of a jump that the tree reads by self-modification.
Input ``i`` owns a two-line tester (``+J 0 b`` taken when the bit is 1, then
``+J 0 1``) whose targets a node fills in: two ``+A`` writes patching the one-
and zero-targets to its children, then a jump into the tester.  ``+A t d``
stores ``d + 1``, so a child at line ``c`` is written ``c - 1``.  Layout: a jump
to the root, the halt, ``+J @ 1`` (a one-step cycle), ``2 n`` tester lines,
then the nodes, zero subtree first; constant subtrees fold to the two gadgets.
A child is only an address, so a subtree equal to one already emitted at its
level is named, not re-emitted, and a node with equal halves is skipped.
Parity and thresholds initialize each tester to its first node at that level.
That node is the tester itself; other nodes patch only differing targets.

Size:
    At most ``5 n + 2`` executed commands over ``3 (2**n - 1) + 2 n + 3`` lines;
    n=10 parity: 398 chars, n=10 random 1847: 6,283 chars.
    Constants: n+1 instructions, one step to halt or repeat; n=8: 62 chars.

Decisions:
    Testers are visited at most once on a row, so their initial targets
    remain available. Parity/threshold children are distinct: selecting the
    first node needs no mode search. Other functions retain the patching
    construction ([ablations.trick_prototype_20261102_preset_named]).
"""

from collections.abc import Callable, Iterator
from itertools import pairwise
from math import isqrt
from typing import Any

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.decision import reduced_diagram
from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_width,
    layout_width,
    same_tokens,
    same_up_to_wrapping,
    symmetric_weights,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
    layout_tokens,
)
from esolangs.generation.wrap import balance_score

__all__ = ["crement"]

#: Lines one node spends: two patches and a call.
_NODE_LINES = 3

#: The fixed opening: a jump to the root, the halt, the loop.
_HEADER_LINES = 3

#: Leaf markers a subtree folds to: the halt is line 1 and the loop line 2,
#: so as ``+A`` data (one less than the address) they are ``0`` and ``1``.
_HALT, _LOOP = 0, 1


PAIR = ("+J 0 0", "+J 0 1")


type _Instruction = tuple[str, str, TemplateToken]
type _Line = _Instruction | InputSlot
_FULL_TESTER = InputSlot(len(PAIR[0]))
_DATA_TESTER = InputSlot(1)


def crement_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return data-only setters for field-wrapped testers."""
    return (("0", "1") if TEMPLATE_CHAR in template.split() else PAIR,) * n


def crement(truth_table: str, width: int | None = None) -> str:
    """Build a Crement template: one run per input, its tester's first line.

    Constant subtrees fold and repeated halves share code. Splits stay in
    input order. Preset testers fill only data; below six columns, other
    templates use that field form too.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    lines: list[_Line]
    if (constant := constant_output(truth_table)) is not None:
        target = 0 if constant == "1" else n + 1
        lines = [("+J", str(target), "1"), *[_FULL_TESTER] * n]
    elif _preset_family(truth_table, n):
        lines = _preset_template(truth_table, n)
    else:
        lines = _shared_template(truth_table, n)
    layout = _render_lines(lines)
    if width is None or grid_width(layout.source) <= width:
        return layout
    lines = [_short_line(line, here, width) for here, line in enumerate(lines)]
    layout = _render_lines(lines)
    if grid_width(layout.source) > width:
        return layout_tokens(
            [
                token
                for line in lines
                for token in ((line,) if isinstance(line, InputSlot) else line)
            ],
            width,
        )
    return layout


def _render_lines(lines: list[_Line]) -> TemplateLayout:
    def parts() -> Iterator[TemplateToken]:
        for i, line in enumerate(lines):
            if i:
                yield "\n"
            if isinstance(line, InputSlot):
                yield line
            else:
                operator, address, data = line
                yield f"{operator} {address} "
                yield data

    return layout_fragments(parts())


def _short_line(line: _Line, here: int, width: int) -> _Line:
    """Shorten operands and use a data-only slot when a tester cannot fit."""
    if isinstance(line, InputSlot):
        return ("+J", "0", _DATA_TESTER) if width < len(line) else line
    operator, address, data = line
    operand = _short_operand(data, here) if isinstance(data, str) else data
    return operator, _short_operand(address, here), operand


def _rel(offset: int) -> str:
    """Spell a relative operand: ``@`` or ``@+k`` / ``@-k``."""
    return "@" if not offset else f"@{offset:+d}"


def _short_operand(source: str, here: int) -> str:
    """Return the shortest absolute or relative spelling of one operand."""
    value = here + int(source[1:] or "0") if source.startswith("@") else int(source)
    offset = value - here
    return min((source, str(value), _rel(offset)), key=len)


def _preset_family(table: str, n: int) -> bool:
    """Recognize parity and thresholds over the inputs the table retains."""
    if len(essential_inputs(table, n)) == 1:
        return True
    symmetric = symmetric_weights(table, n)
    if symmetric is None:
        return False
    changes = [a != b for a, b in pairwise(symmetric.table)]
    return all(changes) or sum(changes) == 1


def _preset_template(table: str, n: int) -> list[_Line]:
    """Initialize each level's tester to its first native branch state."""
    nodes, root = reduced_diagram(table, n)
    order: dict[int, None] = {}
    defaults: dict[int, tuple[int, int]] = {}

    def visit(ref: int) -> None:
        if ref < 2 or ref in order:
            return
        node = nodes[ref]
        order[ref] = None
        visit(node.zero)
        visit(node.one)
        defaults.setdefault(node.level, (node.zero, node.one))

    visit(root)
    first = _HEADER_LINES + 2 * n
    position: dict[int, int] = {}
    end = first
    for ref in order:
        level, zero, one = nodes[ref]
        z0, o0 = defaults[level]
        if (zero, one) == (z0, o0):
            position[ref] = _HEADER_LINES + 2 * level
        else:
            position[ref] = end
            end += 1 + (zero != z0) + (one != o0)

    def address(ref: int) -> int:
        return (_LOOP + 1 if ref else _HALT + 1) if ref < 2 else position[ref]

    body: list[_Line] = []
    for ref in order:
        level, zero, one = nodes[ref]
        z0, o0 = defaults[level]
        if (zero, one) == (z0, o0):
            continue
        cell = _HEADER_LINES + 2 * level
        if one != o0:
            body.append(("+A", str(cell), str(address(one) - 1)))
        if zero != z0:
            body.append(("+A", str(cell + 1), str(address(zero) - 1)))
        body.append(("+J", str(cell), "1"))
    testers: list[_Line] = []
    for name in range(n):
        state = defaults.get(name)
        zero, one = (address(state[0]), address(state[1])) if state else (0, 0)
        testers.extend((("+J", str(one), _DATA_TESTER), ("+J", str(zero), "1")))
    return [
        ("+J", str(address(root)), "1"),
        ("+J", str(end), "1"),
        ("+J", "@", "1"),
        *testers,
        *body,
    ]


def _shared_template(table: str, n: int) -> list[_Line]:
    """Emit each reduced node once, with native child patches and calls."""
    nodes, root = reduced_diagram(table, n)
    first = _HEADER_LINES + 2 * n
    lines: list[_Instruction] = []
    placed: dict[int, int] = {}

    def emit(ref: int) -> int:
        if ref < 2:
            return _LOOP + 1 if ref else _HALT + 1
        if ref in placed:
            return placed[ref]
        level, zero, one = nodes[ref]
        at = placed[ref] = first + len(lines)
        lines.extend([("", "", "")] * _NODE_LINES)
        zero, one = emit(zero), emit(one)
        cell = _HEADER_LINES + 2 * level
        lines[at - first : at - first + 3] = [
            ("+A", str(cell), str(one - 1)),
            ("+A", str(cell + 1), str(zero - 1)),
            ("+J", str(cell), "1"),
        ]
        return at

    start = emit(root)
    testers: list[_Line] = [_FULL_TESTER, ("+J", "0", "1")]
    return [
        ("+J", str(start), "1"),
        ("+J", str(first + len(lines)), "1"),
        ("+J", "@", "1"),
        *(testers * n),
        *lines,
    ]


def _balance(_table: str, default: str) -> str:
    """Compare ``default`` with k whole instructions per line."""
    return min([default, *_packed(default)], key=balance_score)


def _packed(default: str) -> Iterator[str]:
    """``default`` with k whole instructions per line, k near the square root.

    The parser groups whitespace tokens, so line breaks between instructions are
    free.  With L lines and ``total`` characters the best k tracks
    isqrt(2*L*L // total) within 1 (measured on n=1..8).
    """
    lines = default.split("\n")
    total = sum(map(len, lines)) + len(lines)  # each instruction plus one space
    k0 = isqrt(2 * len(lines) ** 2 // total)
    for k in range(max(2, k0 - 1), min(k0 + 2, len(lines))):
        yield "\n".join(" ".join(lines[i : i + k]) for i in range(0, len(lines), k))


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Tokens on whitespace; short setters coexist with fitting layouts."""
    return (
        same_tokens(template, layout(1))
        or same_tokens(template, layout(layout_width(template)))
        or same_up_to_wrapping(template, plain)
    )


def crement_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def crement_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Pack instructions without moving their source offsets."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("Crement balancing needs a rendered template with slots")
    return TemplateLayout(
        _balance(request.table, request.source.source), request.source.spans
    )
