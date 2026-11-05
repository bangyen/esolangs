"""Smu's emitted characters: each level filled to capacity, repeats macro'd."""


def _chars(n: int, _: str) -> int:
    """Return default-source legacy ceilings, then the universal raw-tree ceiling.

    Registered exact rungs are 3, 5, 9, 10, 11. The tighter n=12..16 prices used
    47 names; their derivation for the current 44-name allocator is open.
    Raw 44-name witness prices exceed them by 9, 18, 30, 54, 102 chars;
    the shipped delimiter-compressed witnesses still fit.

    A raw leaf costs 1; a branch costs 5 plus its children, a pad 3 plus
    its child. Thus a height-n tree costs at most 6T-5, plus 91 fixed chars.
    A kept macro's u direct parents guarantee at least u references; its
    (u-1)b > (u+2)l admission saves text even when ancestors inline.
    Each chosen delimiter occurs at least five times in the all-delimiter
    build, hence in the expanded tree, paying its four-character definition.
    X/Y/W are reserved, so these counts contain no macro names.
    The resulting 6T+86 bound does not depend on macro-name lengths.
    """
    if n > 16:
        return 6 * (1 << n) + 86
    if n > 15:
        return 5 * (1 << (n - 3)) + 465 * (1 << (n - 11)) + 3486
    if n > 11:
        uses = 1 << (n - 11)  # parents of each eight-bit subtable
        # Historical 47-name pricing: the 4-bit tables (31 uses) first; the 2-bit tables
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
        return 91 + 5 * ((1 << (n - 3)) - 1) + lower + named
    # 103 = 91 + the X, Y, W delimiter macros (4 each), a delimiter defined
    # only past 4 uses: with 6 or fewer pads (n <= 5) W is not, and each pad
    # is one character longer.
    total, edges, pads_all = 103, 1, 0
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
