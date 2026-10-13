"""Boolean generator for qoibl.

A packed literal has no subtrees to fold or share.
"""

from itertools import combinations
from math import isqrt

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import balance_score, wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["qoibl"]


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


def qoibl(truth_table: str, width: int | None = None) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    whole table rides in one binary literal, bit ``k`` holding row ``k``, so
    ``table // 2**index`` then ``r - 2 * (r // 2)`` reads that row off.
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
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))

    # ``p = p * (p * (et - 47))``: the digit is 48 or 49, so that factor is
    # the bit plus one and squaring makes the reads Horner's rule.  Essential,
    # not an optimisation: the operators are + - * / only, so ``p`` must reach
    # ``2**index`` by squaring for the packed literal's division.
    bit = f"et ry ey ry {_qoibl_enc(_ASCII_ZERO - 1)}"
    lines = []
    counted = False
    for weight in weights:
        if not weight:
            lines.append(f"we {row if counted else power} we {bit} we")
        elif counted:
            lines.append(
                f"we {power} we qe {power} qe ry ye ry qe {power} qe ry ye ry {bit} we"
            )
        else:
            lines.append(f"we {power} we {bit} we")
            counted = True
    lines.append(f"we {row} we {_qoibl_enc(packed)} ry yy ry qe {power} qe we")
    lines.append(
        f"tt qe {row} qe ry ee ry {zero} ry ey ry ye ry ye ry "
        f"qe {row} qe ry yy ry ye tt"
    )
    program = "\n".join(lines)
    if width is None or width <= 0:
        return program
    # Fits as-is: no Horner expansion needed.
    wrapped = _qoibl(program, width)
    if max(map(len, wrapped.splitlines())) <= width:
        return wrapped
    limit = max(2, width)
    output: list[str] = []
    scratch = _qoibl_enc(2)
    for line in lines:
        tokens = line.split()
        for at, token in enumerate(tokens):
            if len(token) <= limit:
                continue
            # Each statement has one long literal. Binary Horner steps use
            # spare variable 2; separate multiply/add respect right association.
            chunks = [token[i : i + limit - 1] for i in range(0, len(token), limit - 1)]
            output.append(f"we {scratch} we {chunks[0]} we")
            for chunk in chunks[1:]:
                factor = _qoibl_enc(1 << len(chunk))
                output.append(f"we {scratch} we qe {scratch} qe ry ye ry {factor} we")
                output.append(f"we {scratch} we qe {scratch} qe ry ee ry {chunk} we")
            tokens[at] = f"qe {scratch} qe"
        output.append(" ".join(tokens))
    return _qoibl("\n".join(output), limit)


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
    """Minimize the affine row envelope at height roots and envelope corners."""
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
    """Compare ordinary statement fits and Horner literal chunk regimes."""
    lines = [line.split() for line in default.split("\n")]
    floor = max(len(token) for line in lines for token in line)
    candidates = [default]
    # Below six columns the fixed ASCII literals also expand into Horner steps.
    candidates.extend(qoibl(table, width) for width in range(1, 6))
    fits = {floor}
    for line in lines:
        for start in range(len(line)):
            span = -1
            for token in line[start:]:
                span += len(token) + 1
                if span >= floor:
                    fits.add(span)
    candidates.extend(qoibl(table, width) for width in sorted(fits))
    quotients = {floor}
    for divisor in range(1, isqrt(floor - 1) + 1):
        quotients.update((divisor + 1, (floor - 1) // divisor + 1))
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
    weekly_mutation=("interpreter",),
    boolean=qoibl,
    # Not a tree: the table is one binary literal the reads divide down.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=balance_qoibl,
)
