"""Boolean-function generator for Crement: a decision tree over shared testers.

Crement has no input instruction, so each input is embedded once as the
*data* of a jump (:data:`PAIR`) that the tree reads by self-modification.
Input ``i`` owns a two-line tester (``+J 0 b`` taken when the bit is 1,
then ``+J 0 1``) whose targets a node fills in: two ``+A`` writes patching
the one- and zero-targets to its children, then a jump into the tester.
``+A t d`` stores ``d + 1``, so a child at line ``c`` is written ``c - 1``.

Layout: a jump to the root, the halt, ``+J @ 1`` (a one-step cycle), then
``2 n`` tester lines, then the nodes, zero subtree first so its root is
``@+1``; constant subtrees fold to the two gadgets.  Halts for a 0 entry,
diverges for a 1: at most ``5 n + 2`` commands over ``3 (2**n - 1) + 2 n + 3``
lines.

Since a child is only an address, a subtree equal to one already emitted at
its level is not emitted again: the patch names the earlier copy, and a node
whose halves are equal is skipped for its child.  Over the 256 three-input
tables that is 39,156 to 37,278 characters (4.8%); over 200 seeded
five-input tables, 114,791 to 83,070 (27.6%).
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    subtree_ids,
)

__all__ = ["crement"]

#: Lines one node spends: two patches and a call.
_NODE_LINES = 3

#: The fixed opening: a jump to the root, the halt, the loop.
_HEADER_LINES = 3

#: Leaf markers a subtree folds to: the halt is line 1 and the loop line 2,
#: so as ``+A`` data (one less than the address) they are ``0`` and ``1``.
_HALT, _LOOP = 0, 1


PAIR = ("+J 0 0", "+J 0 1")


def crement(truth_table: str, width: int | None = None) -> str:
    """Build a Crement template: one run per input, its tester's first line.

    Constant subtrees fold, so the tree splits in the shorter of the identity
    and greedy orders as emitted; the identity wins ties.  Each order is
    built plain and shared (:func:`_crement_ordered`), and the shorter wins.
    Over-wide instructions use their shortest absolute or relative operands;
    the width floor is one complete three-field instruction.
    """
    template = best_input_order(truth_table, _crement_best)
    if width is None or width <= 0 or max(map(len, template.splitlines())) <= width:
        return template
    lines = []
    for here, line in enumerate(template.splitlines()):
        if line.startswith(TEMPLATE_CHAR):
            lines.append(line)
            continue
        operator, address, data = line.split()
        lines.append(
            f"{operator} {_short_operand(address, here)} {_short_operand(data, here)}"
        )
    return "\n".join(lines)


def _short_operand(source: str, here: int) -> str:
    """Return the shortest absolute or relative spelling of one operand."""
    value = here + int(source[1:] or "0") if source.startswith("@") else int(source)
    offset = value - here
    relative = "@" if not offset else f"@{offset:+d}"
    return min((source, str(value), relative), key=len)


def _crement_best(truth_table: str, perm: tuple[int, ...]) -> str:
    """Return the shorter of one order's plain and shared templates."""
    plain = _crement_ordered(truth_table, perm)
    shared = _crement_ordered(truth_table, perm, share=True)
    return shared if len(shared) < len(plain) else plain


def _data(target: int, line: int) -> str:
    """Spell ``+A`` data at ``line`` naming ``target``: absolute or ``@-k``."""
    offset = target - 1 - line
    relative = "@" if not offset else f"@{offset:+d}"
    absolute = str(target - 1)
    return relative if len(relative) < len(absolute) else absolute


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
            return f"@+{target - 1 - line}" if target > at else _data(target, line)

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
    testers = [
        line
        for zero, _one in (PAIR,) * n
        for line in (TEMPLATE_CHAR * len(zero), "+J 0 1")
    ]
    return "\n".join(header + testers + lines)
