"""Qoibl Boolean program generator: one packed binary literal, divided down.

The whole table is a literal, bit ``k`` holding row ``k``; each input read
squares and multiplies ``power`` so it ends as ``2**index`` (the row index
accumulates in the exponent by Horner's rule), and the printed character is
``'0'`` plus the low bit of ``literal // power``, or ``'1'`` minus it when
the complement packs shorter ([ablations.polarity_flip]).  A top-heavy table
is packed reversed under complemented reads, if shorter ([ablations.negated_reads]).

Size:
    O(T) characters for the literal, O(n) statements;
    n=10 parity: 1,703 chars, n=16 random 1847: 66,539 chars.

Decisions:
    A packed literal has no subtrees to fold or share.  Variables 48 and 49
    hold ``2**bit`` so a read is one operand, and every chain is a pure
    product or a plus-first ``+``/``-``: the page leaves association open,
    and the program is the same under either.
"""

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
)
from esolangs.generation.wrap import balance_score, wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["qoibl"]


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


#: Qoibl instruction mnemonics.  ``we <target> we <value> we`` assigns,
#: ``qe <key> qe`` reads a variable, ``et`` reads the next input character,
#: ``tt <expr> tt`` prints a character, and ``ry <op> ry`` is arithmetic with
#: ``ee``/``ey``/``ye``/``yy`` standing for ``+``/``-``/``*``/``/``.
_ASSIGN, _VAR, _INPUT, _PRINT, _ARITH = "we", "qe", "et", "tt", "ry"
_ADD, _SUB, _MUL, _DIV = "ee", "ey", "ye", "yy"


def _assign(target: str, value: str) -> str:
    """Return the statement assigning ``value`` to variable ``target``."""
    return f"{_ASSIGN} {target} {_ASSIGN} {value} {_ASSIGN}"


def _read_var(key: str) -> str:
    """Return the expression reading the variable named by ``key``."""
    return f"{_VAR} {key} {_VAR}"


def _arith(left: str, op: str, right: str) -> str:
    """Return ``left <op> right`` for ``op`` in ``_ADD``/``_SUB``/``_MUL``/``_DIV``."""
    return f"{left} {_ARITH} {op} {_ARITH} {right}"


def _print(expr: str) -> str:
    """Return the statement printing the character with code ``expr``."""
    return f"{_PRINT} {expr} {_PRINT}"


def qoibl(truth_table: str, width: int | None = None) -> str:
    """Build a Qoibl program; ``truth_table`` has length ``2**n``, MSB first."""
    n = _validate_truth_table(truth_table)
    # An ignored input is read into ``p`` until the first essential read sets
    # it, then into ``row``, which the packed literal overwrites: it costs no
    # variable, and the table is packed over the rest.  It is stored as the
    # bit plus one: a raw 49 beside a live ``p`` broke the workspace bound
    # (17 > 16 bits on ``00111100``).
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        # A constant still needs the first read to set ``p``, so the first input
        # stands as a two-row table; the rest are ignored reads.
        weights = [1] + [0] * (n - 1)
        truth_table = truth_table[0] * 2
    program = min(
        (
            _program(table, weights, negated=negated)
            for table, negated in ((truth_table, False), (truth_table[::-1], True))
        ),
        key=len,
    )
    return _fit(program, width)


def _program(truth_table: str, weights: list[int], *, negated: bool) -> str:
    """Return the unwrapped program; ``negated`` reads each input complemented.

    Complementing every input reverses the row order, so the negated build
    packs the reversed table and an input contributes ``2 / 2**bit``.
    """
    # Variables 0 and 1; variable 2 is the Horner scratch when narrow.
    power = _qoibl_enc(0)
    row = _qoibl_enc(1)
    zero = _qoibl_enc(_ASCII_ZERO)
    two = _qoibl_enc(2)
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))
    # Trailing zeros of the literal are free, trailing ones are not: pack the
    # complement when it is shorter and print '1' minus the bit instead
    # ([ablations.polarity_flip]).
    flipped = ((1 << len(truth_table)) - 1) ^ packed
    flip = flipped.bit_length() < packed.bit_length()
    if flip:
        packed, zero = flipped, _qoibl_enc(_ASCII_ZERO + 1)
    lines = _read_statements(
        weights, power, row, zero, two, packed, flip=flip, negated=negated
    )
    return "\n".join(lines)


def _fit(program: str, width: int | None) -> str:
    """Wrap ``program`` to ``width`` characters, Horner-splitting if needed."""
    lines = program.split("\n")
    if width is None:
        return program
    # Fits as-is: no Horner expansion needed.
    wrapped = _qoibl(program, width)
    if grid_width(wrapped) <= width:
        return wrapped
    limit = max(2, width)
    return _qoibl("\n".join(_horner_lines(lines, limit)), limit)


