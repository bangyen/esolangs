"""Boolean template generator for bfpda."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)
from esolangs.tools.wrap import wrap_chars

__all__ = ["BFPDA_PAIR", "bfpda"]


BFPDA_PAIR = ("x", "@")


def bfpda(truth_table: str) -> str:
    """Return a BF-PDA template for a binary, MSB-first ``2**n`` truth table.

    The last input is tested first; every arm empties the stack so its ``]``
    exits. Characters outside @.<>[] are comments; the first marker is a bare @.
    """
    n = _validate_truth_table(truth_table)

    # Marker then bit, per input in name order.
    head = "<".join(["@<" + TEMPLATE_CHAR] * n)

    def leaf(level: int, value: str) -> str:
        # ``left`` cells still hold untested inputs; a one stops on the bottom
        # marker and prints it (left == 0: only that marker remains).
        left = 2 * (n - level)
        if value == "0":
            return ">" * left + "."
        return ">" * (left - 1) + ".>" if left else "@.>"

    # The stack hands back the *last* input first: level ``i`` tests input
    # ``n - 1 - i``, row bit ``i``; bit-reversed, each subtree is a span.
    reflected = "".join(
        truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(2**n)
    )
    constant = constant_span_test(reflected)
    ids = subtree_ids(reflected)
    pieces = [head]

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


LANGUAGE = Language(
    "BF-PDA",
    "stack_based.bf_pda",
    boolean=bfpda,
    contract=BooleanContract(
        parameterized=True,
    ),
    wrap=wrap_chars,
    empty_program="BF-PDA program cannot be empty",
    example=Example(pair=BFPDA_PAIR),
)
