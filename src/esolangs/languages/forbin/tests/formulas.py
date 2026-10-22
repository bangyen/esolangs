"""Forbin's emitted characters: reads, shift register, a tree of blocks."""


def _chars_of_names(m: int) -> int:
    """Characters of the first m identifiers: 52 one-letter, then two-letter."""
    return m + max(0, m - 52)


def _length(k: int) -> int:
    return 1 if k < 52 else 2


def _chars(n: int, _: str) -> int:
    """N: main, reads, shift register and tree text, 2^(n-7) distinct blocks."""
    h = max(n - 7, 0)
    low = n - h
    block = 1 << low
    table, junk, first = n, n + 3, n + 4  # name indexes; cells follow

    def cells(a: int, b: int) -> int:
        return _chars_of_names(first + b) - _chars_of_names(first + a)

    reads = 7 * n * _length(junk) + _chars_of_names(n) + (8 * n - 1) + 8
    register = _length(table) + 1 + cells(0, block) + (block - 1) + 1
    live = block
    for level in range(h, n):
        half = live // 2
        register += (
            9
            + _length(level)
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
    tree = sum((1 << lv) * (11 + _length(lv)) for lv in range(h)) + (1 << h) * leaf
    lines = 4 + (1 << (h + 2)) - 2
    return 5 + reads + register + tree + 1 + (lines - 1)


FORMULAS = {"scaling": (_chars, True, (3, 7, 8, 9))}
