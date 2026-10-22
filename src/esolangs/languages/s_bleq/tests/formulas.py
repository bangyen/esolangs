"""S*bleq's emitted characters: the packed decoder, n >= 11 (built to n = 21)."""

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
    instruction: 17 named cells, then a target cell each, then the chunks.
    """
    code = 11 * n + 45
    base = 3 * code
    extra = _wide(base + 16, base + 15 + code) + _wide(
        base + 17 + code, base + 17 + code
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


def _chars(n: int, _: str) -> int:
    """P: 175n + 719 + _extra(n), then each chunk's widest decimal.

    Two more once N and COUNT take two digits.
    """
    t = 1 << n
    full, rest = divmod(t, n)
    total = 175 * n + 719 + 2 * (len(str(n)) - 1) + _extra(n)
    total += full * (2 + len(str(t - 1)))
    if rest:
        total += 2 + len(str((1 << rest) - 1))
    return total


FORMULAS = {"scaling": (_chars, True, (11, 12, 13, 19))}
