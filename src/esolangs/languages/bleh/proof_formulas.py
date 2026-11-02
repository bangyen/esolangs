"""Command and written-state bounds for the short read alias."""


def workspace(n: int, _: str) -> int:
    """Heap cells, control/continuation peaks, fresh address and input cursor."""
    bl = int.bit_length
    # Node ids <2^(n+1), and 52>2^5. Constant names add a level suffix.
    width = max((n + 5) // 5, 1 + len(str(n - 1)))
    control = max(128, 8 * width + 16, 8 * width + bl(n) + 1)
    kont = max(105, 8 * width + 17, 8 * width + 2 * bl(n) + 1)
    heap = 64 * n + 1 + sum(map(bl, range(1, n)))
    # A final statement-read tail uses at least one fewer heap cell;
    # the flat constant's 16n+256+max(1,bl(n-1))+bl(n) is also below this.
    return heap + control + kont + 2 * bl(n)


def execution(n: int, program: str) -> int:
    """Alias calls add two transitions per read; a constant has one flat block."""
    if "main:={" in program:
        return 5 * n + 6
    return 10 * n + 5
