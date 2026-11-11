"""S*bleq's emitted characters: the packed decoder, n >= 11 (built to n = 25)."""

#: Cell-naming operands by cell index: per input read, and in the decoder.
_READ_CELLS = {3: 1, 5: 3, 6: 5, 7: 4, 8: 8}
_DECODER_CELLS = {
    0: 25, 1: 5, 2: 5, 4: 1, 5: 2, 8: 16, 9: 3, 10: 4, 11: 10, 12: 6,
    13: 4, 14: 4, 15: 2,
}  # fmt: skip
#: Decoder branches: (instruction offset, offset of the label it jumps to).
_BRANCHES = (
    (0, 13), (1, 2), (5, 7), (6, 0), (12, 0), (22, 32), (23, 24),
    (25, 30), (26, 27), (29, 22), (31, 32), (33, 40), (34, 35), (39, 20),
)  # fmt: skip


def _wide(first: int, last: int, step: int = 1) -> int:
    """Digits past three over first, first + step, ..., last."""
    total = 0
    for floor in (10**3, 10**4, 10**5, 10**6):
        start = first + max(0, -(-(floor - first) // step)) * step
        total += max(0, (last - start) // step + 1)
    return total


def _extra(n: int) -> int:
    """Digits the address cells gain at four and more digits.

    Instructions: 11 a read and 45 in the decoder.  The cells start at 3 a
    instruction: 16 named cells, then a target cell each, then the chunks.
    """
    code = 11 * n + 45
    base = 3 * code
    extra = _wide(base + 16, base + 15 + code) + _wide(
        base + 16 + code, base + 16 + code
    )
    for index, count in _READ_CELLS.items():
        extra += n * count * _wide(base + index, base + index)
    for index, count in _DECODER_CELLS.items():
        extra += count * _wide(base + index, base + index)
    extra += _wide(3, 3 * (code - 1), 3)
    for offset, label in _BRANCHES:
        extra += _wide(3 * (11 * n + label), 3 * (11 * n + label))
        extra -= _wide(3 * (11 * n + offset + 1), 3 * (11 * n + offset + 1))
    return extra + _wide(3 * (11 * n + 14) + 1, 3 * (11 * n + 14) + 1)


def _distinct(n: int, d: int) -> int:
    """Most distinct tested subtables at depth d: differing halves, at most 2^d."""
    m = n - d
    return min(2**d, 2 ** (2**m) - 2 ** (2 ** (m - 1)))


def tree_chars(n: int, _: str = "") -> int:
    """Bound on the hoisted tree route: n + 2K + 3 instructions, K distinct tests.

    Compaction only removes cells and lowers addresses; this original
    envelope still bounds either polarity. Each test is placed once; its
    zero edge falls through or jumps (one
    instruction), its one edge is a data cell; two leaf pairs.  Every
    instruction cell is at most the widest data address.
    """
    k = sum(_distinct(n, d) for d in range(n))
    ins, tg = n + 2 * k + 3, k + 2
    cb = 13 + 2 * n + tg
    pre = 9 + 8 + len(str(cb))
    data = 9 + 3 + n + n * len(str(cb + 3 * n)) + tg * len(str(cb + 3 * ins))
    return pre + data + 4 + 2 * n + tg + 3 * ins * (len(str(cb)) + 1)


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price only the routes admitted at this arity."""
    return {"A": _extra(n) if n >= 5 else 0, "Q": tree_chars(n) if n <= 10 else 0}


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Measure signed initial memory and its cell count."""
    cells = [int(word) for word in program.split()]
    bits = sum(max(1, value.bit_length()) + (value < 0) for value in cells)
    return {"B": bits, "R": len(cells)}
