"""Affine Boolean forms in physical input order."""

from typing import NamedTuple

_BLOCK_BITS = 10
_FLIP_BITS = str.maketrans("01", "10")


class AffineForm(NamedTuple):
    """XOR ``bias`` with selected inputs, coefficients in input order."""

    bias: int
    coefficients: tuple[int, ...]


def affine_form(table: str, n: int) -> AffineForm | None:
    """Return the affine form of a validated table, checking every row in O(T).

    Coefficients are in input order.
    """
    bias = int(table[0])
    coefficients = tuple(int(table[1 << (n - i - 1)]) ^ bias for i in range(n))
    split = max(0, n - _BLOCK_BITS)
    word = str(bias)
    for coefficient in reversed(coefficients[split:]):
        word += word.translate(_FLIP_BITS) if coefficient else word
    words = word, word.translate(_FLIP_BITS)
    # Within each block the low inputs run through the same rows. Selected
    # high inputs contribute only a common XOR, so compare one of two words.
    mask = 0
    for coefficient in coefficients[:split]:
        mask = (mask << 1) | coefficient
    for block, start in enumerate(range(0, len(table), len(word))):
        if not table.startswith(words[(block & mask).bit_count() & 1], start):
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
    limit = min(len(table), 1 << _BLOCK_BITS)
    while len(word) < limit:
        word += word.translate(_FLIP_BITS)
    words = word, word.translate(_FLIP_BITS)
    width = len(word)
    for row in range(0, len(table), width):
        expected = words[bias ^ ((row // width).bit_count() & 1)]
        if not table.startswith(expected[: len(table) - row], row):
            return None
    return bias
