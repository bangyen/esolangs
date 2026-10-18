"""Executed command and snapshot-bit bounds."""


# Each one entry costs a step; a constant folds to one level, so the
# worst table is all ones but one.  The constants carry the tail's 51
# columns, which the westbound drive crosses once per program since the
# tail stopped overlapping the fill.
def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if n < 8:
        return 3 * (1 << n) + 110 * n + 106
    return 4 * (1 << n) + 14 * n + 650


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    # Peak car state is 13 + bl(width), width = 2T + 57 + G.
    return (
        n * (1 << n)
        + 2 * n
        + 25
        + bl(
            (1 << (n + 1)) + 57 + sum(max(51, (1 << (k - 1)) + 3) for k in range(1, n))
        )
        + 2 * bl(n)
    )
