"""Codesick's emitted characters: the saturated shared diagram."""


def _digit_sum(x: int) -> int:
    """Total decimal digits of 1..x."""
    total, low = 0, 1
    for width in range(1, len(str(x)) + 1):
        total += width * (min(x, 10**width - 1) - low + 1)
        low *= 10
    return total


def _chars(n: int, _: str) -> int:
    """W = 68C + 43 + 8 digits(ids 2..C+1) + E, E the digits of every child name.

    Exact for n = 2..36.  Size is 43 + sum over nodes of 68 + 8 digits(id) +
    digits(zero) + digits(one); ids run up by level, deepest first, so a level
    is a block of consecutive ids.  A node count below the level's cap loses
    at least 72 characters (the per-level bound is monotone in every count).
    The transition level takes the best distinct pairs, but for n = 20..36
    (ids of widths 3, 4, 5) covering all 65,534 ranks once binds first, the
    spares going to 5-digit pairs: 9,000 below the two-width greedy.
    """
    nodes = [min(1 << d, (1 << (1 << (n - d))) - 2) for d in range(n)]
    g = next(d for d in range(n) if (1 << (1 << (n - d))) - 2 <= 1 << d)
    first = [2] * (n + 1)  # lowest id of level d; ids ascend upward
    for d in range(n - 1, -1, -1):
        first[d] = first[d + 1] + (nodes[d + 1] if d + 1 < n else 0)

    def digits(d: int) -> int:  # digits summed over the ids of level d
        return _digit_sum(first[d] + nodes[d] - 1) - _digit_sum(first[d] - 1)

    edges = 0
    for d in range(n):
        if d >= g:  # every pair but (0,0), (1,1) over the level below
            below = nodes[d + 1] if d + 1 < n else 0
            names = 2 + (digits(d + 1) if d + 1 < n else 0)
            edges += 2 * (below + 2) * names - 4
        elif d < g - 1:  # every child named once
            edges += digits(d + 1)
        else:  # the 2^d pairs over level g: low ids covered in pairs, heaviest next
            low = len(str(first[g]))
            high = len(str(first[g] + nodes[g] - 1))
            if low == high:
                edges += 2 * nodes[d] * low
            elif high - low > 1:  # three widths: cover every rank, spares at the top
                edges += digits(g) + (2 * nodes[d] - nodes[g]) * high
            else:
                lows = 10**low - first[g]
                highs = nodes[g] - lows
                cover = (lows + 1) // 2
                rest = nodes[d] - cover
                edges += 2 * low * cover
                classes = [
                    (2 * high, highs * highs),
                    (high + low, 2 * highs * lows),
                    (high + 1, 4 * highs),
                    (2 * low, lows * lows - cover),
                    (low + 1, 4 * lows),
                    (2, 2),
                ]
                for weight, count in sorted(classes, reverse=True):
                    take = min(rest, count)
                    edges += take * weight
                    rest -= take
    total = sum(nodes)
    return 68 * total + 43 + 8 * (_digit_sum(total + 1) - 1) + edges


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14))}
