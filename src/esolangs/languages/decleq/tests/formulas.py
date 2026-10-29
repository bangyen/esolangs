"""DecLEQ's emitted characters: header, chains, six cells per distinct subtree."""


def _chars(n: int, _: str) -> int:
    """B: header, reads and chains exactly; the tree by distinct-subtree counts."""
    code = -(-(17 + n) // 3) * 3
    nodes = sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(n))
    cells = 15 + 2 + (code - 17) + 3 * n + 141 * n + 6 * nodes + 3
    d = max(2, len(str(cells)))
    return (
        16
        + len(str(code))
        + 2 * d
        + 4
        + (code - 17)
        + 5 * n
        + 235 * n
        + nodes * (4 + d)
        + (nodes + 1) * (2 + d)
        + (cells - 1)
    )


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6))}
