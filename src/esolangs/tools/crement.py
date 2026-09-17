"""Boolean-function generator for Crement: a decision tree over shared testers.

Crement has no input instruction, so each input is embedded once as the
*data* of a jump -- ``+J 0 1`` for a one, ``+J 0 0`` for a zero -- and
the tree reads it by self-modification.  Input ``i`` owns a two-line
tester (``+J 0 b`` taken when the bit is 1, then ``+J 0 1``) whose jump
addresses a node fills in: a node is two ``+A`` writes patching the
tester's one- and zero-targets to its children, then a jump into the
tester.  ``+A t d`` stores ``d + 1``, so a child at line ``c`` is written
``c - 1``.

The program opens with a jump to the root, a jump past the end (halt),
and ``+J @ 1`` (a one-step state cycle), then ``2 n`` tester lines, then
the nodes; the zero subtree is laid first so its root is ``@+1`` and the
one subtree's root is ``@`` plus three times the zero subtree's node
count.  Constant subtrees fold to the two gadgets, so leaves cost no
lines.  The program halts for a 0 entry and diverges for a 1, running at
most ``5 n + 2`` commands over at most ``3 (2**n - 1) + 2 n + 3`` lines.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)

__all__ = ["crement", "instantiate_crement"]

#: Lines one node spends: two patches and a call.
_NODE_LINES = 3

#: The fixed opening: a jump to the root, the halt, the loop.
_HEADER_LINES = 3

#: Leaf markers a subtree folds to: the halt is line 1 and the loop line 2,
#: so as ``+A`` data (one less than the address) they are ``0`` and ``1``.
_HALT, _LOOP = 0, 1


def _set_bit(_index: int, bit: int) -> str:
    """Spell the tester's first line: a jump taken exactly when the bit is 1."""
    return f"+J 0 {bit}"


def crement(truth_table: str) -> str:
    """Build a Crement template: one run per input, its tester's first line.

    Rows split most-significant-first; a subtree whose rows agree folds to
    the shared loop or the halt.
    """
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    tester = [_HEADER_LINES + 2 * i for i in range(n)]

    def walk(lo: int, hi: int) -> int | None:
        """Emit the subtree over rows ``lo:hi``; a folded leaf is its gadget."""
        span = truth_table[lo:hi]
        if span.count(span[0]) == len(span):
            return _LOOP if span[0] == "1" else _HALT
        level = n - (hi - lo).bit_length() + 1
        at = len(lines)
        lines.extend([""] * _NODE_LINES)  # reserve the node's lines
        half = (hi - lo) // 2
        zero = walk(lo, lo + half)
        one_start = len(lines)
        one = walk(lo + half, hi)
        # The zero subtree's root is the line after this node, so as data
        # (one less than the address) it is ``@+1`` from the second line;
        # the one subtree's root is wherever the zero subtree ended.
        one_data = f"@+{one_start - 1 - at}" if one is None else str(one)
        zero_data = "@+1" if zero is None else str(zero)
        lines[at] = f"+A {tester[level]} {one_data}"
        lines[at + 1] = f"+A {tester[level] + 1} {zero_data}"
        lines[at + 2] = f"+J {tester[level]} 1"
        return None

    root = walk(0, len(truth_table))
    first = _HEADER_LINES + 2 * n
    header = [
        f"+J {first if root is None else root + 1} 1",
        f"+J {first + len(lines)} 1",
        "+J @ 1",
    ]
    testers = [
        line
        for zero, _one in crement_setters("", n)
        for line in (TEMPLATE_CHAR * len(zero), "+J 0 1")
    ]
    return "\n".join(header + testers + lines)


def instantiate_crement(template: str, bits: list[int]) -> str:
    """Fill each input's run with the jump line that spells its bit."""
    setters = crement_setters(template, len(bits))
    return fill_runs(template, TEMPLATE_CHAR, setters, bits)


def crement_setters(_template: str, n: int) -> Setters:
    """Return the tester's first line for a zero and a one, per input."""
    return ((_set_bit(0, 0), _set_bit(0, 1)),) * n
