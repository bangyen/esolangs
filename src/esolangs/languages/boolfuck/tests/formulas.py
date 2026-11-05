"""Boolfuck's emitted characters: the unshared tree, shortened by later routes."""


def _chars(n: int, _: str) -> int:
    """The finite three-input maximum, then the inherited upper envelopes.

    Zero-child pruning lowers the exhaustive n=3 maximum to 162, reached by
    parity with row 6 flipped. Larger arities retain their old nonexact caps;
    the unchanged normalized gate route supplies the envelope from n=9.
    """
    if n == 3:
        return 162
    if n >= 9:
        return 85 * (1 << n) // 8 + 2 * n * n + 10 * n + 39
    return 35 * (1 << n) // 2 + 2 * n * n + 12 * n - (23 if n <= 7 else 11)
