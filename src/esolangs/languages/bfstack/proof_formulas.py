"""Executed command and snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program.

    Past seven inputs the root is a zero arm (stack peak ``n + 6``) or a one
    arm (loop at position 51: six bits, not ``bl(L)``): never both at full
    width.  At n = 9 the zero arm's loop sits below 2^11 (a one arm of a
    1,510-character block), one bit short.

    An identity has no loops and at most two six-bit input bytes. Inside a
    tree it replaces a block of at least eight remaining reads: its twelve
    data bits plus the ancestor sentinels fit n+6. The cursor and loop
    positions use the emitted L, so shortening a block preserves the bound.
    Alone it uses at most 12+bl(n)+bl(L) bits (six data bits when n=1),
    below this formula also for n<8.
    At n=9 an identity one arm puts the zero-arm loop below 128; an identity
    zero arm has no decoder loops, while the one-arm loop stays at 51.
    Thus the one-bit n=9 correction survives either shortened arm.
    """
    bl = int.bit_length
    return (
        n
        + 6
        + (n < 8)
        - (n == 9)
        + bl(n)
        + (max(n - 8, 0) + min(1 << n, 255) + 2) * bl(len(p))
    )
