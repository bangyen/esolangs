"""Shared helpers for the boolean-function program generators.

The generators in this package build programs that read ``n`` boolean
inputs and print the result of a truth table; the helpers here are the
common input handling they all repeat.
"""


def _validate_truth_table(truth_table: str, n: int) -> None:
    """Reject a truth table that is not ``2**n`` binary entries."""
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def _complement(truth_table: str) -> str:
    """Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str, n: int) -> tuple[str, bool]:
    """Return the table (or its complement) and whether it was flipped.

    A table with more ones than zeros is cheaper to evaluate complemented
    and inverted, so generators flip when ones dominate.
    """
    if truth_table.count("1") > 2**n // 2:
        return _complement(truth_table), True
    return truth_table, False
