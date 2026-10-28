"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Index cell and cursor: ``n + 32 + bl(S)``, S the worst program length.

    A negated setter's cell reaches -1, one bit more.  It is picked only on
    a shorter program, so it adds a bit exactly where one reaches the top
    bit length of S: every n but 4, where S passes 16T and none does.
    """
    length = 27 * (1 << n) // 2 + 10 * n + 6
    return n + 32 + length.bit_length() + (n != 4)
