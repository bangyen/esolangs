"""Smu's emitted characters: each level filled to capacity, repeats macro'd."""


def _chars(n: int, _: str) -> int:
    """C: 107 + per level 3 a node, 2 a pad, plus 2D + E or 3(E - D) of macro names.

    Exact at n = 3, 5, 9, 10, 11 (n = 7: no table reaches it, the 4 level-5 pads
    used twice stay inline, 3 < 4).  From n = 12 it is the price before
    the delimiter macros, an upper bound only (witness 4,256 at n = 12, 42,532
    at n = 16, against 6,267 and 59,330): the old constants no longer fit
    and the exact worst case is open.  Before them, from n = 12 the 256
    eight-bit subtables are each named, one-letter names going to the most
    used; exact to n = 15.  From n = 16 (32 uses, above the
    4-bit tables' 31) the 8-bit tables outrank the lower macros: 47 get
    one-letter names, the rest and every 4- and 2-bit macro two letters, so
    5T/8 + 465T/2048 + 3490, exact at n = 16 only.  Past n = 16 that price
    charges every subtable once per distinct parent; a level n - 4 pair
    repeated twice under a three-letter name fails the macro test
    ((2 - 1) * 9 <= (2 + 2) * 3) and is written out at both places, so its
    subtables collect two references per parent while names still rank by
    parents.  Keeping the 47 one-letter subtables' pairs distinct and
    repeating the 209 two-letter subtables' pairs beats it (n = 17
    116,224 > 115,170; n = 19 454,881 > 450,210; n = 20 905,770 > 896,930),
    so 6T + 90 bounds past n = 16.
    """
    if n > 16:
        return 6 * (1 << n) + 90
    if n > 15:
        return 5 * (1 << (n - 3)) + 465 * (1 << (n - 11)) + 3490
    if n > 11:
        uses = 1 << (n - 11)  # parents of each eight-bit subtable
        # Names go by use: the 4-bit tables (31 uses) first; the 2-bit tables
        # (7) are one-letter only while uses < 7, else the 8-bit tables take
        # the remaining 27 or 31 one-letter names.
        short, tail = (27, 1) if uses < 7 else (31, 2)

        def unequal(letters: int) -> int:
            """A 7-character subtable inline or as a macro, whichever is shorter."""
            return min(7 * uses, 7 + (uses + 2) * letters)

        def pad(letters: int) -> int:
            return min(4 * uses, 4 + (uses + 2) * letters)

        lower = 8 * tail + 22 + 104 + 28 * tail  # the 2- and 4-bit macros
        named = 16 * pad(1) + (short - 16) * unequal(1) + (256 - short) * unequal(2)
        return 95 + 5 * ((1 << (n - 3)) - 1) + lower + named
    # 107 = 95 + the X, Y, W delimiter macros (4 each), a delimiter defined
    # only past 4 uses: with 6 or fewer pads (n <= 5) W is not, and each pad
    # is one character longer.
    total, edges, pads_all = 107, 1, 0
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
    return total + edges - (4 - pads_all if pads_all <= 4 else 0)


FORMULAS = {
    "scaling": (
        _chars,
        frozenset((3, 5, 9, 10, 11)),
        (3, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18),
    )
}
