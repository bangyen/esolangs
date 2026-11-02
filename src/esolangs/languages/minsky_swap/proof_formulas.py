"""Command and snapshot bounds for the pair cascade and symmetric reader."""


def commands(n: int) -> int:
    """The maximal compact command-line length, including ignored-tail macros."""
    return max((1 << n) + 6 * n + 12, 16 * n + 4)


def execution(n: int, _p: str) -> int:
    """The maximal native commands before the post-halt dump."""
    return max((1 << n) + 6 * n + 5, 16 * n - 3)


def workspace(n: int, _p: str) -> int:
    """An upper bound: two register magnitudes, pointer, and full code cursor."""
    # A tail macro raises scratch to six but removes an index bit, so n+3
    # still bounds both register magnitudes and the pointer together.
    return n + 3 + commands(n).bit_length()
