"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Index, flags and cursor: ``n + 49 + bl(S)``, S the worst program length.

    A negated setter's cell reaches -1, one bit more.  The reversed twin is
    picked only on a shorter program, yet one still reaches the top bit length
    of S: a long run of equal pairs at the front.
    """
    return n + 49 + (6 * (1 << n) + 10 * n + 61).bit_length()
