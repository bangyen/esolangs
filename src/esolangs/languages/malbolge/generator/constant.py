"""Read all input bytes, then build and print a constant accumulator."""

from .isa import _ONE_OPERAND, _ZERO_OPERAND, _char_for, _program, _render


def _constant_program(inputs: int, bit: int) -> str:
    """Return straight-line code printing ``bit`` and reading every input."""
    # Both ASCII output bytes fit in four trits. Crazy merges a 2 over
    # each of those trits when A is binary there, and makes a 1 above
    # them when A and the operand both have zero trits.
    output_trits = 4
    merged = 3**output_trits - 1
    # Halve the mask for a printable binary-trit seed and clear its
    # units trit so rotation puts a zero at the top.
    rotated = merged // 2 // 3 * 3
    final = (_ZERO_OPERAND, _ONE_OPERAND)[bit]
    offset = _char_for("j", 0)
    # The operand bytes decode as i, p, p at these addresses. All are
    # beyond the halt, and the first is past any of the seventeen reads.
    start = _char_for("i", 0) - rotated
    middle = _char_for("p", 0) - merged + 94
    end = _char_for("p", 0) - final + 94
    code = dict(enumerate("j" + "/" * inputs))
    code[start - offset] = "*"
    code[middle - offset] = "p"
    code.update(enumerate("p<v", end - offset))
    words = _program(code) | {start: rotated, middle: merged, end: final}
    return _render(words, end + 1)
