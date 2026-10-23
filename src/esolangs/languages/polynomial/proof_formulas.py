"""Instruction-count and snapshot-bit bounds."""


def states(n: int, k: int) -> int:
    """Most distinct residual subtables at level ``k`` of an ``n``-input table."""
    return min(1 << k, 1 << (1 << (n - k)))


def commands(n: int) -> int:
    """Most instructions of the shipped program: the bound ``A``.

    The k = 0 state machine costs 3 for level 0, at most 6 a block at the
    others and 6 a leaf; the hybrid takes the fewest over k, and a reduced
    table of m < n inputs adds n - m reads, less than A(n) - A(m).  The
    older 10T - 7 is the tighter term at n = 1.
    """
    levels = sum(states(n, k) for k in range(n))
    return min(10 * (1 << n) - 7, 3 + 6 * (levels - 1) + 6 * states(n, n), 1934)


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        bl(commands(n) + 10)
        + 1
        + max(bl(n + 3), bl(49 * (max(states(n, k) for k in range(n + 1)) - 1)))
        + 2 * bl(n)
    )
