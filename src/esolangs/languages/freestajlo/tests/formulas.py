"""Freestajlo workspace bound: the literal's codes dominate."""

bl = int.bit_length


def _plain(n: int) -> int:
    """P: the plain literal of m = min(n, 4) essential inputs, t = 2^m codes.

    The stack after ``&``: a zero, t 6-bit codes, the copy and the length;
    ip ends at 2n + 2m, the progress counter at 2n.  Plain is chosen exactly
    when m <= 4, so past n = 4 its worst ignores the other inputs.
    """
    m = min(n, 4)
    t = 1 << m
    return 6 * t + 7 + bl(t + 2) + bl(2 * n + 2 * m) + bl(2 * n)


def _packed(n: int) -> int:
    """W: 7 bits a full six-entry word, the zero, the length and the transient."""
    if n < 5:
        return 0
    t = 1 << n
    return (
        7
        + 7 * (t // 6)
        + bl(-(-t // 6) + 4)
        + max(16, 2 * n + 3)
        + bl(4 * n + 18)
        + bl(2 * n)
    )


def _freestajlo(n: int, _: str) -> int:
    """max(P, W): 117 at n = 4..6, the packed literal from n = 7."""
    return max(_plain(n), _packed(n))


FORMULAS = {"workspace": (_freestajlo, True, (3, 4, 5, 6, 7))}
