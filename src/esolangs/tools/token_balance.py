"""Exact balance on the prefix-sum lattice of whole-token row fits."""

from bisect import bisect_left
from itertools import accumulate
from math import isqrt


def balanced_token_width(
    tokens: list[str],
    separator: str = "",
    *,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    """Return an optimal greedy-wrap width for nonempty tokens within the bounds."""
    if not tokens:
        return minimum
    lengths = list(map(len, tokens))
    gap = len(separator)
    total = sum(lengths) + gap * len(tokens)
    longest = max(lengths)
    high = max(minimum, min(total - gap, maximum or total))

    def clipped(width: int) -> int:
        return min(high, max(minimum, width))

    def score(width: int) -> tuple[int, int, int]:
        row = widest = 0
        height = 1
        for length in lengths:
            candidate = row + gap + length if row else length
            if row and candidate > width:
                widest = max(widest, row)
                height += 1
                row = length
            else:
                row = candidate
        widest = max(widest, row)
        return abs(widest - height), total + (1 - gap) * height - 1, widest

    if minimum <= longest and longest >= len(tokens):
        return minimum
    choices = {minimum, high, clipped(isqrt(total))}
    if len(set(lengths)) == 1:
        stride = longest + gap
        columns = (gap + isqrt(gap * gap + 4 * stride * len(tokens))) // (2 * stride)
        choices.update(
            clipped(stride * count - gap) for count in (columns, columns + 1)
        )
        return min(choices, key=lambda width: (score(width), width))

    difference = min(score(width)[0] for width in choices)
    # Charged rows include their trailing gap: P=sum(length+gap), C=w+gap.
    # H>=ceil(P/C); every completed row has charge > C-(longest+gap).
    # These bounds exclude shapes beyond the two quadratic roots, except
    # the single row already represented by the upper-bound choice.
    offset = difference - gap
    root = (-offset + isqrt(offset * offset + 4 * total)) // 2 - gap
    lower = clipped(root) if root > longest else minimum
    offset = difference + gap
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
