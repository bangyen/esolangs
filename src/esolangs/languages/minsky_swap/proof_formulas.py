"""Command and snapshot bounds for the pair cascade and symmetric reader."""


def commands(n: int) -> int:
    """The maximal compact command-line length, including ignored-tail macros."""
    return max((1 << n) + 6 * n + 12, 16 * n + 4)
