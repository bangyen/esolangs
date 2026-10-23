"""Circuit Diagram's emitted cells: the H-tree pool bounds every race."""


def _cells(n: int, _: str) -> int:
    """F: the pool's reserved square plus the port margin, n >= 9.

    The race keeps the smaller of the pool and every rival, so its area is
    at most the pool's.  The pool takes atoms of k = 7 (odd n) or 8 inputs
    at the leaves; a leaf is 8 * ((4G + 10k + 59) // 8) square, G = 14 +
    3(2^(k-2) - 1) + k, and each two prefix levels double the side and add a
    16(r + k) + 8 band.  That recurrence is
    D = (leaf + 16k + 72) 2^((n-k)/2) - 16n - 72; the margin is 8n + 8.
    """
    k = 7 if n % 2 else 8
    gates = 14 + 3 * ((1 << (k - 2)) - 1) + k
    leaf = 8 * ((4 * gates + 10 * k + 59) // 8)
    side = (leaf + 16 * k + 72) << ((n - k) // 2)
    return (8 * n + 8 + side - 16 * n - 72) ** 2


FORMULAS = {"scaling": (_cells, False, (9, 10, 11))}
