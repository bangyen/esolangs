"""Boolean template generator for bfpda."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)

__all__ = ["BFPDA_PAIR", "bfpda"]


BFPDA_PAIR = ("x", "@")


def bfpda(truth_table: str) -> str:
    """Return a BF-PDA template for a binary, MSB-first ``2**n`` truth table.

    Each setter flips a fresh zero cell above a marker. The last input is
    tested first: [>> one ]>[> zero ] consumes its bit and marker. Leaves
    empty the stack so closing brackets exit; one prints the bottom marker.
    Characters outside @.<>[] are comments; the first marker is a bare @.
    """
    n = _validate_truth_table(truth_table)

    # Marker then bit, in name order, so the tree tests the last input
    # first (the same tree reflected; the reversed load bought nothing and
    # put the runs out of order).
    head = "".join("<@<" + run for run in ([TEMPLATE_CHAR * len(BFPDA_PAIR[0])] * n))[
        1:
    ]

    def leaf(level: int, value: str) -> str:
        # A one stops on the bottom entry, the first marker, and prints it.
        left = 2 * (n - level)
        if value == "0":
            return ">" * left + "."
        return ">" * (left - 1) + ".>" if left else "@.>"

    # The load pushes in name order, so the stack hands back the *last*
    # input first: level ``i`` tests input ``n - 1 - i``, row bit ``i``.
    # Through the bit-reversed index that subtree is a contiguous span.
    reflected = "".join(
        truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(2**n)
    )
    constant = constant_span_test(reflected)
    ids = subtree_ids(reflected)
    pieces = [head]

    # Not routed through :func:`decision_tree_tokens`: a plain string with no
    # index to thread, so its token lists would be one-element lists throughout.
    def node(i: int, lo: int, hi: int) -> None:
        if i == n or constant(lo, hi):
            pieces.append(leaf(i, reflected[lo]))
            return
        mid = (lo + hi) // 2
        below = ids[i + 1]
        if below[lo >> (n - i - 1)] == below[mid >> (n - i - 1)]:
            pieces.append(">>")  # halves agree: drop bit and marker, untested
            node(i + 1, lo, mid)
            return
        # Each arm ends on an empty stack, so its ``]`` exits as it stands.
        pieces.append("[>>")
        node(i + 1, mid, hi)
        pieces.append("]>[>")
        node(i + 1, lo, mid)
        pieces.append("]")

    node(0, 0, 2**n)
    return "".join(pieces)
