r"""Build a Line program computing a given boolean truth table directly."""

from __future__ import annotations

from render import Node, chain


def _validate_truth_table(truth_table: str) -> int:
    r"""Validate a truth table and return its input count ``n``."""
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
    r"""Build a Line program computing ``truth_table`` (see module."""
    n = _validate_truth_table(truth_table)

    # Read n inputs into cells.
    head = Node("i")
    tail = head
    for _ in range(n - 1):
        move = Node(">")
        tail.next = move
        read = Node("i")
        move.next = read
        tail = read
    # Walk back to cell 0 so the.
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
                # Advance to the next input's.
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

    from render import render

    tt = sys.argv[1] if len(sys.argv) > 1 else "0001"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "line_bool_out.png"
    render(line_boolean(tt)).save(out_path)
    print(f"wrote {out_path}")
