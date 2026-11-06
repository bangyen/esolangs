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
    for row, bit in enumerate(table):
        if bit != "01"[(row.bit_count() & 1) ^ bias]:
            return None
    return bias
