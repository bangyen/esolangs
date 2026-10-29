"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return (11 * n + 4) * ((1 << n) // n) + 11 * (1 << n) + 13 * n - 17 + (n >= 10)


def _add_sub_jump(n: int, _: str) -> int:
    """Every program address's bits, the T/n packed cells, Q the rest."""
    bl = int.bit_length
    c = -(-(1 << n) // n)
    i = 5 * n + 54
    b = 4 * i
    m = b + 14 + 2 * c
    q = i * bl(b) + (3 * i - 2) * bl(b + 13) + 2 * bl(m - 1) + bl(20 * n + 212) + 23
    return sum(map(bl, range(m))) + c * (n + bl(b + 13 + c)) + 3 * n + 5 * bl(n) + q


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _add_sub_jump(n, p)
