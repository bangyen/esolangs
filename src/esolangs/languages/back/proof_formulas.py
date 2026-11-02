"""Executed command bounds.

Popcount-symmetric tables may reverse input cells: the comb drawing stays
fixed and the shorter loader only lowers this bound. The nonsymmetric
worst-case witnesses retain the original layout.
"""


def _constant(n: int, program: str) -> bool:
    """Whether ``program`` is the compact constant build.

    That build is one fixed template -- ``($-)^n`` input runs, a ``>^n``
    walk to the answer cell, an extra ``-`` flip for the one constant and
    the closing ``*`` -- and only it matches in full. The first character
    cannot select it: a comb program's loader opens with the same ``-$``
    pairs (the AND, NAND and NOR programs start ``-$>-``), so a
    first-char test charges comb programs the constant bounds.
    """
    return program == "$-" * n + ">" * n + ("-*" if program.endswith("-*") else "*")


def execution(n: int, program: str) -> int:
    """Shared one-edges cap the tree at 3T/4 + 1 rows (n=3,4 exhaustive).

    At n = 17 every row of the eleven corpus tables was run once:
    worst 7,654 commands, no output wrong, none over this bound.
    """
    if _constant(n, program):
        return 3 * n + 2 + program.endswith("-*")
    return max(3 * (1 << n) // 4 + 1, 6 * n - 1) + 3 * (1 << n) // 4 + 1 + 3 * n + 6


def workspace(n: int, program: str) -> int:
    """A constant's tape, column and cell pointer; otherwise the comb."""
    if _constant(n, program):
        bit = program.endswith("-*")
        return n + 1 + (3 * n + bit).bit_length() + n.bit_length()
    return (
        n
        + 5
        + max(6 * n - 2, (1 << n) - 1).bit_length()
        + (3 * n + 4).bit_length()
        + n.bit_length()
    )
