"""SendStuff's emitted characters: an upper bound over the saturated diagram."""


def _digits(x: int) -> int:
    return len(str(x))


def _chars(n: int, _: str) -> int:
    """C: per depth d, B branching, E equal-halves and chain nodes.

    Every node sits at the longest ids.
    """
    s = [1 << (n - d) for d in range(n)]
    full = [d >= s[d] for d in range(n)]  # every 2^s subtable of the depth can appear
    bra = [(1 << s[d]) - (1 << (s[d] // 2)) if full[d] else 1 << d for d in range(n)]
    eq = [(1 << (s[d] // 2)) - 2 if full[d] else 0 for d in range(n)]
    con = [2 if full[d] and d else 0 for d in range(n)]
    pos = [(1 << s[d]) if full[d] else 1 << d for d in range(n)]
    lam = [_digits(1 + sum(bra[j] + eq[j] for j in range(d, n))) for d in range(n)]
    # Macros, ">root", the two leaves.
    total = 64 + 1 + lam[0] + 2 * (24 + _digits(n))
    for d in range(n):
        kap = 1 + _digits(d)  # z<d> / o<d>
        total += bra[d] * (10 + lam[d]) + eq[d] * (9 + lam[d]) + con[d] * (9 + kap)
        slots = 2 * bra[d] + eq[d] + con[d]
        if d + 1 == n:
            total += slots * (1 + _digits(n))
        else:
            to_const = min(slots, 4 * (pos[d + 1] - 1) + 2)
            kap_below = 1 + _digits(d + 1)
            total += slots * lam[d + 1] + max(0, kap_below - lam[d + 1]) * to_const
    return total


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7))}
