"""Smu's finite low-arity diagram prices."""


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Count the node and edge price, terminal edges and pads through n=11."""
    if n > 11:
        return {"B": 0, "E": 0, "P": 0}
    # 103 = 91 + the X, Y, W delimiter macros (4 each), a delimiter defined
    # only past 4 uses: with 6 or fewer pads (n <= 5) W is not, and each pad
    # is one character longer.
    total, edges, pads_all = 0, 1, 0
    for j in range(n):
        s = 1 << (n - j)
        nodes = min(1 << j, 1 << s)
        unequal = min(nodes, (1 << s) - (1 << (s // 2)))
        pads = nodes - unequal
        pads_all += pads
        if j:
            total += 2 * nodes + edges if edges >= 2 * nodes else 3 * (edges - nodes)
        total += 3 * unequal + 2 * pads
        edges = 2 * unequal + pads
    return {"B": total, "E": edges, "P": pads_all}
