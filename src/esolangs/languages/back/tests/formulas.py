"""Pair-comb/fold area bounds and derived witnesses; legacy corpus retained."""

#: Legacy searched regression corpus, retained unchanged, not production data.
#: n=6 blocks:0-5 had48-49 comb rows,6-8 full-fold45-47.
_BLOCKS = (
    "0111010001010010111000011010000111001010011110000100101000100010",
    "0111010010100100010111011110010111001010010010100111101001010010",
    "0101101001011010011101011010010100011101111011000101101000110101",
    "1010010111100101101001011010010110001010111000011110010100100101",
    "1010000100101100100010101100010100011010110010000101110111000111",
    "1000011110100011101011001010111001010001001000010011010111011010",
    "0101100001000101101110001010011101011010010110100110010110011010",
    "1101110100110101110110110100101110011010010110100101100110100110",
    "1101100010110101110110110100101110011010010110100101100110100110",
)
#: Comb-regime slot orders: at n = 7-9 the comb is the smaller build, and
#: these picks of the 48-49-row blocks reach its rows with the fold above.
#: Searched (4590e0c49), not derived: 8 of 81 block pairs reach 2,522 cells
#: at n = 7, 35 of 6,561 quadruples 5,597 at 8; kept picks also reach the
#: old execution formula on every row; retained as coverage, not re-searched.
_COMB_ORDERS = {
    7: (0, 2),
    8: (0, 1, 2, 3),
    9: (0, 1, 2, 3, 4, 5, 2, 3),
}
#: Full-fold blocks fill the slots the fold's extremes need, 49-row ones the rest.
_FULL, _ROWS = (7, 8, 6), (0, 1, 5, 2, 3)


def _full(m: int, *, wide: bool) -> list[bool]:
    """Blocks of an m-level fold that must have a full half for its width (height).

    A node is 3 + max(H0, H1) wide and W0 + W1 + 2 tall: its width needs one
    child's height (the zero child), its height both children's widths, and a
    block's width needs a half with all 32 leaves.
    """
    if m == 6:
        return [wide]
    if wide:
        return _full(m - 1, wide=False) + [False] * (1 << (m - 7))
    return _full(m - 1, wide=True) * 2


def _order(n: int) -> list[int]:
    """Slot blocks reaching the smaller build: the recorded comb-regime
    orders at n = 7-9, else periodic picks, so no aligned neighbours match."""
    if n in _COMB_ORDERS:
        return list(_COMB_ORDERS[n])
    need = [
        a or b for a, b in zip(_full(n, wide=True), _full(n, wide=False), strict=True)
    ]
    return [
        (pool := _FULL if full else _ROWS)[i % len(pool)] for i, full in enumerate(need)
    ]


def legacy_witness(n: int) -> str:
    """Legacy n=6 blocks; at n=7-9 they kept the old fold above the comb.

    From n = 10 the comb outruns the fold (752 rows against 749 at n = 10), and
    the full-fold slots make F the fold.  For every n >= 10 the comb has
    N + sum(r_s) - sum(save(s_i, s_i+1)) rows, N = 2^(n-6) slots: no level above
    a block shares (slots i and i + 2^j differ, 3 and 5 not dividing 2^j; the
    ring pairs slot N - 1 with slot 0), a block's first nodes sit on the zero
    spine so a link sees only its two blocks, r_s = 44-48 and a link saves at
    most 4 (the 72 ordered pairs, run).  So rows >= 41N, the width is 3n + 5,
    and (3n + 5) * 41N >= 27.5T > fold for n >= 13; n = 10-12 are the formula.
    """
    return "".join(_BLOCKS[i] for i in _order(n))


def witness(n: int) -> str:
    """Rudin-Shapiro pair states keep every tested split and reach both boxes."""
    if n == 1:
        return "10"
    if n == 2:
        return "1011"
    return "".join(
        str((row & (row >> 1)).bit_count() % 2 ^ (n % 2)) for row in range(1 << n)
    )


def execution_witness(n: int) -> str:
    """Keep the final pair11; prune only fold-dimension-inactive rectangles."""
    if n < 3:
        return witness(n)
    table = list("".join(str(1 - int(bit)) for bit in witness(n)))
    table[-1] = "1"
    if n in (8, 9):
        block = 1 << 5  # pair slots in a five-level comb base
        quarter = block // 4
        from scripts.docs.resource_evidence import resource_bounds

        area = resource_bounds("Back")["scaling"].formula(n, "")
        deficit = (1 << (n - 1)) - area // (3 * n + 5)
        if n == 8:
            assert deficit == 2 * (quarter - 1)
            # Blocks0/3 keep both required heights; block2 keeps root width.
            cuts = ((block, quarter, "0"), (block + 2 * quarter, quarter, "1"))
        else:
            assert deficit == block - 1 + quarter - 1
            # Blocks0/2 keep heights,4/5 width,7 the final all-one path.
            cuts = (((1 << (n - 6)) - 2) * block, block, "0"), (block, quarter, "1")
        for start, length, bit in cuts:
            table[2 * start : 2 * (start + length)] = bit * (2 * length)
    return "".join(table)
