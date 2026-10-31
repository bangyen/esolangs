"""DecLEQ's emitted characters: header, pass loop, six cells per distinct subtree."""


def _chars(n: int, _: str) -> int:
    """B: header, reads and pass loop exactly; the tree by distinct-subtree counts."""
    code = -(-(18 + n) // 3) * 3
    nodes = sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(n))
    cells = 15 + 2 + (code - 17) + 3 * n + 3 * n + 6 + 6 * nodes + 3
    d = max(2, len(str(cells)))
    return (
        16
        + len(str(code))
        + 2 * d
        + 4
        + (code - 17)
        + 1  # the counter cell holds 47
        + 6 * n  # the reads
        + 5 * n  # the decrements
        + 2 * len(str(17 + n))
        + 2 * d  # the counter's exit, the loop's return
        + 2
        + nodes * (4 + d)
        + (nodes + 1) * (2 + d)
        + (cells - 1)
    )


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6))}
