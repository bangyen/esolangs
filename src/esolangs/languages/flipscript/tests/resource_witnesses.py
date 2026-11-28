"""Witnesses for the finite source maxima."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Reach the exhaustive source-size maxima."""
    size = ("10", "1001", "11100001", "1110110111001010")
    return (size[n - 1],) if 1 <= n <= len(size) else ()
