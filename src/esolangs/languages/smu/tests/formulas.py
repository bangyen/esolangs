"""Smu's emitted characters: each level filled to capacity, repeats macro'd."""


def _chars(n: int, _: str) -> int:
    """C: 95 + per level 5 a node, 3 a pad, plus 2D + E or 4(E - D) of macro names.

    Exact to n = 10 (the rule fails from n = 12); past it, 6T + 90 bounds.
    """
    if n > 10:
        return 6 * (1 << n) + 90
    total, edges = 95, 1
    for j in range(n):
        s = 1 << (n - j)
        nodes = min(1 << j, 1 << s)
        unequal = min(nodes, (1 << s) - (1 << (s // 2)))
        pads = nodes - unequal
        if j:
            total += 2 * nodes + edges if edges >= 2 * nodes else 4 * (edges - nodes)
        total += 5 * unequal + 3 * pads
        edges = 2 * unequal + pads
    return total + edges


FORMULAS = {"scaling": (_chars, True, (3, 5, 7, 9, 10))}
