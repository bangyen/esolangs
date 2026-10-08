"""Boolean program generator for Grapheme.

The table is one integer literal, so it has no subtrees to fold or share.
"""

from esolangs._grapheme import DEFAULT_GRAPHEME, GraphemeDialect
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at

#: Int-mode digits: ``Z`` is 0 and ``A``-``Y`` are 1 to 25, so the one value
#: with no letter is 6 -- ``F`` closes the mode.  16 with a borrow spells it.
_GRAPHEME_DIGITS = "ZABCDE?GHIJKLMNOPQRSTUVWXY"

#: Holds 65 at integer key 9.
_GRAPHEME_CONST = 9


def _grapheme_push65(dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> str:
    """Grapheme code pushing 65: ``5 * 13``, or ``FEFFMFS`` between letters."""
    if dialect.integer_conversion == "between_letters":
        return "FEFFMFS"
    return _grapheme_literal(5, dialect) + _grapheme_literal(13, dialect) + "S"


def _grapheme_literal(value: int, dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> str:
    """Return a literal for nonnegative ``value`` without a leading decimal 6."""
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
    source = "F" + "".join(_GRAPHEME_DIGITS[digit] for digit in digits) + "F"
    # Prose conversion yields 10*value; FAF supplies its divisor below it.
    return (
        "FAF" + source + "R"
        if dialect.integer_conversion == "after_each_letter"
        else source
    )


def _grapheme_table(table: str) -> int:
    """Pack entry ``i`` at bit ``len(table) - 1 - i``, lifted to lead with 1."""
    span = 1 << len(table)
    value = int(table, 2)
    lift: int = 10 ** (len(str(span)) + 1)
    return value + -(-(lift - value) // span) * span


def grapheme(
    truth_table: str,
    *,
    integer_conversion: str = "between_letters",
) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  The table is one int-mode literal, ~0.302 letters an
    entry, indexed by Horner's rule run on the complemented input bits.
    """
    dialect = GraphemeDialect(integer_conversion)
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    reading = set(used)

    one = _grapheme_literal(1, dialect)
    two = _grapheme_literal(2, dialect)
    store65 = (
        _grapheme_push65(dialect) + _grapheme_literal(_GRAPHEME_CONST, dialect) + "C"
    )
    read_bit = "W" + _grapheme_literal(_GRAPHEME_CONST, dialect) + "D" + "B" + "T"
    drop_unread_line = "WM"
    square = "KS"
    double_unless_set = two + "B" + "S"
    shift = "R"
    low_bit = "K" + two + "LR" + two + "SLB"

    pieces = [store65, one]
    for input_index in range(n):
        if input_index in reading:
            pieces.append(square + read_bit + double_unless_set)
        else:
            pieces.append(drop_unread_line)
    pieces.append(_grapheme_literal(_grapheme_table(table), dialect))
    pieces.append(shift + low_bit + "Y")
    return "".join(pieces)


LANGUAGE = Language(
    "Grapheme",
    "stack_based.grapheme",
    boolean=grapheme,
    contract=BooleanContract(
        alphabet=("%", "A"),
        note="Grapheme's generator normalizes each input line with "
        "ord(line[0]) - 65 and then maps zero to 1, so its input "
        "bits are spelled % and A: 'A' is a 1 and every other "
        "first character is a 0, which means a 0/1 line reads as 0 "
        "and the program answers the all-zeros row. The second "
        "step is not optional prose -- ord('A') - 65 is 0, so the "
        "subtraction alone says the opposite",
    ),
)
