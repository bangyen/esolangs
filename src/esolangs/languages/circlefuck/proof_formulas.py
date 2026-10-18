"""Executed command bounds."""


def execution(n: int, p: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return (
        (2 * n + 13) * (1 << n) + 94 * n + 89 + 2 * sum(map(ord, p[1 : n + 1]))
        # 94n = 63n + 31n loop-based 48-normalization in _READ
    )
