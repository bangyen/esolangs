"""Crement Boolean program generator: a decision tree over shared testers.

Crement has no input instruction, so each input is embedded once as the
*data* of a jump (:data:`PAIR`) that the tree reads by self-modification.
Input ``i`` owns a two-line tester (``+J 0 b`` taken when the bit is 1, then
``+J 0 1``) whose targets a node fills in: two ``+A`` writes patching the one-
and zero-targets to its children, then a jump into the tester.  ``+A t d``
stores ``d + 1``, so a child at line ``c`` is written ``c - 1``.  Layout: a jump
to the root, the halt, ``+J @ 1`` (a one-step cycle), ``2 n`` tester lines,
then the nodes, zero subtree first; constant subtrees fold to the two gadgets.
A child is only an address, so a subtree equal to one already emitted at its
level is named, not re-emitted, and a node with equal halves is skipped.

Size:
    At most ``5 n + 2`` executed commands over ``3 (2**n - 1) + 2 n + 3`` lines;
    n=10 parity: 659 chars, n=10 random 1847: 6,363 chars.

Decisions:
    Sharing cuts the 256 three-input tables from 39,156 to 37,862 characters
    (3.3%) and 200 seeded five-input tables from 114,791 to 83,070 (27.6%).
"""

from collections.abc import Callable, Iterator
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    grid_width,
    in_input_order,
    layout_width,
    same_tokens,
    same_up_to_wrapping,
    subtree_ids,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

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
    input order. Below six columns, whitespace separates fields and only
    tester data is filled.
    """
    template = in_input_order(truth_table, _crement_shared)
    if width is None or width <= 0 or grid_width(template) <= width:
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
        lines.append(
            f"{operator} {_short_operand(address, here)} {_short_operand(data, here)}"
        )
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
    return _crement_ordered(truth_table, perm, share=True)


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

        # A child emitted here is named relative to the patch, as ``@+k``;
        # a gadget or earlier copy takes the shorter spelling.
        def data(target: int, line: int) -> str:
            return f"@+{target - 1 - line}" if target > at else str(target - 1)

        cell = tester[level]
        rel = at - first
        lines[rel] = f"+A {cell} {data(one, at)}"
        lines[rel + 1] = f"+A {cell + 1} {data(zero, at + 1)}"
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


def _balance(table: str, default: str) -> str:
    """Compare preserved instructions and the two field-wrapping regimes."""
    candidates = [default]
    upper = grid_width(default) - 1
    if upper >= 6:
        normal = crement(table, upper)
        candidates.append(normal)
        folded_upper = min(upper, grid_width(normal) - 1)
        if folded_upper >= 6:
            width = balanced_token_width(
                normal.split(), " ", minimum=6, maximum=folded_upper
            )
            candidates.append(crement(table, width))
    short = crement(table, 1)
    width = balanced_token_width(short.split(), " ", maximum=5)
    candidates.append(crement(table, width))
    candidates.extend(_packed(default, min(map(balance_score, candidates))[0]))
    return min(candidates, key=balance_score)


def _packed(default: str, bound: int) -> Iterator[str]:
    """``default`` with k whole instructions per line, k = 2, 3, ...

    The parser groups whitespace tokens, so line breaks between instructions are
    free.  The widest row is at least the mean row, which grows with k; stop
    once it reaches ``bound``, the best side, since the side is at least that.
    """
    lines = default.split("\n")
    total = sum(map(len, lines)) + len(lines)  # each instruction plus one space
    for k in range(2, len(lines)):
        rows = -(-len(lines) // k)
        if total - rows >= bound * rows:  # mean row width >= bound
            return
        yield "\n".join(" ".join(lines[i : i + k]) for i in range(0, len(lines), k))


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Tokens on whitespace; short setters coexist with fitting layouts."""
    return (
        same_tokens(template, layout(1))
        or same_tokens(template, layout(layout_width(template)))
        or same_up_to_wrapping(template, plain)
    )


LANGUAGE = Language(
    "Crement",
    "crement",
    category="program_based",
    boolean=crement,
    same_layout=_same_layout,
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Crement answers by termination: the tree's nodes patch a "
        "per-input tester's jump targets, and the row lands past the "
        "end (halts, 0) or on a self-jump (diverges, 1)",
    ),
    balance=_balance,
    no_wrap="jumps and patches name instruction numbers, so lines stay whole",
    example=Example(setters=crement_setters, expected=""),
)
