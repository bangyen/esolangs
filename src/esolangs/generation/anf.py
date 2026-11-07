"""Packed algebraic normal forms in truth-table row order.

Coefficient i multiplies the input variables whose row-index bits occur in i.
The transform is independent of target syntax, reads, factoring and layout.
"""

from esolangs.generation.helpers import _validate_shape


def word_width(n: int) -> int:
    """Return a power-of-two packing width >=2 and Theta(n), for n>=1."""
    return max(2, 1 << (n.bit_length() - 1))


def anf_coefficients(truth_table: str) -> list[int]:
    """Return row-indexed ANF coefficients, allowing a nullary reduced table.

    Pack Theta(log T) coefficients per word for O(T) word-RAM work.
    """
    n = _validate_shape(truth_table)
    if n == 0:
        return [int(truth_table)]
    if n == 2:
        a, b, c, d = map(int, truth_table)
        return [a, a ^ b, a ^ c, a ^ b ^ c ^ d]
    width = word_width(n)
    words = [
        int(truth_table[start : start + width][::-1], 2)
        for start in range(0, len(truth_table), width)
    ]
    stride = 1
    while stride < width:
        high = int(("1" * stride + "0" * stride) * (width // (2 * stride)), 2)
        words = [value ^ ((value << stride) & high) for value in words]
        stride *= 2
    stride = 1
    while stride < len(words):
        for start in range(0, len(words), 2 * stride):
            for offset in range(start, start + stride):
                words[offset + stride] ^= words[offset]
        stride *= 2
    return [(value >> bit) & 1 for value in words for bit in range(width)]
