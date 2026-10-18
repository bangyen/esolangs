"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """At n=8 the large pool is one atom: no prefix/footer tick; parity reaches 17."""
    return 2 * n + 1 + (n > 8)


# Latches never clear: 3T - 6 + n flat slots, 6T - 10 + n under the
# H-layout. Same-state pulses are an antichain: T/2 + n flat, T + n after.
def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if n <= 7:
        return 7 * (1 << n) // 2 + 2 * n - 5
    return 7 * (1 << n) + 2 * n - 9
