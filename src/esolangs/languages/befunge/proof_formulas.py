"""Default command and written-state bounds."""


def execution(n: int, _: str) -> int:
    """Natural projections or one-row nibbles through eight, then six-bit decode."""
    # k>=3: factor9 + index(4k-11) + tail12 + ignored2(n-k).
    # k=2 needs a zero index; a natural projection costs 2n+23.
    if n <= 8:
        return max(2 * n + 23, 4 * n + 10)
    return 5 * n + 67


def workspace(n: int, _: str) -> int:
    """Immutable grid; nibble stack17, packed stack2n+11, plus written cursors."""
    if n == 1:
        return 14 + (2 * n + 23).bit_length() + (2 * n - 1).bit_length()
    if n <= 8:
        # Two essential bits need a zero index; otherwise the first index
        # input is bare. The 48* subtraction peaks at [f,cell,4,8].
        cursor = max(2 * n + 18, 4 * n + 10).bit_length()
        return 18 + cursor + (2 * n - 1).bit_length()
    return 2 * n + 23 + (2 * n - 1).bit_length()
