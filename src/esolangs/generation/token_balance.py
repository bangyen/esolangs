"""Exact balance on the prefix-sum lattice of whole-token row fits."""

from bisect import bisect_left
from collections.abc import Iterator, Sequence
from itertools import accumulate
from math import isqrt


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
        return abs(widest - height), total + (1 - gap) * height - 1 - trimmed, widest

    actual_longest = max(
        length - trim for length, trim in zip(lengths, trims, strict=True)
    )
    # Every width retains the longest token and can only reduce the greedy
    # row count.  Once width already exceeds height, widening cannot improve
    # either difference or the tied emitted size.
    if not rstrip_rows and minimum <= actual_longest >= wrap(minimum)[0]:
        return minimum
    choices = {minimum, high, clipped(isqrt(total))}
    if len(set(lengths)) == 1 and len(set(trims)) == 1:
        stride = longest + gap
        offset = gap + slack
        columns = (offset + isqrt(offset * offset + 4 * stride * len(tokens))) // (
            2 * stride
        )
        choices.update(
            clipped(stride * count - gap) for count in (columns, columns + 1)
        )
        return min(choices, key=lambda width: (score(width), width))

    difference = min(score(width)[0] for width in choices)
    # Charged rows include their trailing gap: P=sum(length+gap), C=w+gap.
    # H>=ceil(P/C); every completed row has charge > C-(longest+gap).
    # Trimming loses at most slack per row, shifting the upper root.
    # These bounds exclude shapes beyond the two quadratic roots, except
    # the single row already represented by the upper-bound choice.
    offset = difference - gap
    root = (-offset + isqrt(offset * offset + 4 * total)) // 2 - gap
    lower = clipped(root) if root > longest else minimum
    offset = difference + gap + slack
    root = (offset + isqrt(offset * offset + 4 * total)) // 2 + 1
    upper = min(high, max(lower, longest + root))
    choices.add(lower)
    prefix = [0, *accumulate(length + gap for length in lengths)]
    for start, position in enumerate(prefix[:-1]):
        end = bisect_left(prefix, position + lower + gap, start + 1)
        while end < len(prefix) and prefix[end] - position <= upper + gap:
            # Greedy rows change only when this contiguous run starts fitting.
            choices.add(prefix[end] - position - gap)
            end += 1
    return min(choices, key=lambda width: (score(width), width))
