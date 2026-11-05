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

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    in_input_order,
    layout_width,
    same_tokens,
    same_up_to_wrapping,
    subtree_ids,
    symmetric_weights,
)
from esolangs.generation.wrap import balance_score, wrap_space_delimited

__all__ = ["crement"]

#: Lines one node spends: two patches and a call.
_NODE_LINES = 3

#: The fixed opening: a jump to the root, the halt, the loop.
_HEADER_LINES = 3

#: Leaf markers a subtree folds to: the halt is line 1 and the loop line 2,
#: so as ``+A`` data (one less than the address) they are ``0`` and ``1``.
_HALT, _LOOP = 0, 1


PAIR = ("+J 0 0", "+J 0 1")


def crement_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return data-only setters for field-wrapped testers."""
    return (("0", "1") if TEMPLATE_CHAR in template.split() else PAIR,) * n


def crement(truth_table: str, width: int | None = None) -> str:
    """Build a Crement template: one run per input, its tester's first line.

    Constant subtrees fold and repeated halves share code. Splits stay in
    input order. Preset testers fill only data; below six columns, other
    templates use that field form too.
    """
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        target = 0 if truth_table[0] == "1" else n + 1
        template = "\n".join([f"+J {target} 1", *[TEMPLATE_CHAR * len(PAIR[0])] * n])
    else:
        template = in_input_order(truth_table, _crement_shared)
    if width is None or grid_width(template) <= width:
        return template
    return _narrow(template, width)


def _narrow(template: str, width: int) -> str:
    """Respell over-wide instructions with their shortest operands, then wrap."""
    lines = []
    for here, line in enumerate(template.splitlines()):
        if line.startswith(TEMPLATE_CHAR):
            lines.append(line)
            continue
        operator, address, data = line.split()
        operand = data if data == TEMPLATE_CHAR else _short_operand(data, here)
        lines.append(f"{operator} {_short_operand(address, here)} {operand}")
    narrowed = "\n".join(lines)
    if width < 6:
        narrowed = narrowed.replace(
            TEMPLATE_CHAR * len(PAIR[0]), f"+J 0 {TEMPLATE_CHAR}"
        )
    if grid_width(narrowed) > width:
        return wrap_space_delimited(narrowed, width)
    return narrowed


def _rel(offset: int) -> str:
    """Spell a relative operand: ``@`` or ``@+k`` / ``@-k``."""
    return "@" if not offset else f"@{offset:+d}"


def _short_operand(source: str, here: int) -> str:
    """Return the shortest absolute or relative spelling of one operand."""
    value = here + int(source[1:] or "0") if source.startswith("@") else int(source)
    offset = value - here
    return min((source, str(value), _rel(offset)), key=len)


def _crement_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Return one order's shared template."""
    if _preset_family(truth_table, len(perm)):
        return _preset_template(truth_table, perm)
    return _crement_ordered(truth_table, perm, share=True)


type _Ref = int | tuple[int, int]


def _preset_family(table: str, n: int) -> bool:
    """Recognize parity and thresholds over the inputs the table retains."""
    if len(essential_inputs(table, n)) == 1:
        return True
    symmetric = symmetric_weights(table, n)
    if symmetric is None:
        return False
    changes = [a != b for a, b in pairwise(symmetric.table)]
    return all(changes) or sum(changes) == 1


def _preset_template(table: str, perm: tuple[int, ...]) -> str:
    """Reuse each level's first tester state; parent references bypass its call."""
    n = len(perm)
    ids = subtree_ids(table)
    nodes: dict[tuple[int, int], tuple[_Ref, _Ref]] = {}
    order: list[tuple[int, int]] = []
    defaults: dict[int, tuple[_Ref, _Ref]] = {}

    def visit(level: int, block: int) -> _Ref:
        node = ids[level][block]
        if node < 2:
            return node
        if ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]:
            return visit(level + 1, 2 * block)
        key = (level, node)
        if key not in nodes:
            order.append(key)
            children = (visit(level + 1, 2 * block), visit(level + 1, 2 * block + 1))
            nodes[key] = children
            defaults.setdefault(level, children)
        return key

    root = visit(0, 0)
    first = _HEADER_LINES + 2 * n
    position: dict[tuple[int, int], int] = {}
    end = first
    for key in order:
        zero, one = nodes[key]
        z0, o0 = defaults[key[0]]
        if (zero, one) == (z0, o0):
            position[key] = _HEADER_LINES + 2 * perm[key[0]]
        else:
            position[key] = end
            end += 1 + (zero != z0) + (one != o0)

    def address(ref: _Ref) -> int:
        if isinstance(ref, int):
            return _LOOP + 1 if ref else _HALT + 1
        return position[ref]

    body = []
    for key in order:
        zero, one = nodes[key]
        z0, o0 = defaults[key[0]]
        if (zero, one) == (z0, o0):
            continue
        cell = _HEADER_LINES + 2 * perm[key[0]]
        if one != o0:
            body.append(f"+A {cell} {address(one) - 1}")
        if zero != z0:
            body.append(f"+A {cell + 1} {address(zero) - 1}")
        body.append(f"+J {cell} 1")
    testers = []
    for name in range(n):
        state = defaults.get(perm.index(name))
        zero, one = (address(state[0]), address(state[1])) if state else (0, 0)
        testers.extend([f"+J {one} {TEMPLATE_CHAR}", f"+J {zero} 1"])
    return "\n".join(
        [f"+J {address(root)} 1", f"+J {end} 1", "+J @ 1", *testers, *body]
    )


def _crement_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> str:
    """Emit one split order's template; level ``k`` calls input ``perm[k]``'s tester.

    The runs, and so the testers, stay in name order.  With ``share`` a
    parent may name a copy emitted for another: sound, since a node patches
    its tester's two targets itself on every entry.
    """
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    tester = [_HEADER_LINES + 2 * perm[level] for level in range(n)]
    first = _HEADER_LINES + 2 * n
    ids = subtree_ids(truth_table)  # O(2**n), so a node's lookup is O(1)
    placed: dict[tuple[int, int], int] = {}

    def walk(level: int, block: int) -> int:
        """Emit the subtree at ``block`` of ``level``; return its first line."""
        key = ids[level][block]
        if key < 2:
            return _LOOP + 1 if key else _HALT + 1
        if (level, key) in placed:
            return placed[level, key]
        # Equal halves need no test: the parent names the child directly.
        if share and ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]:
            return walk(level + 1, 2 * block)
        at = first + len(lines)
        if share:
            placed[level, key] = at
        lines.extend([""] * _NODE_LINES)  # reserve the node's lines
        zero = walk(level + 1, 2 * block)
        one = walk(level + 1, 2 * block + 1)

        # A child is named by its absolute line, one less as ``+A`` data.
        cell = tester[level]
        rel = at - first
        lines[rel] = f"+A {cell} {one - 1}"
        lines[rel + 1] = f"+A {cell + 1} {zero - 1}"
        lines[rel + 2] = f"+J {cell} 1"
        return at

    root = walk(0, 0)
    header = [
        f"+J {root} 1",
        f"+J {first + len(lines)} 1",
        "+J @ 1",
    ]
    testers = [TEMPLATE_CHAR * len(PAIR[0]), "+J 0 1"] * n
    return "\n".join(header + testers + lines)


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
