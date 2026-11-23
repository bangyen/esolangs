"""Boolean row boundaries, counts and popcount lookup profiles."""

from collections.abc import Iterator
from itertools import accumulate

_PREFIX_MARKS = {
    value: bytes(int(code == ord(value)) for code in range(256)) for value in "01"
}
_BLOCK_BITS = 10
_BLOCK_WEIGHTS = bytes(row.bit_count() for row in range(1 << _BLOCK_BITS))
_PACK_CELLS_PER_BLOCK = 1 << 16


def constant_output(table: str) -> str | None:
    """Return the constant output of a validated nonempty table, or None."""
    return table[0] if table.count(table[0]) == len(table) else None


def change_points(table: str) -> list[int]:
    """Return ascending row boundaries whose adjacent outputs differ."""
    return [row for row in range(1, len(table)) if table[row] != table[row - 1]]


def prefix_counts(table: str, value: str) -> list[int]:
    """Return matching-entry counts for every prefix, including the empty one."""
    return list(prefix_totals(table, value))


def prefix_totals(table: str, value: str) -> Iterator[int]:
    """Yield matching-entry counts, allowing callers to choose their storage."""
    marks = _PREFIX_MARKS.get(value)
    if marks is not None and str.isascii(table):
        return accumulate(str.encode(table, "ascii").translate(marks), initial=0)
    return accumulate((int(entry == value) for entry in table), initial=0)


def symmetric_outputs(table: str, n: int) -> str | None:
    """Return outputs by popcount for a validated n-input symmetric table."""
    outputs = "".join(table[(1 << count) - 1] for count in range(n + 1))
    prefix = table if n <= _BLOCK_BITS else table[:16]
    if any(bit != outputs[row.bit_count()] for row, bit in enumerate(prefix)):
        return None
    if n <= _BLOCK_BITS:
        return outputs

    # Blocks with the same high-input popcount have identical output words.
    profile = outputs.encode("ascii")
    words: dict[int, str] = {}
    for block, start in enumerate(range(0, len(table), len(_BLOCK_WEIGHTS))):
        weight = block.bit_count()
        word = words.get(weight)
        if word is None:
            output_by_weight = profile[weight : weight + _BLOCK_BITS + 1]
            word = _BLOCK_WEIGHTS.translate(output_by_weight.ljust(256, b"\0")).decode(
                "ascii"
            )
            words[weight] = word
        if not table.startswith(word, start):
            return None
    return outputs


def packed_cells(
    table: str, bits: int, *, offset: int = 0, complement: bool = False
) -> str:
    """Pack consecutive bits little-endian; the last cell uses only its entries."""
    if bits <= 0:
        raise ValueError("bits must be positive")
    prefix = ""
    if (
        len(table) >= 1024
        and bits <= 8
        and type(offset) is int
        and 0 <= offset <= 256 - (1 << bits)
        and str.count(table, "0") + str.count(table, "1") == len(table)
    ):
        complete = len(table) // bits * bits
        marks = _PREFIX_MARKS["0" if complement else "1"]
        shift = bytes((value + offset) & 255 for value in range(256))
        block = bits * _PACK_CELLS_PER_BLOCK
        prefix = "".join(
            _packed_block(table[start : min(start + block, complete)], bits, marks)
            .translate(shift)
            .decode("latin-1")
            for start in range(0, complete, block)
        )
        table = table[complete:]
    if complement:
        table = table.translate(str.maketrans("01", "10"))
    return prefix + "".join(
        chr(offset + int(table[start : start + bits][::-1], 2))
        for start in range(0, len(table), bits)
    )


def _packed_block(table: str, bits: int, marks: bytes) -> bytes:
    flags = str.encode(table, "ascii").translate(marks)
    # Each column contributes one bit per byte, so addition never carries.
    words = sum(
        int.from_bytes(flags[bit::bits], "little") << bit for bit in range(bits)
    )
    return words.to_bytes(len(table) // bits, "little")


def exceptional_row(table: str) -> tuple[int, bool] | None:
    """Return the unique one or zero row, preferring a one, and whether inverted."""
    if table.count("1") == 1:
        return table.index("1"), False
    if table.count("0") == 1:
        return table.index("0"), True
    return None


def majority_bias(table: str, n: int) -> bool | None:
    """Return the inversion of strict majority, or None for another table."""
    invert = table[0] == "1"
    # Keep scalar rejection for the dense tables that fail at the first rows.
    prefix = table if n <= _BLOCK_BITS else table[:16]
    if any(
        (bit == "1") != ((row.bit_count() > n // 2) ^ invert)
        for row, bit in enumerate(prefix)
    ):
        return None
    if n <= _BLOCK_BITS:
        return invert
    zero, one = "10" if invert else "01"
    cutoff = n // 2 + 1
    expected = zero * cutoff + one * (n + 1 - cutoff)
    return invert if symmetric_outputs(table, n) == expected else None


def near_unanimity(table: str, n: int) -> bool:
    """Whether all but at most one input must be one, or its negation."""
    bit = "1" if table[0] == "0" else "0"
    return (
        n >= 2
        and table.count(bit) == n + 1
        and table[-1] == bit
        and all(table[len(table) - 1 - (1 << i)] == bit for i in range(n))
    )
