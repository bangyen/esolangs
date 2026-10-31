"""BrainIf's emitted characters: the layered DAG at its widest."""


def _digit_sum(first: int, step: int, count: int) -> int:
    """Total decimal digits of first, first + step, ... (count terms)."""
    total, power = 0, 1
    while True:
        above = count if first >= power else max(0, count - -(-(power - first) // step))
        if not above:
            return total
        total += above
        power *= 10


def _chars(n: int, _: str) -> int:
    """W: layer d holds c_d = min(c_(d-1)^2, 2^(n-1-d)) nodes, c_(-1) = 2."""
    nodes, prev = [], 2
    for d in range(n):
        prev = min(prev * prev, 1 << (n - 1 - d))
        nodes.append(prev)
    lines = [3 if d == n - 1 else 4 for d in range(n)]  # lines a node
    start, line = {}, 1
    for d in reversed(range(n)):  # the root layer is emitted first
        start[d] = line
        line += nodes[d] * lines[d]
    out0, out1 = line, line + 51
    done = out1 + 3
    chars = 0
    for d in range(n):
        # Reads and two `if 4x goto ` heads a node.
        chars += nodes[d] * ((10 if d == n - 1 else 26) + 22)
        if d == 0:
            # Distinct pairs, the most `out_1` targets first: 2, 3, then 4 of 4.
            ones = min(nodes[0] + 1, 4)
            chars += (2 * nodes[0] - ones) * len(str(out0)) + ones * len(str(out1))
            continue
        below = nodes[d - 1]
        spread = _digit_sum(start[d - 1], lines[d - 1], below)
        if 2 * nodes[d] == below:  # each below node is the target once
            chars += spread
        elif nodes[d] == below * below:  # every ordered pair: 2*below targets each
            chars += 2 * below * spread
        else:  # the one mixed layer shares one digit width (checked to n = 40)
            last = start[d - 1] + (below - 1) * lines[d - 1]
            chars += 2 * nodes[d] * len(str(last))
    climb = sum(len(f"if {k} increment") for k in range(48))
    chars += 16 + climb + 12 + 2 * (11 + len(str(done))) + 15 + 12
    return chars + sum(nodes[d] * lines[d] for d in range(n)) + 54 - 1


FORMULAS = {"scaling": (_chars, False, (1, 2, 3, 4, 5))}
