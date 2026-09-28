"""Underload boolean generator: equal-width selectors force a promise tree."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
)

# ``()!`` and ``:!`` are stack-neutral before the shared selector suffix.
PAIR = ("(()!!^)", "(:!~!^)")


def underload(truth_table: str) -> str:
    """Return an Underload template computing ``truth_table`` in linear text."""
    n = _validate_truth_table(truth_table)
    reflected = "".join(
        truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(1 << n)
    )
    constant = constant_span_test(reflected)

    def tree(level: int, lo: int, hi: int) -> str:
        if constant(lo, hi):
            return "!" * (n - level) + f"({reflected[lo]})S"
        mid = (lo + hi) // 2
        return f"({tree(level + 1, lo, mid)})~({tree(level + 1, mid, hi)})~^"

    slots = TEMPLATE_CHAR * (len(PAIR[0]) * n)
    return slots + f"({tree(0, 0, len(reflected))})^"
