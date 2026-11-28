"""Witnesses for the finite source maxima."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Reach the exhaustive source-size maxima."""
    size = ("10", "1110", "11101001", "1110110110000100")
    return (size[n - 1],) if 1 <= n <= len(size) else ()
