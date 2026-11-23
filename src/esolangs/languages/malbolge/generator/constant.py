"""Read all input bytes, then build and print a constant accumulator."""

from .isa import _char_for, _program, _render


def _constant_program(inputs: int, bit: int) -> str:
    """Return straight-line code printing ``bit`` and reading every input."""
    # The initial j separates C and D by its source character. Rotate 39
    # to 13, then p over 80 gives four low 2-trits and six high 1-trits.
    # A final p over 69 or 71 gives ASCII 48 or 49, independent of input.
    offset = _char_for("j", 0)
    rotated, merged, final = 39, 80, 69 + 2 * bit
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
