"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 2 * n + 3 + sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(1, n))


def _intercal(n: int) -> int:
    """Nine bits and a key per variable, S the Execution statement bound."""
    bl = int.bit_length
    s = 2 * n + 3 + sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(1, n))
    return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _intercal(n)
