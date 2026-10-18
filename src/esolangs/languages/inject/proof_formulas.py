"""Snapshot-bit bounds."""


def _inject(n: int, _: str) -> int:
    """The program text after the n reads, its label spans and cursor."""
    bl = int.bit_length
    spans = sum(bl(3 * i) + bl(3 * i + 2) for i in range(n + 3))
    spans += sum(map(bl, range(2 * n + 5, 6 * n + 5)))
    return 24 * (1 << n) + 516 * n + 169 + bl(12 * n + 10) + bl(2 * n) + bl(n) + spans


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _inject(n, p)
