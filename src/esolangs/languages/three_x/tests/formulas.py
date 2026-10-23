"""3x key, emitted-size and workspace bounds."""

from fractions import Fraction

from esolangs.languages.three_x.generator import _COMPLEMENT

bl = int.bit_length


def _key(i: int) -> int:
    """K(i): bits of the ith key's value (numerator, sign, denominator).

    Rank i - 1 is ``_constant(i - 1)``: 3, then 0 wrapped once per binary
    digit after the leading one, ``v/3 - 1`` or ``1 - v/3``.
    """
    if i == 1:
        return 3
    value = Fraction(0)
    for digit in bin(i - 1)[3:]:
        value = value / 3 - 1 if digit == "0" else 1 - value / 3
    return (
        (abs(value.numerator).bit_length() or 1) + (value < 0) + bl(value.denominator)
    )


def _three_x(n: int, p: str) -> int:
    """Read cursor, guard positions and residues, keys and values.

    Every guard met leaves one 3-bit item; N bounds the names: the result,
    n bits, the complements the program stores (two snippets each) and the
    flags (one guard each, a shared block covers 24 rows).
    """
    names = 1 + n + str(p).count(_COMPLEMENT) // 2 + min(str(p).count("("), 2**n // 24)
    return (
        n * bl(len(p))
        + bl(2 * n - 1)
        + 3 * p.count("(")
        + 2 * n
        + 2 * _key(names)
        + 6 * bl(names - 1)
        + 9
        + sum(_key(i) + 3 for i in range(1, names + 1))
    )


def _width(rank: int) -> int:
    """Characters of the rank-th cheapest key: ``3``, then 4 + 3 (bl(k) - 1)."""
    return 1 if rank == 0 else 4 + 3 * (bl(rank) - 1)


def _chars(n: int, _: str) -> int:
    """The plain tree over n essential inputs; fewer essential inputs only shrink it.

    The shipped keys are the cheapest assignment for the real uses, so pricing
    the tree under any one fixed assignment bounds it: the result variable
    takes rank 0, then each level's bit and complement, deepest first.  A node
    at depth e is a leaf (a write of at most 5, or a copy of a bit or
    complement of a level >= e: 2 and its key) or, for e <= n - 2, a split (the
    bit's key, ``^(`` and a close of at most 4) over two nodes at e + 1.  The
    worst node recurses on e; the head reads and scales every bit and
    complements it, the tail prints the result.
    """
    bit = {n - 1 - i: _width(1 + 2 * i) for i in range(n)}
    comp = {n - 1 - i: _width(2 + 2 * i) for i in range(n)}
    result = _width(0)
    worst = 0
    for e in range(n - 1, -1, -1):
        leaf = result + max(5, 2 + max(max(bit[v], comp[v]) for v in range(e, n)))
        worst = leaf if e == n - 1 else max(leaf, bit[e] + 6 + 2 * worst)
    head = sum(48 + bit[v] + 2 * comp[v] for v in range(n))
    return head + worst + 8 + result


FORMULAS = {
    "scaling": (_chars, False, tuple(range(2, 10))),
    "workspace": (_three_x, False, (3, 5)),
}
