"""3x key and workspace bounds."""

bl = int.bit_length


def _key(i: int) -> int:
    """K(i), the ledger's bound on the ith 3x key's bits."""
    return 2 * bl(2 ** (i - 1) * 3 ** (2 * i - 1)) + 1


def _three_x(n: int, p: str) -> int:
    """Guard residues, read cursor and the 2n + 1 keys, K a key's bits."""
    return (
        n * bl(len(p))
        + 3 * 2**n // 2
        + 2 * n
        + 16
        + bl(2 * n - 1)
        + 2 * _key(2 * n + 1)
        + sum(_key(i) + 3 for i in range(1, 2 * n + 2))
    )


FORMULAS = {"workspace": (_three_x, False, (3, 5))}
