"""Build a Line program computing a given boolean truth table directly.

No brainfuck intermediate: Line's ``i`` reads a whole number and ``o``
prints one, so 0/1 is exactly what ``IO`` hands over and no ASCII offset
enters.  The program reads each input into its own cell, returns to cell
0, then a ``?`` tree ``n`` deep whose ``2**n`` leaves build their entry
with ``+`` and print with ``o``.  ``truth_table`` is a binary string of
length ``2**n``, MSB first.  Arms are sized from measured subtree extent
(``render.py``), so n=4 renders at 1960x2160 rather than the old
~17000x9000; the round trip is correct for every combination through
n=10 (16800x14880, 23.7s extract, ~29s simulate), which
``tests/line/test_line_boolean.py`` exercises to n=8.  Nothing is
enforced; n=11 upward is untested.
"""

from __future__ import annotations

from .render import Node, chain


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``."""
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


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
    # Walk back to cell 0 so the decision tree tests bits in reading order.
    for _ in range(n - 1):
        move = Node("<")
        tail.next = move
        tail = move

    def leaf(bits: str) -> Node:
        value = truth_table[int(bits, 2)]
        ops = [">", *(["+"] if value == "1" else []), "o"]
        return chain(*ops)

    def fork(bits: str, depth: int) -> Node:
        if depth == n:
            return leaf(bits)

        def branch(bit: str) -> Node:
            sub = fork(bits + bit, depth + 1)
            if depth + 1 < n:
                # Advance to the next input's cell before testing it.
                move = Node(">")
                move.next = sub
                return move
            return sub

        node = Node("?")
        node.zero = branch("0")
        node.nonzero = branch("1")
        return node

    tail.next = fork("", 0)
    return head


if __name__ == "__main__":
    import sys

    from .render import render

    tt = sys.argv[1] if len(sys.argv) > 1 else "0001"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "line_bool_out.png"
    render(line_boolean(tt)).save(out_path)
    print(f"wrote {out_path}")
