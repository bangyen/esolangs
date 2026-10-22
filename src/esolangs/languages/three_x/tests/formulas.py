"""3x key and workspace bounds."""

from esolangs.languages.three_x.generator import _COMPLEMENT

bl = int.bit_length


def _key(i: int) -> int:
    """K(i), a bound on the ith 3x key's bits: after w wraps a/3^w, |value| <= 3/2."""
    return 2 * bl(3 ** bl(i - 1)) + 1


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


FORMULAS = {"workspace": (_three_x, False, (3, 5))}
