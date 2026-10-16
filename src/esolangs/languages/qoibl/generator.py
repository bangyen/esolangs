"""Qoibl Boolean program generator: one packed binary literal, divided down.

The whole table is a literal, bit ``k`` holding row ``k``; each input read
squares and multiplies ``power`` so it ends as ``2**index`` (the row index
accumulates in the exponent by Horner's rule), and the printed character is
``'0'`` plus the low bit of ``literal // power``.

Size:
    O(T) characters for the literal, O(n) statements;
    n=10 parity: 1,728 chars, n=16 random 1847: 66,624 chars.

Decisions:
    A packed literal has no subtrees to fold or share.
"""

from math import isqrt

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

#: Narrowest chunk limit: the three-token prefix needs a row of its own.
_MIN_CHUNK_LIMIT = 6


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
    # Variables 0 and 1; variable 2 is the Horner scratch when narrow.
    power = _qoibl_enc(0)
    row = _qoibl_enc(1)
    zero = _qoibl_enc(_ASCII_ZERO)
    two = _qoibl_enc(2)
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))
    lines = _read_statements(weights, power, row, zero, two, packed)
    program = "\n".join(lines)
    if width is None or width <= 0:
        return program
    # Fits as-is: no Horner expansion needed.
    wrapped = _qoibl(program, width)
    if grid_width(wrapped) <= width:
        return wrapped
    limit = max(2, width)
    return _qoibl("\n".join(_horner_lines(lines, limit)), limit)


def _read_statements(
    weights: list[int], power: str, row: str, zero: str, two: str, packed: int
) -> list[str]:
    """Emit one assignment per input read, then unpack the row and print it."""
    # The input digit is 48 or 49, so minus 47 it is 2**bit: multiplying it
    # in appends the new bit to the row index accumulating in the exponent.
    two_to_bit = _arith(_INPUT, _SUB, _qoibl_enc(_ASCII_ZERO - 1))
    lines = []
    counted = False
    for weight in weights:
        if not weight:
            # An ignored input only needs draining; ``row`` is overwritten by
            # the packed literal below, and before the first essential read
            # ``power`` is overwritten by it instead.
            lines.append(_assign(row if counted else power, two_to_bit))
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
    # Print ``'0' + (row mod 2)``: the selected row's bit as a character.
    lines.append(
        _print(
            _arith(
                _read_var(row),
                _ADD,
                _arith(
                    zero, _SUB, _arith(two, _MUL, _arith(_read_var(row), _DIV, two))
                ),
            )
        )
    )
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
    """Wrap Qoibl, folding each of its lines but keeping them apart.

    A newline between tokens is whitespace (measured), so each statement
    line folds on its own; joining first would fold across statements.
    """
    return "\n".join(wrap_space_delimited(line, width) for line in program.split("\n"))


#: Statement-wrapping offsets from ``sqrt(2 * chars)`` and chunk-width offsets
#: from :func:`_chunk_width`.  Offsets are the set that matched the swept
#: side exactly at n<=6 and stayed within 2% at n=7..11 (10 random tables
#: each; the test oracle holds the sweep).
_FIT_OFFSETS = (0, 2, 4)
_CHUNK_OFFSETS = (-2, 1, 4, 7)


def _chunk_width(statements: int, literal: int) -> int:
    """The chunk limit where a Horner-chunked program renders square.

    A full chunk costs two statements of three rows, so ``rows = 6 * literal
    / w + r`` with ``r`` one less than the statement count (the wrapped rest),
    and the side is least at ``w == 2 * rows``: ``w = r + sqrt(r^2 + 12
    literal)``.  Rows step with the chunk count, so one width misses by up to 7%.
    """
    rest = statements - 1
    return rest + isqrt(rest * rest + 12 * literal)


def balance_qoibl(table: str, default: str) -> str:
    """Compare statement wrapping and Horner literal chunks at fixed widths.

    The program renders square near ``sqrt(2 * chars)`` when its literal
    fits (n<=6 here), else chunked near :func:`_chunk_width`; each is tried
    at a few named offsets, since the row count steps with the chunk count.
    """
    lines = [line.split() for line in default.split("\n")]
    floor = max(len(token) for line in lines for token in line)
    candidates = [default]
    side = isqrt(2 * len(default))
    candidates.extend(qoibl(table, max(floor, side + o)) for o in _FIT_OFFSETS)
    centre = _chunk_width(len(lines), floor)
    candidates.extend(
        qoibl(table, width)
        for width in (centre + o for o in _CHUNK_OFFSETS)
        if _MIN_CHUNK_LIMIT <= width < floor
    )
    return min(candidates, key=balance_score)


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
