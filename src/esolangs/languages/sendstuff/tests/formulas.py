"""SendStuff's emitted characters: an upper bound over the saturated diagram."""


def _digits(x: int) -> int:
    return len(str(x))


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price definitions and references at each layer's widest IDs."""
    s = [1 << (n - d) for d in range(n)]
    full = [d >= s[d] for d in range(n)]  # every 2^s subtable of the depth can appear
    bra = [(1 << s[d]) - (1 << (s[d] // 2)) if full[d] else 1 << d for d in range(n)]
    eq = [(1 << (s[d] // 2)) - 2 if full[d] else 0 for d in range(n)]
    con = [2 if full[d] and d else 0 for d in range(n)]
    pos = [(1 << s[d]) if full[d] else 1 << d for d in range(n)]
    lam = [_digits(1 + sum(bra[j] + eq[j] for j in range(d, n))) for d in range(n)]
    definitions = references = 0
    for d in range(n):
        kap = 1 + _digits(d)  # z<d> / o<d>
        definitions += (
            bra[d] * (10 + lam[d]) + eq[d] * (9 + lam[d]) + con[d] * (9 + kap)
        )
        slots = 2 * bra[d] + eq[d] + con[d]
        if d + 1 == n:
            references += slots * (1 + _digits(n))
        else:
            to_const = min(slots, 4 * (pos[d + 1] - 1) + 2)
            kap_below = 1 + _digits(d + 1)
            references += slots * lam[d + 1] + max(0, kap_below - lam[d + 1]) * to_const
    return {"A": definitions, "H": 1 + sum(bra) + sum(eq), "J": references}
