"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 73 * n + 371 + 13 * (n % 2)


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        n
        + 7
        + bl(n)
        + (max(n - 7, 0) + (3 * min(1 << n, 128) + 1) // 5 + 3) * bl(len(p))
    )
