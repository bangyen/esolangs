"""Executed command bounds.

Popcount-symmetric tables may reverse input cells: the comb drawing stays
fixed and the shorter loader only lowers this bound. The nonsymmetric
worst-case witnesses retain the original layout.
"""


def _constant_bit(n: int, program: str) -> bool | None:
    """Identify the complete flat constant template, not a loader prefix."""
    # Nonconstant combs also start with '-'; a prefix gave 21 commands for
    # the 69-command six-input single-one table.
    prefix = "$-" * n + ">" * n
    if program == prefix + "*":
        return False
    if program == prefix + "-*":
        return True
    return None


def execution(n: int, program: str) -> int:
    """Shared one-edges cap the tree at 3T/4 + 1 rows (n=3,4 exhaustive).

    At n = 17 every row of the eleven corpus tables was run once:
    worst 7,654 commands, no output wrong, none over this bound.
    """
    bit = _constant_bit(n, program)
    if bit is not None:
        return 3 * n + 2 + bit
    return max(3 * (1 << n) // 4 + 1, 6 * n - 1) + 3 * (1 << n) // 4 + 1 + 3 * n + 6


def workspace(n: int, program: str) -> int:
    """A flat constant's tape and cursors; other layouts use the comb bound."""
    bit = _constant_bit(n, program)
    if bit is not None:
        return n + 1 + (3 * n + bit).bit_length() + n.bit_length()
    return (
        n
        + 5
        + max(6 * n - 2, (1 << n) - 1).bit_length()
        + (3 * n + 4).bit_length()
        + n.bit_length()
    )
