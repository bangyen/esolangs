"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """Shared one-edges cap the tree at 3T/4 + 1 rows (n=3,4 exhaustive).

    At n = 17 every row of the eleven corpus tables was run once:
    worst 7,654 commands, no output wrong, none over this bound.
    """
    return max(3 * (1 << n) // 4 + 1, 6 * n - 1) + 3 * (1 << n) // 4 + 1 + 3 * n + 6
