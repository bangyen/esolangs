"""Build a Line program computing a given boolean truth table directly.

No brainfuck intermediate: Line's ``i`` reads a whole number and ``o``
prints one, so 0/1 is exactly what ``IO`` hands over and no ASCII offset
enters.  The program reads each input into its own cell, then walks a ``?``
tree that tests only the inputs its subtree depends on: a level whose
halves agree is skipped, so a constant is one leaf and an ignored input
is read but never tested.  A leaf prints the cell it just tested, after
one ``+`` or ``-`` when the entry differs from that bit; a constant has no
test and prints the unread cell ``n``.  ``truth_table`` is a binary string of
length ``2**n``, MSB first.  Arms are sized from measured subtree extent
(``render.py``), so n=4 parity renders at 1880x2060 rather than the old
~17000x9000; the round trip is correct for every combination through
n=10 (16800x14880, 23.7s extract, ~29s simulate, measured before the
tree was pruned), which
``tests/line/test_line_boolean.py`` exercises to n=8.  Nothing is
enforced; n=11 upward is untested.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table

from .render import Node, chain


def line_boolean(truth_table: str) -> Node:
    """Build a Line program computing ``truth_table`` (see module docstring).

    Returns a :class:`render.Node` graph for :func:`render.render`; Line has no text.
    """
    n = _validate_truth_table(truth_table)

    # Read n inputs into cells 0..n-1, one `i` per cell, `>` between them.
    head = Node("i")
    tail = head
    for _ in range(n - 1):
        move = Node(">")
        tail.next = move
        read = Node("i")
        move.next = read
        tail = read

    def moved(pointer: int, cell: int, rest: Node) -> Node:
        """Prefix ``rest`` with the moves from ``pointer`` to ``cell``."""
        step = ">" if cell > pointer else "<"
        for _ in range(abs(cell - pointer)):
            rest = Node(step, next=rest)
        return rest

    def fork(lo: int, depth: int, pointer: int, known: int | None) -> Node:
        # Skip every level whose halves agree: that input cannot change
        # this subtree's answer, so it is read but never tested.
        size = 2 ** (n - depth)
        while (
            depth < n
            and truth_table[lo : lo + size // 2]
            == truth_table[lo + size // 2 : lo + size]
        ):
            depth += 1
            size //= 2
        if depth == n:
            value = int(truth_table[lo])
            if known is None:
                # Only a constant gets here untested: cell n is never read,
                # so it is zero, and the entry is built there.
                return moved(pointer, n, chain(*(["+"] * value), "o"))
            # A leaf straight under a test sits on the input it just tested
            # and knows its bit; nothing tests that cell again.
            step = {1: ["+"], 0: [], -1: ["-"]}[value - known]
            return chain(*step, "o")
        node = Node("?")
        node.zero = fork(lo, depth + 1, depth, 0)
        node.nonzero = fork(lo + size // 2, depth + 1, depth, 1)
        return moved(pointer, depth, node)

    tail.next = fork(0, 0, n - 1, None)
    return head


if __name__ == "__main__":
    import sys

    from .render import render

    tt = sys.argv[1] if len(sys.argv) > 1 else "0001"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "line_bool_out.png"
    render(line_boolean(tt)).save(out_path)
    print(f"wrote {out_path}")
