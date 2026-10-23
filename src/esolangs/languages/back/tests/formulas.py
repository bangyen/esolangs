"""Back's emitted cells: the comb, then the smaller of it and the fold."""


def _comb(n: int) -> int:
    """3n + 5 load columns by max(6n - 1, 3T/4 + 1) rows (Rudin-Shapiro's tree)."""
    return (3 * n + 5) * max(6 * n - 1, 3 * (1 << n) // 4 + 1)


def _fold(n: int) -> int:
    """The H-tree fold's rectangle under the load row; parity reaches it.

    Five-level combs at the leaves; a node is 3 + max(H0, H1) wide and
    W0 + W1 + 2 tall, children transposed.
    """
    width, height, entry = 17, 32, 0  # the five-level comb, 3 * 5 + 2 wide
    for _ in range(6, n + 1):
        width, height, entry = 3 + height, 2 * width + 2, width + 1
    return (1 + width) * (max(0, 4 * n - entry) + height)


#: Annealed n = 6 blocks: 0-5 have 48-49 comb rows, 6-8 are full-fold (45-47).
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
#: n = 9 stays in the comb regime: eight slots of the 49-row blocks.
_COMB_ORDER = (0, 1, 2, 3, 4, 5, 2, 3)
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
    """Slot blocks reaching the fold: periodic picks, so no aligned neighbours match."""
    if n == 9:
        return list(_COMB_ORDER)
    need = [
        a or b for a, b in zip(_full(n, wide=True), _full(n, wide=False), strict=True)
    ]
    return [
        (pool := _FULL if full else _ROWS)[i % len(pool)] for i, full in enumerate(need)
    ]


def witness(n: int) -> str:
    """Concatenated n = 6 blocks: n = 9 keeps the fold above the comb's 12,320.

    From n = 10 the comb (>= 752 rows at n = 10, 1,503 at 11) outruns the fold
    (35 x 749 / 38 x 1,412 rows), and the full-fold slots make F the fold.
    """
    return "".join(_BLOCKS[i] for i in _order(n))


def _cells(n: int, _: str) -> int:
    """F: the comb to n = 5, then min(comb, fold), under 27.5T; reached to n = 16."""
    return _comb(n) if n <= 5 else min(_comb(n), _fold(n))


FORMULAS = {
    "scaling": (
        _cells,
        frozenset(range(3, 17)),
        (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16),
    )
}
