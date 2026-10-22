"""Suffolk's emitted characters: the countdown sweep."""


def _chars(n: int, _: str) -> int:
    """F: (17T + 316n + 482)/2, one less from n = 7.

    The sweep's worst halves alternate with one equal pair; from n = 7 that
    table's cofactors share and the NOR DAG wins, and swapping its first two
    entries costs the sweep one character (exhaustive n = 4; the
    one-pair family enumerated at n = 7, 8).
    """
    return (17 * (1 << n) + 316 * n + 482) // 2 - (n >= 7)


FORMULAS = {"scaling": (_chars, True, (4, 5, 6, 7, 8))}
