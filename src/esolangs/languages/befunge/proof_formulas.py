"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """Capped rows: straight-line headers, the same count on every table."""
    if n <= 8:
        return 5 * n + 16 + 4 * -(-n // 2)
    if n <= 10:
        return 5 * n + 29
    return 5 * n + 67
