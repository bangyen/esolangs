"""Executed command bounds.

Popcount-symmetric tables may reverse input cells: the comb drawing stays
fixed and the shorter loader only lowers this bound. The nonsymmetric
worst-case witnesses retain the original layout.
"""


def execution(n: int, program: str) -> int:
    """Shared one-edges cap the tree at 3T/4 + 1 rows (n=3,4 exhaustive).

    At n = 17 every row of the eleven corpus tables was run once:
    worst 7,654 commands, no output wrong, none over this bound.
    """
    if program[0] in ("$", "-", "+"):
        return 3 * n + 2 + program.endswith("-*")
    return max(3 * (1 << n) // 4 + 1, 6 * n - 1) + 3 * (1 << n) // 4 + 1 + 3 * n + 6


def workspace(n: int, program: str) -> int:
    """A constant's tape, column and cell pointer; otherwise the comb."""
    if program[0] in ("$", "-", "+"):
        bit = program.endswith("-*")
        return n + 1 + (3 * n + bit).bit_length() + n.bit_length()
    return (
        n
        + 5
        + max(6 * n - 2, (1 << n) - 1).bit_length()
        + (3 * n + 4).bit_length()
        + n.bit_length()
    )
