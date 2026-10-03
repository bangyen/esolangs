"""Boolean program generator for Grapheme."""

from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at

#: Int-mode digits: ``Z`` is 0 and ``A``-``Y`` are 1 to 25, so the one value
#: with no letter is 6 -- ``F`` closes the mode.  16 with a borrow spells it.
_GRAPHEME_DIGITS = "ZABCDE?GHIJKLMNOPQRSTUVWXY"

#: Holds 65.  A literal is worth ten times its digits, so ``9`` names key 90.
_GRAPHEME_CONST = 9


def _grapheme_push65() -> str:
    """Grapheme code pushing 65 (``ord('A')``), spelled ``70 - (50 / 10)``."""
    return "FAF" + "FEF" + "R" + "FGF" + "B"


def _grapheme_literal(value: int) -> str:
    """Return an int-mode literal pushing ``10 * value``, for ``value >= 0``."""
    digits = [int(c) for c in str(value)]
    if digits[0] == 6:
        raise AssertionError("a leading 6 has nothing to borrow from")
    for at in range(len(digits) - 1, 0, -1):
        if digits[at] != 6:
            continue
        digits[at] = 16
        lend = at - 1
        while digits[lend] == 0:
            digits[lend] = 9
            lend -= 1
        digits[lend] -= 1
    return "F" + "".join(_GRAPHEME_DIGITS[digit] for digit in digits) + "F"


def _grapheme_table(table: str) -> int:
    """Pack entry ``i`` at bit ``len(table) - 1 - i``, lifted to lead with 1."""
    span = 1 << len(table)
    value = int(table, 2)
    lift: int = 10 ** (len(str(span)) + 1)
    return value + -(-(lift - value) // span) * span


def grapheme(truth_table: str) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  The table is one int-mode literal, ~0.302 letters an
    entry, indexed by Horner's rule run on the complemented input bits.
    """
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    reading = set(used)

    ten = _grapheme_literal(1)
    one = ten * 2 + "R"
    two = ten + _grapheme_literal(2) + "R"
    store65 = _grapheme_push65() + _grapheme_literal(_GRAPHEME_CONST) + "C"
    read_bit = "W" + _grapheme_literal(_GRAPHEME_CONST) + "D" + "B" + "T"
    drop_unread_line = "WM"
    square = "KS"
    double_unless_set = two + "B" + "S"
    match_the_literal_scale = ten + "S"
    shift = "R"
    low_bit = "K" + two + "LR" + two + "SLB"

    pieces = [store65, one]
    for input_index in range(n):
        if input_index in reading:
            pieces.append(square + read_bit + double_unless_set)
        else:
            pieces.append(drop_unread_line)
    pieces.append(match_the_literal_scale)
    pieces.append(_grapheme_literal(_grapheme_table(table)))
    pieces.append(shift + low_bit + "Y")
    return "".join(pieces)