def _read_statements(
    weights: list[int],
    power: str,
    row: str,
    zero: str,
    two: str,
    packed: int,
    *,
    flip: bool = False,
    negated: bool = False,
) -> list[str]:
    """Emit one assignment per input read, then unpack the row and print it.

    With ``flip`` the literal is the complement and ``zero`` is ``'1'``.
    """
    # Variables 48 and 49 (the digits' codes) hold ``2**bit`` (``2**(1 - bit)``
    # negated), so ``qe et qe`` reads a digit as its factor in one operand.
    # An arithmetic form (``et - 47``) is a chain whose association the page
    # leaves open; here every chain is a pure product or a plus-first +/-.
    low, high = (2, 1) if negated else (1, 2)
    lines = [
        _assign(_qoibl_enc(_ASCII_ZERO), _qoibl_enc(low)),
        _assign(_qoibl_enc(_ASCII_ZERO + 1), _qoibl_enc(high)),
    ]
    two_to_bit = drain = _read_var(_INPUT)
    counted = False
    for weight in weights:
        if not weight:
            # An ignored input only needs draining; ``row`` is overwritten by
            # the packed literal below, and before the first essential read
            # ``power`` is overwritten by it instead.
            lines.append(_assign(row if counted else power, drain))
        elif counted:
            # ``power = power * (power * 2**bit)``: squaring doubles the
            # exponent and the multiply appends the new bit -- Horner's rule
            # on the exponent, so after the k-th essential read ``power`` is
            # ``2**index``.  Essential, not an optimisation: with only
            # + - * / available, the power must reach ``2**index`` by
            # squaring for the packed literal's division below.
            lines.append(
                _assign(
                    power,
                    _arith(
                        _read_var(power),
                        _MUL,
                        _arith(_read_var(power), _MUL, two_to_bit),
                    ),
                )
            )
        else:
            lines.append(_assign(power, two_to_bit))
            counted = True
    # ``row = packed // power``: shift the table right by the row index.
    lines.append(_assign(row, _arith(_qoibl_enc(packed), _DIV, _read_var(power))))
    # ``power`` is dead now: reuse it for ``2 * (row // 2)``, one operator per
    # statement.  The print chains ``row + zero - half`` and ``zero + half -
    # row`` are +/- with the plus first, so left and right association agree
    # (the page fixes neither).
    lines.append(_assign(power, _arith(_read_var(row), _DIV, two)))
    lines.append(_assign(power, _arith(_read_var(power), _MUL, two)))
    row_read, half = _read_var(row), _read_var(power)
    first, second, third = (zero, half, row_read) if flip else (row_read, zero, half)
    lines.append(_print(_arith(first, _ADD, _arith(second, _SUB, third))))
    return lines


def _horner_lines(lines: list[str], limit: int) -> list[str]:
    """Expand each statement's over-long literal into binary Horner steps.

    Each statement has one long literal.  Splitting it into chunks evaluates
    ``((c0 * 2**len(c1) + c1) * 2**len(c2) + c2) ...`` into spare variable 2.
    The multiply and the add stay separate statements: one ``ry`` chain
    would associate to the right (``a * (b + c)``), so the two operations
    cannot share a statement.
    """
    scratch = _qoibl_enc(2)
    output: list[str] = []
    for line in lines:
        tokens = line.split()
        for at, token in enumerate(tokens):
            if len(token) <= limit:
                continue
            chunks = [token[i : i + limit - 1] for i in range(0, len(token), limit - 1)]
            output.append(_assign(scratch, chunks[0]))
            for chunk in chunks[1:]:
                factor = _qoibl_enc(1 << len(chunk))
                output.append(
                    _assign(scratch, _arith(_read_var(scratch), _MUL, factor))
                )
                output.append(_assign(scratch, _arith(_read_var(scratch), _ADD, chunk)))
            tokens[at] = _read_var(scratch)
        output.append(" ".join(tokens))
    return output


def _qoibl(program: str, width: int) -> str:
    """Wrap Qoibl across statements.

    A newline between tokens is whitespace (measured), so rows fill instead
    of each statement taking its own.
    """
    return wrap_space_delimited(program, width)


def balance_qoibl(table: str, default: str) -> str:
    """Return the best of three wraps at closed-form widths.

    With ``s`` default characters and a ``lit``-character literal, a plain
    wrap is square at ``sqrt(2 s)`` (a row is twice a column).  Past n=5 the
    literal splits into Horner chunks, each adding overhead, which fits
    ``w**2 = 2 s + a lit`` with ``a`` between 5.2 and 6.5 for n=6..11; the
    three ``a`` values 0, 3 and 6 stay within a few percent of the best
    width on random tables of 8-2048 rows.
    """
    literal = max(map(len, default.split()))
    widths = [(2 * len(default) + a * literal) ** 0.5 for a in (0, 3, 6)]
    return min((qoibl(table, round(width)) for width in widths), key=balance_score)


LANGUAGE = Language(
    "Qoibl",
    "qoibl",
    category="register_based",
    boolean=qoibl,
    # Not a tree: the table is one binary literal the reads divide down.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=balance_qoibl,
)
