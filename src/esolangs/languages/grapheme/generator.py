"""Grapheme Boolean program generator: the table is one integer literal.

The literal (int mode, ~0.302 letters an entry) is indexed by Horner's rule
run on the complemented or the direct input bits, and its bit or the
complement is printed.  The smallest of the four packings is taken when it
fits in 3/4 of the table width (sparse and/or/threshold tables); it has no
subtrees to fold or share.

Size:
    O(T) letters; n=10 random 1847: 498 chars, n=16 random 1847: 20,021 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.grapheme.interpreter import (
    DEFAULT_GRAPHEME,
    INTEGER_CONVERSIONS,
    GraphemeDialect,
)
from esolangs.languages.grapheme.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime.memory import format_integer

#: Int-mode digits: ``Z`` is 0 and ``A``-``Y`` are 1 to 25, so the one value
#: with no letter is 6 -- ``F`` closes the mode.  16 with a borrow spells it.
_GRAPHEME_DIGITS = "ZABCDE?GHIJKLMNOPQRSTUVWXY"


def _grapheme_push65(dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> str:
    """Grapheme code pushing 65: ``5 * 13``, or ``FEFFMFS`` between letters."""
    if dialect.integer_conversion == "between_letters":
        return "FEFFMFS"
    return _grapheme_literal(5, dialect) + _grapheme_literal(13, dialect) + "S"


def _grapheme_literal(value: int, dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> str:
    """Return a literal for nonnegative ``value`` without a leading decimal 6."""
    digits = [int(c) for c in format_integer(value)]
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
    # The minimal leading-1 lift: scan the bands [10^j, 2*10^j) upward for
    # the first member of value's residue class. The old fixed target
    # 10^(d+1) overshot it by a fixed ~2 letters a program on every corpus
    # measured (candidate 32). The band at span's digit count is wider
    # than span, so a member always lands there and the scan ends.
    band = 1
    while True:
        base = max(value, band)
        lifted = base + (value - base) % span
        if lifted < 2 * band:
            return lifted
        band *= 10


def grapheme(
    truth_table: str,
    *,
    integer_conversion: str = "between_letters",
) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  The table is one int-mode literal, ~0.302 letters an
    entry, indexed by Horner's rule run on the complemented or direct input
    bits; the answer bit or its complement is printed (the smallest packing).
    """
    return _program(truth_table, integer_conversion=integer_conversion)


def _program(
    truth_table: str,
    *,
    integer_conversion: str = "between_letters",
) -> str:
    """Build the integer lookup, including a one-entry constant table."""
    dialect = GraphemeDialect(integer_conversion)
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    reading = set(used)

    one = _grapheme_literal(1, dialect)
    two = _grapheme_literal(2, dialect)
    # 65 is spelled inline at each read: the key-9 store that amortized it
    # netted 3 chars an essential input against an 11-char block, a share
    # declining toward zero against the 2^n literal (candidate 31).
    read_bit = "W" + _grapheme_push65(dialect) + "B" + "T"
    drop_unread_line = "WM"
    square = "KS"
    shift = "R"
    low_bit = "K" + two + "LR" + two + "SLB"

    # The literal's length follows its magnitude.  Four packings: the index
    # complemented (``2 - bit`` doubles on a 0) or direct (``1 + bit``, the
    # table reversed), the answer stored or negated by ``T``.  Sparse tables
    # (and/or/threshold families) pack to a tiny integer in one of them, 30-62%
    # off at n=10; on random tables the smallest packing is within a bit of the
    # plain one, so a packing is taken only when it fits in 3/4 of the width.
    packings = []
    for direct in (False, True):
        packed = table[::-1] if direct else table
        for negate in (False, True):
            entries = packed.translate(str.maketrans("01", "10")) if negate else packed
            packings.append((int(entries, 2), direct, negate, entries))
    value, direct, negate, entries = min(packings, key=lambda p: (p[0], p[2], p[1]))
    if value.bit_length() * 4 > 3 * len(table):
        direct = negate = False
        entries = table
    double = one + "AS" if direct else two + "BS"
    head = one + "".join(
        square + read_bit + double if i in reading else drop_unread_line
        for i in range(n)
    )
    literal = _grapheme_literal(_grapheme_table(entries), dialect)
    return head + literal + shift + low_bit + ("T" if negate else "") + "Y"


LANGUAGE = Language(
    "Grapheme",
    "grapheme",
    category="stack_based",
    boolean=grapheme,
    dialect=GraphemeDialect,
    dialect_values={"integer_conversion": INTEGER_CONVERSIONS},
    # Each input line is normalized with ord(line[0]) - 65 and then zero is
    # mapped to 1; the second step is what makes 'A' a 1 -- ord('A') - 65 is
    # 0, so the subtraction alone says the opposite.
    contract=BooleanContract(
        alphabet=("%", "A"),
        note="input bits are spelled % and A: a line starting with A is a 1 "
        "and any other line a 0, so a 0/1 line reads as 0 and the program "
        "answers the all-zeros row; esolangs encode spells them",
    ),
    wrap=wrap_chars,
    proof_execution=(execution, True, (3, 5)),
    proof_workspace=(workspace, True, (3, 5)),
)
