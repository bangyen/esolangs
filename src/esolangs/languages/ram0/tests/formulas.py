"""RAM0's emitted characters: tokens from distinct subtables per level."""


def _chars(n: int, _: str) -> int:
    """C: tokens bounded by the distinct subtables of each level."""
    nodes = [
        min(1 << k, (1 << (1 << (n - k))) - (1 << (1 << (n - k - 1)))) for k in range(n)
    ]
    prefix = n * (n + 9) // 2
    base = 8 + prefix + sum(nk * (n - k + 4) for k, nk in enumerate(nodes))
    tokens = base if base + 1 < 10**4 else base + 2 * sum(nodes)
    digits = len(str(tokens + 1))
    return 2 * tokens - 1 + (2 * sum(nodes) + 1) * (digits - 1)


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6))}
