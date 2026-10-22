"""Executed word bounds."""


def execution(n: int, _: str) -> int:
    """5N + 21n + 9, N the most distinct subtables a diagram holds.

    A level of height h has 2^(n-h) positions and 2^2^h subtables; the
    branch avoids building 2^2^h when it is the larger.
    """
    nodes = sum(
        1 << (1 << h) if 1 << h <= n - h else 1 << (n - h) for h in range(n + 1)
    )
    return 5 * nodes + 21 * n + 9
