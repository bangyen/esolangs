"""Snapshot-bit bounds."""


# Atomic muxes use three slots instead of six (four with a root NOT);
# prefix definitions are not outer-machine state. Primitive copied pools
# retain their geometry and slots. Latches never clear: 3T - 6 + n flat
# slots, 6T - 10 + n under the
# H-layout. Same-state pulses are an antichain: T/2 + n flat, T + n after.
def workspace(n: int, program: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if program in ("-\n" * n + "(-:", "-\n" * n + ")-:"):
        # n discarded port events, the source event and the halt flag.
        return n + 2
    if n <= 7:
        return 7 * (1 << n) // 2 + 2 * n - 5
    return 7 * (1 << n) + 2 * n - 9
