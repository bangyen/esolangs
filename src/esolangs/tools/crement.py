"""Boolean-function generator for Crement: a decision tree over shared testers.

Crement has no input instruction, so each input is embedded once as the
*data* of a jump -- ``+J 0 1`` for a one, ``+J 0 0`` for a zero, the same
width either way -- and the tree reads it through Crement's only means of
indirection, self-modification.  Input ``i`` owns a two-line tester::

    T_i:    +J 0 {Xi}      * taken when the bit is 1
    T_i+1:  +J 0 1         * taken otherwise

whose two jump addresses are ``0`` until a node fills them in.  A node of
the tree that splits on input ``i`` is three lines: two ``+A`` writes that
patch the tester's one- and zero-targets to the node's children, then a
jump into the tester.  ``+A t d`` stores ``d + 1`` in the address field of
line ``t``, so a child at line ``c`` is written as ``c - 1``.

The program opens with three fixed lines -- a jump to the root, a jump past
the end (the halt), and ``+J @ 1`` (a one-step state cycle: it writes
nothing, so the snapshot repeats at once) -- then the ``2 n`` tester lines,
then the nodes.  A child is therefore either the halt (``0``), the loop
(``1``) or a node written relative to the patch itself: the zero subtree is
laid down first, so its root is always ``@+1``, and the one subtree's root
is ``@`` plus three times the zero subtree's node count.  Constant subtrees
fold to the two gadgets directly, so a table's leaves cost no lines, and
every operand but the halt's own is small, which keeps the size within a
constant of the node count.  The instantiated program halts for a 0 entry
and diverges for a 1 entry: one node per level, so it runs at most
``5 n + 2`` commands, and it is ``3`` lines per node, at most
``3 (2**n - 1) + 2 n + 3`` lines in all.
"""

from esolangs.tools.helpers import (
    Setters,
    _validate_truth_table,
    instantiate,
    slot_count,
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
    """Build a Crement template with one ``{Xi}`` tester line per input.

    The program is a decision tree whose nodes route through per-input
    testers by patching their jump targets (see the module docstring).
    Rows split most-significant-first, so the root tests input 0, and a
    subtree whose rows agree folds to the shared loop or to the halt.
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
    testers = [line for i in range(n) for line in (f"{{X{i}}}", "+J 0 1")]
    return "\n".join(header + testers + lines)


def instantiate_crement(template: str, bits: list[int]) -> str:
    """Fill each ``{Xi}`` with the jump line that spells its bit."""
    return instantiate(template, bits, crement_setters(template))


def crement_setters(template: str) -> Setters:
    """Return the tester's first line for a zero and a one, per input."""
    return ((_set_bit(0, 0), _set_bit(0, 1)),) * slot_count(template)
