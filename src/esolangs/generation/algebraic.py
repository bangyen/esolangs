"""Affine Boolean forms in physical input order."""

from typing import NamedTuple


class AffineForm(NamedTuple):
    """XOR ``bias`` with selected inputs, coefficients in input order."""

    bias: int
    coefficients: tuple[int, ...]


def affine_form(table: str, n: int) -> AffineForm | None:
    """Return the affine form of ``table``, or None, checking every row in O(T).

    Coefficients are per input, first input first; checked against every row.
    """
    bias = int(table[0])
    coefficients = tuple(int(table[1 << (n - i - 1)]) ^ bias for i in range(n))
    expected = [bias]
    for coefficient in reversed(coefficients):
        expected += [value ^ coefficient for value in expected]
    if any(str(value) != bit for value, bit in zip(expected, table, strict=True)):
        return None
    return AffineForm(bias, coefficients)


def parity_bias(table: str) -> int | None:
    """Return full parity's bias for a validated table, or None; no table copy."""
    bias = int(table[0])
    if len(table) > 1 and table[1] == table[0]:
        return None
    if len(table) >= 4 and (table[2] != table[1] or table[3] != table[0]):
        return None
    # Aligned power-of-two words differ only by their word index's parity.
    # Bound the derived word so checking a large table never copies it whole.
    word = "0"
    flip = str.maketrans("01", "10")
    limit = min(len(table), 1024)
    while len(word) < limit:
        word += word.translate(flip)
    words = word, word.translate(flip)
    width = len(word)
    for row in range(0, len(table), width):
        expected = words[bias ^ ((row // width).bit_count() & 1)]
        if not table.startswith(expected[: len(table) - row], row):
            return None
    return bias
