"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Parity's gate path 2n - 1 and two ticks; pool and bundles stay within it.

    Past n = 12 the class banks are bounded only by their admission arithmetic.
    """
    return 2 * n + 1 + (n > 12)


# Latches never clear: 3T - 6 + n flat slots, 6T - 10 + n under the
# H-layout. Same-state pulses are an antichain: T/2 + n flat, T + n after.
def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if n <= 7:
        return 7 * (1 << n) // 2 + 2 * n - 5
    return 7 * (1 << n) + 2 * n - 9
