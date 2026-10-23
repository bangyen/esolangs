"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 8 * (1 << (2 * n)) + 43 * (1 << n) + 15 * n - 5


def workspace(n: int, program: str) -> int:
    """Written-state peaks: tape, pointer, cursor, rotation count, input count.

    The tape peaks at 2T + 2 cells (the strip, the Horner scratch pair) with a
    count of 2^n - 1 (n bits) and one decrement-wrapped 255 (8) on it;
    pointer at most 2T + 6, cursor L, rotation the execution bound.
    """
    t = 1 << n
    bl = int.bit_length
    return (
        2 * t
        + n
        + 8
        + bl(2 * t + 6)
        + bl(len(program))
        + bl(execution(n, program))
        + bl(n)
    )
