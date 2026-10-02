"""Exact Qoibl statement fits and binary-literal chunk quotients."""

from itertools import combinations
from math import isqrt

from esolangs.tools.qoibl import qoibl
from esolangs.tools.wrap import balance_score

_Affine = tuple[int, int]


def _chunk_rows(lines: list[list[str]], count: int, size: int) -> list[list[_Affine]]:
    """Return statement token lengths affine in the requested width."""
    full = (1, -1)
    partial = (1 - count, size + count - 1)
    prefix = [(0, 2)] * 9
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
