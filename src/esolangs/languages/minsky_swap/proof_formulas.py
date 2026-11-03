"""Command and snapshot bounds for the pair cascade and symmetric reader."""


def commands(n: int) -> int:
    """The maximal compact command-line length, including ignored-tail macros."""
    return max((1 << n) + 6 * n + 12, 16 * n + 4)


def execution(n: int, _p: str) -> int:
    """The maximal native commands before the post-halt dump."""
    return max((1 << n) + 6 * n + 5, 16 * n - 3)


def workspace(n: int, _p: str) -> int:
    """An upper bound: two register magnitudes, pointer, and full code cursor."""
    # Held scratch uses two bits, the index at most m-1. A tail macro uses
    # three scratch bits but has m<=n-1; zero index still costs one bit.
    # Thus registers plus pointer need n+2 bits from n=3, n+3 below it.
    # The symmetric path needs <=3+bl(n), and constants need less.
    return n + (3 if n <= 2 else 2) + commands(n).bit_length()
