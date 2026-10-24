"""Modulous balance: the closed-form chunk width against the old sweep."""

import random

from esolangs.generation.token_balance import rendered_side, run_widths
from esolangs.generation.wrap import balance_score
from esolangs.languages.modulous.generator import (
    _TABLE_PUSH_OVERHEAD,
    _TOKEN,
    _chunked_columns,
    modulous,
)
from tests.support.generator_support import near_even_counts

# The oracle: ``_balance`` once scored every chunk count near a divisor of
# ``size - 1`` at each width where a greedy row count can change.
# Token lengths of the chunk-boundary window ``[ PSH STR "<chunk>"] [ PSH STR``
# with the chunk itself zeroed, so slice sums over it measure only the fixed
# push syntax straddling a chunk boundary.
_CHUNK_BOUNDARY_FIXED = [1, 3, 3, 0, 1, 3, 3]

# A chunk token ``"<chunk>"]`` is the chunk plus quote, quote, bracket.
_CHUNK_TOKEN_EXTRA = 3

# Estimated fixed characters per table chunk: the ``[PSH STR "`` / ``"]`` push
# syntax plus its separators -- the per-chunk term of the length proxy scored
# in the chunked search below.
_CHUNK_PUSH_OVERHEAD = 14

# Narrowest chunk width the search considers: ``[ PSH STR`` is 9 characters and
# needs a row of its own, so narrower chunks cannot use the two-rows-per-push
# layout the row estimate assumes.
_MIN_CHUNK_WIDTH = 6


def _height(parts: list[int], columns: int) -> int:
    """Greedy single-space wrap row count for token lengths."""
    rows, used = 1, 0
    for length in parts:
        if used and used + 1 + length > columns:
            rows += 1
            used = length
        else:
            used += length + bool(used)
    return rows


def _swept_columns(
    table: str, suffix_lengths: list[int], suffix_fits: set[int]
) -> int | None:
    """Return the best column width from the chunked-table search, if any.

    Splits the table literal into ``count`` ``[PSH STR "…"]`` pushes and scans
    chunk widths, counting rows at ``chunk width + 3`` columns -- the exact fit
    of a full chunk token -- as the greedy wrap of the first chunk's boundary
    window (``[ PSH STR "<chunk>"] [ PSH STR``), plus one row for the second
    push's tail and two rows per remaining push, plus the greedy wrap of the
    instruction suffix.  Only chunk widths where a greedy row count can change
    are visited: widths where a suffix token run exactly fills the column
    budget, and widths where the boundary window rewraps, for chunk counts
    near the divisors of ``size - 1``.  Each visited interval scores
    ``(rendered_side(columns, rows), size + 14 * count, columns)`` -- side first,
    then an estimated program length (table characters plus push syntax per
    chunk), then width -- and the winning width is the first of its
    interval.
    """
    size = len(table)

    # Widths of the push syntax around a chunk boundary: every contiguous run
    # of the boundary template straddling the (zeroed) chunk token.
    boundary_fits = {
        sum(_CHUNK_BOUNDARY_FIXED[start:stop]) + stop - start - 1
        for start in range(4)
        for stop in range(4, 8)
    }
    quotients = near_even_counts(size)

    best: tuple[int, int, int] | None = None
    for count in quotients:
        # ``count`` pushes need chunks of at least ``size / count`` characters;
        # the bounds keep the final chunk non-empty and short of a full chunk.
        lower = max(_MIN_CHUNK_WIDTH, (size + count - 1) // count)
        upper = min(size - 1, (size - 1) // (count - 1))
        if lower > upper:
            continue
        events = {lower, upper + 1}
        events.update(fit for fit in suffix_fits if lower < fit <= upper)
        events.update(
            point
            for extra in boundary_fits
            if lower < (point := (size + extra + count - 1) // count) <= upper
        )
        boundaries = sorted(events)
        for start in boundaries[:-1]:
            partial = size - (count - 1) * start
            # The boundary window with the partial chunk filled in.
            rows = (
                _height(
                    [1, 3, 3, partial + _CHUNK_TOKEN_EXTRA, 1, 3, 3],
                    start + _CHUNK_TOKEN_EXTRA,
                )
                + 2 * count
                - 3
                + _height(suffix_lengths, start + _CHUNK_TOKEN_EXTRA)
            )
            # Rows are fixed inside this event interval: its first width
            # renders the smallest square.
            columns = start + _CHUNK_TOKEN_EXTRA
            score = (
                rendered_side(columns, rows),
                size + _CHUNK_PUSH_OVERHEAD * count,
                columns,
            )
            if best is None or score < best:
                best = score
    return best[2] if best is not None else None


def test_chunked_columns_match_the_swept_optimum() -> None:
    """The square root rule is within 3% of the sweep's rendered side (sum)."""
    rng = random.Random(9)
    got = swept = 0
    for n in range(3, 13):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        default = modulous(table)
        size = len(table)
        lengths = list(map(len, _TOKEN.findall(default[size + _TABLE_PUSH_OVERHEAD :])))
        fits = {span - _CHUNK_TOKEN_EXTRA for span in run_widths(lengths)}
        columns = _swept_columns(table, lengths, fits)
        assert columns is not None
        swept += balance_score(modulous(table, columns))[0]
        got += min(
            balance_score(modulous(table, _chunked_columns(size, lengths) + off))[0]
            for off in (-3, -1, 1, 3)
        )
    assert got <= 1.03 * swept


def test_suffix_measurement_starts_past_the_table_push() -> None:
    """The chunked centre is measured from the instruction suffix.

    The suffix slice starts at ``size + _TABLE_PUSH_OVERHEAD``,
    past the default program's table push.  Starting the slice
    that far earlier folds table-push tokens into the suffix
    sum, moves the centre, and this table's balanced form
    renders 48 columns wide instead of 49.
    """
    from esolangs.languages.modulous.generator import _balance, modulous

    table = (
        "0100001101101111101010100101110100101001001110010000111011001011"
        "1111010111000000010101110011001010010110000010001110011011001101"
        "1101000001011010111011111100101000110011011010001011001010111001"
        "1011100011011111000101001001110111100100011100010010011010111100"
    )
    balanced = _balance(table, modulous(table))
    assert max(map(len, balanced.splitlines())) == 49
