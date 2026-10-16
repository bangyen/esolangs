"""Qoibl balance: fixed offsets from a closed form against the old sweep."""

import random
from itertools import combinations, product

from esolangs.generation.token_balance import (
    CELL_ASPECT,
    near_even_counts,
    rendered_side,
    run_widths,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.qoibl.generator import balance_qoibl, qoibl

# The oracle: ``balance_qoibl`` once tried every statement fit and, for every
# chunk count near a divisor of the literal length, the affine row envelope's
# best width.

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
            root = (CELL_ASPECT * height - offset) // slope
            points.update((root, root + 1))
    for (left, left_offset), (right, right_offset) in combinations(envelope.items(), 2):
        crossing = (right_offset - left_offset) // (left - right)
        points.update((crossing, crossing + 1))

    def score(width: int) -> tuple[int, int, int]:
        span = max(slope * width + offset for slope, offset in envelope.items())
        return rendered_side(span, height), length[0] * width + length[1], span

    return min((min(max(point, lower), upper) for point in points), key=score)


def swept_balance(table: str, default: str) -> str:
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
            score = (
                rendered_side(span, len(rows)),
                length[0] * width + length[1],
                span,
                width,
            )
            if best is None or score < best:
                best = score
            lower = stop
    if best is not None:
        candidates.append(qoibl(table, best[3]))
    return min(candidates, key=balance_score)


def test_qoibl_affine_row_envelope_minima() -> None:
    for negative, constant, positive, extra in product(
        [32, 45, 60], [1, 5, 15], [-1, 4, 12], [0, 10, 30]
    ):
        rows = [(-2, negative), (0, constant), (1, positive)] + [(0, 1)] * extra
        length = (
            sum(slope for slope, _ in rows),
            sum(offset for _, offset in rows) + len(rows) - 1,
        )
        width = _best_width(rows, length, 1, 15)
        layouts = [
            "\n".join("x" * (slope * columns + offset) for slope, offset in rows)
            for columns in range(1, 16)
        ]
        assert balance_score(layouts[width - 1]) == min(map(balance_score, layouts))


def test_balance_stays_near_the_swept_optimum() -> None:
    """Seven named widths are within 3% of the sweep's rendered side (sum)."""
    rng = random.Random(1)
    got = swept = 0
    for n in range(2, 10):
        for _ in range(6):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            default = qoibl(table)
            got += balance_score(balance_qoibl(table, default))[0]
            swept += balance_score(swept_balance(table, default))[0]
    assert swept <= got <= 1.03 * swept
