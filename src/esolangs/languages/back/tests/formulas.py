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


#: Annealed 64-bit n = 6 blocks (49 rows, 34 wide) and five full-fold ones (47 rows).
_BLOCKS = (
    "0111010001010010111000011010000111001010011110000100101000100010",
    "0111010010100100010111011110010111001010010010100111101001010010",
    "0101101001011010011101011010010100011101111011000101101000110101",
    "1010010111100101101001011010010110001010111000011110010100100101",
    "1010000100101100100010101100010100011010110010000101110111000111",
    "1000011110100011101011001010111001010001001000010011010111011010",
    "0101100001000101101110001010011101011010010110100110010110011010",
    "1101110100110101110110110100101110011010010110100101100110100110",
    "0101100001000100101110001010011101011010010110100110010110011010",
    "0101110001000101101110001011011101011010010110100110010110011010",
    "1101100010110101110110110100101110011010010110100101100110100110",
)
#: Slots per n, hill-climbed on min(width * rows, fold) to reach the fold.
_ORDERS = {
    9: (0, 1, 2, 3, 4, 5, 2, 3),
    10: (2, 1, 6, 7, 1, 4, 2, 0, 8, 9, 1, 5, 6, 10, 9, 0),
    11: (
        6,
        6,
        0,
        0,
        1,
        1,
        8,
        8,
        0,
        2,
        5,
        2,
        4,
        5,
        1,
        2,
        4,
        2,
        5,
        2,
        5,
        1,
        0,
        1,
        8,
        8,
        0,
        0,
        9,
        8,
        1,
        2,
    ),
}


def witness(n: int) -> str:
    """Concatenated n = 6 blocks: n = 9 keeps the fold above the comb's 12,320.

    Full-fold blocks give the fold 155 x 168 at n = 10 and 171 x 312 at n = 11,
    and 35 x 749 / 38 x 1521 comb rows cover them: F is the fold.
    """
    return "".join(_BLOCKS[i] for i in _ORDERS[n])


def _cells(n: int, _: str) -> int:
    """F: the comb to n = 5, then min(comb, fold), under 27.5T; reached to n = 11."""
    return _comb(n) if n <= 5 else min(_comb(n), _fold(n))


FORMULAS = {"scaling": (_cells, frozenset(range(3, 12)), (3, 4, 5, 6, 7, 8, 9, 10, 11))}
