"""Forbin's emitted characters: reads, shift register, a tree of blocks."""


def _chars_of_names(m: int) -> int:
    """Characters of the first m identifiers: 52 one-letter, then two-letter."""
    return m + max(0, m - 52)


def _length(k: int) -> int:
    return 1 if k < 52 else 2


def _chars(n: int, _: str) -> int:
    """N: the b = 7 build, main, reads, shift register, 2^(n-7) distinct blocks.

    A table's size is this minus what constants, repeats and ignored inputs
    drop: a nonconstant leaf costs 7 + len(table) + 2 * block, a collapsed
    constant span a call (about 12) plus one of two 23-character printers,
    and a subtree used k times a definition (at most 6 over its body) and k
    calls, against the k - 1 leaves it omits.
    """
    h = max(n - 7, 0)
    low = n - h
    block = 1 << low
    # Name indexes, in order of first use: junk, n bits, table, then the cells.
    junk, table, first = 0, n + 1, n + 2

    def cells(a: int, b: int) -> int:
        return _chars_of_names(first + b) - _chars_of_names(first + a)

    reads = (
        7 * n * _length(junk)
        + _chars_of_names(n + 1)
        - _chars_of_names(1)
        + (8 * n - 1)
        + 8
    )
    register = _length(table) + 1 + cells(0, block) + (block - 1) + 1
    live = block
    for level in range(h, n):
        half = live // 2
        register += (
            9
            + _length(level + 1)
            + 1
            + cells(0, half)
            + half
            - 1
            + 1
            + cells(half, live)
            + (live - half)
            - 1
            + 1
        )
        live = half
    register += 18 + _length(first) + 1 + 1
    leaf = 7 + _length(table) + 2 * block
    tree = sum((1 << lv) * (11 + _length(lv + 1)) for lv in range(h)) + (1 << h) * leaf
    lines = 4 + (1 << (h + 2)) - 2
    return 5 + reads + register + tree + 1 + (lines - 1)


#: The b = 7 build's size; the race (3 <= b <= 7) reaches it only where 7 wins.
FORMULAS = {
    "scaling": (
        _chars,
        frozenset({2, 3, 12, 13}),
        (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13),
    )
}
