"""Boolean generator for qoibl.

A packed literal has no subtrees to fold or share.
"""

from itertools import combinations

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
)
from esolangs.generation.token_balance import near_even_counts, run_widths
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
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    whole table rides in one binary literal, bit ``k`` holding row ``k``.
    Each essential input read multiplies ``2**bit`` into ``power``, so after
    the reads ``power`` is ``2**index`` -- the row index accumulates in the
    exponent by Horner's rule.  ``packed // power`` then shifts the table
    down to the row, and the printed character is ``'0'`` plus its low bit.
    """
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


_Affine = tuple[int, int]


def _chunk_rows(lines: list[list[str]], count: int, size: int) -> list[list[_Affine]]:
    """Return statement token lengths affine in the requested width."""
    full = (1, -1)
    partial = (1 - count, size + count - 1)
    prefix = [(0, 2)] * 9  # tokens of "we s we qe s qe ry ye ry"
    rows: list[list[_Affine]] = []
    for line in lines:
        tokens: list[_Affine] = []
        for token in line:
            if len(token) <= 6:
                tokens.append((0, len(token)))
                continue
            rows.append([(0, 2)] * 3 + [full, (0, 2)])
            for index in range(1, count):
                part = partial if index == count - 1 else full
                factor = (part[0], part[1] + 1)
                rows.extend(([*prefix, factor, (0, 2)], [*prefix, part, (0, 2)]))
            tokens.extend([(0, 2)] * 3)
        rows.append(tokens)
    return rows


def _row_fits(
    statements: list[list[_Affine]], width: int, stop: int
) -> tuple[list[_Affine], int]:
    """Return rendered row lengths and the next whole-token fit."""
    rows = []
    for statement in statements:
        used = (0, 0)
        for slope, offset in statement:
            if used == (0, 0):
                used = (slope, offset)
                continue
            span = (used[0] + slope, used[1] + offset + 1)
            if span[0] * width + span[1] > width:
                # Each statement has at most one variable-length token; its
                # slope is at most one, so a failed fit can only become true.
                rate = 1 - span[0]
                if rate:
                    stop = min(stop, (span[1] + rate - 1) // rate)
                rows.append(used)
                used = (slope, offset)
            else:
                used = span
        rows.append(used)
    return rows, stop


def _best_width(rows: list[_Affine], length: _Affine, lower: int, upper: int) -> int:
    """Minimize the affine row envelope at height roots and envelope corners.

    A closed-form width from a smooth height model misses: mean imbalance
    5.8 vs 1.0 at n=7..8, since height steps with the chunk count.
    """
    envelope: dict[int, int] = {}
    for slope, offset in rows:
        envelope[slope] = max(envelope.get(slope, offset), offset)
    points = {lower, upper}
    height = len(rows)
    for slope, offset in envelope.items():
        if slope:
            root = (height - offset) // slope
            points.update((root, root + 1))
    for (left, left_offset), (right, right_offset) in combinations(envelope.items(), 2):
        crossing = (right_offset - left_offset) // (left - right)
        points.update((crossing, crossing + 1))

    def score(width: int) -> tuple[int, int, int]:
        span = max(slope * width + offset for slope, offset in envelope.items())
        return abs(span - height), length[0] * width + length[1], span

    return min((min(max(point, lower), upper) for point in points), key=score)


def balance_qoibl(table: str, default: str) -> str:
    """Compare ordinary statement fits and Horner literal chunk regimes.

    Widths 1..5 never won (all 65,536 tables at n=4, 300 each at n=5, 6), so
    they are not swept.  Fits decide n<=4 (n=4 mean imbalance 22 -> 1.8); the
    chunk search decides n>=6 (n=8: 243 -> 0.9).
    """
    lines = [line.split() for line in default.split("\n")]
    floor = max(len(token) for line in lines for token in line)
    candidates = [default]
    fits = {floor}
    for line in lines:
        fits.update(span for span in run_widths(list(map(len, line))) if span >= floor)
    candidates.extend(qoibl(table, width) for width in sorted(fits))
    quotients = near_even_counts(floor)
    best: tuple[int, int, int, int] | None = None
    for count in quotients:
        lower = max(5, (floor + count - 1) // count) + 1
        upper = min(floor - 2, (floor - 1) // (count - 1)) + 1
        if lower > upper:
            continue
        statements = _chunk_rows(lines, count, floor)
        length = (
            sum(slope for line in statements for slope, _ in line),
            sum(offset + 1 for line in statements for _, offset in line) - 1,
        )
        while lower <= upper:
            rows, stop = _row_fits(statements, lower, upper + 1)
            width = _best_width(rows, length, lower, stop - 1)
            span = max(slope * width + offset for slope, offset in rows)
            score = (abs(span - len(rows)), length[0] * width + length[1], span, width)
            if best is None or score < best:
                best = score
            lower = stop
    if best is not None:
        candidates.append(qoibl(table, best[3]))
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
