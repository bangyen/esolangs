"""Exact balance on the prefix-sum lattice of whole-token row fits."""

from bisect import bisect_left
from collections.abc import Iterator, Sequence
from itertools import accumulate
from math import isqrt

#: Columns per row that render square: a monospace cell is about twice as
#: tall as it is wide, so balance targets ``width == CELL_ASPECT * height``.
CELL_ASPECT = 2


def rendered_side(width: int, height: int) -> int:
    """Return the side, in columns, of the least square ``width`` x ``height`` fits.

    Ranking by it trades squareness against size: a squarer layout of a
    longer program loses to a compact one that fits a smaller square.
    """
    return max(width, CELL_ASPECT * height)


def run_widths(lengths: Sequence[int]) -> Iterator[int]:
    """Yield the single-space joined width of every contiguous token run."""
    for start in range(len(lengths)):
        span = -1
        for length in lengths[start:]:
            span += length + 1
            yield span


def near_even_counts(size: int) -> set[int]:
    """Return ``size`` and the chunk counts near the divisors of ``size - 1``.

    Those are every count that splits ``size`` items near-evenly: O(sqrt size).
    """
    counts = {size}
    for divisor in range(1, isqrt(size - 1) + 1):
        counts.update((divisor + 1, (size - 1) // divisor + 1))
    return counts


def balanced_token_width(
    tokens: list[str],
    separator: str = "",
    *,
    minimum: int = 1,
    maximum: int | None = None,
    rstrip_rows: bool = False,
) -> int:
    """Return an optimal greedy-wrap width for nonempty tokens within the bounds."""
    if not tokens:
        return minimum
    lengths = list(map(len, tokens))
    trims = [len(token) - len(token.rstrip()) if rstrip_rows else 0 for token in tokens]
    gap = len(separator)
    total = sum(lengths) + gap * len(tokens)
    longest = max(lengths)
    slack = max(trims)
    high = max(minimum, min(total - gap, maximum or total))

    def clipped(width: int) -> int:
        return min(high, max(minimum, width))

    def wrap(width: int) -> tuple[int, int, int]:
        """Greedy-wrap at ``width``: rows, widest trimmed row, characters trimmed."""
        row = widest = 0
        last_trim = trimmed = 0
        height = 1
        for length, trim in zip(lengths, trims, strict=True):
            candidate = row + gap + length if row else length
            if row and candidate > width:
                widest = max(widest, row - last_trim)
                trimmed += last_trim
                height += 1
                row = length
            else:
                row = candidate
            last_trim = trim
        widest = max(widest, row - last_trim)
        trimmed += last_trim
        return height, widest, trimmed

    def score(width: int) -> tuple[int, int, int]:
        height, widest, trimmed = wrap(width)
        return (
            rendered_side(widest, height),
            total + (1 - gap) * height - 1 - trimmed,
            widest,
        )

    choices = {minimum, high, clipped(isqrt(CELL_ASPECT * total))}
    if len(set(lengths)) == 1 and len(set(trims)) == 1:
        stride = longest + gap
        offset = gap + slack
        columns = (
            offset + isqrt(offset * offset + 4 * CELL_ASPECT * stride * len(tokens))
        ) // (2 * stride)
        # The ceiling moves CELL_ASPECT*H by under CELL_ASPECT, so the sign
        # change of W - CELL_ASPECT*H lies within CELL_ASPECT+1 of the root.
        # Left of it the side is CELL_ASPECT*H, tied across a row count's
        # column counts; the fewest columns reaching that count win the tie.
        size = len(tokens)
        for count in range(max(1, columns), columns + CELL_ASPECT + 2):
            width = clipped(stride * count - gap)
            rows = -(-size // max(1, (width + gap) // stride))
            choices.update((width, clipped(stride * -(-size // rows) - gap)))
        return min(choices, key=lambda width: (score(width), width))

    side = min(score(width)[0] for width in choices)
    # Charged rows include their trailing gap: P=sum(length+gap), C=w+gap.
    # A tie needs CELL_ASPECT*H <= side with H >= P/C, so C >= A*P/side;
    # H >= P/C needs every token to fit, so that holds only past ``longest``.
    # Greedy wraps identically at w and at its longest untrimmed row, at
    # most widest + slack <= side + slack: no narrowest optimum lies beyond.
    bound = -(-CELL_ASPECT * total // side) - gap
    lower = clipped(bound) if bound > longest else minimum
    upper = min(high, max(lower, side + slack))
    choices.add(lower)
    prefix = [0, *accumulate(length + gap for length in lengths)]
    for start, position in enumerate(prefix[:-1]):
        end = bisect_left(prefix, position + lower + gap, start + 1)
        while end < len(prefix) and prefix[end] - position <= upper + gap:
            # Greedy rows change only when this contiguous run starts fitting.
            choices.add(prefix[end] - position - gap)
            end += 1
    return min(choices, key=lambda width: (score(width), width))
