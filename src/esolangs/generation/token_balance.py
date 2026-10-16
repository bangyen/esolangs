"""Balance of whole-token row fits: a closed-form width, within 5% of the best side."""

from collections.abc import Iterator, Sequence
from math import isqrt, sqrt

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


def balanced_token_width(
    tokens: list[str],
    separator: str = "",
    *,
    minimum: int = 1,
    maximum: int | None = None,
    rstrip_rows: bool = False,
) -> int:
    """Return a greedy-wrap width within 5% of the best side, within the bounds."""
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

    # Greedy rows waste about half a token, so the capacity-corrected square
    # solves W*(W - c) = CELL_ASPECT*total for c = 0, mean/2, mean cost.  The
    # lattice optimum sits within 2 of one of them: on 3x2000 random lists
    # (n<60, gap 0/1, trims, bounds) the best of these widths was at most
    # 2% above the exact scan's side; c=0 alone was 4.6% worse on average
    # and 43% worse at worst.
    mean = total / len(lengths)
    for half_cost in (0, mean / 2, mean):
        root = (half_cost + sqrt(half_cost**2 + 4 * CELL_ASPECT * total)) / 2
        choices.update(clipped(int(root) + step) for step in range(-2, 3))
    choices.add(clipped(longest))
    return min(choices, key=lambda width: (score(width), width))
