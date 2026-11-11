"""The four closed-form strip areas in ArrowQueue's layout race."""

from math import isqrt


def _fold(n: int, height: int, leaves: int) -> int | None:
    """Price packed six-line stages, one middle, leaf strips and the end."""
    capacity = height - 3
    stages_per_strip = capacity // 6
    stage_strips, stage_tail = divmod(n - 1, stages_per_strip)
    last_stage = 6 * (stage_tail + 1)
    stage_height = 6 * stages_per_strip if stage_strips else 0
    middle, middle_width = last_stage + 7, 5
    if middle > capacity:
        stage_strips += 1
        stage_height = max(stage_height, last_stage)
        middle, middle_width = 7, 4

    added = min(leaves, capacity - middle)
    middle += added
    if added:
        middle_width = 6
    remaining = leaves - added
    full, tail = divmod(remaining, capacity)
    last = tail or (capacity if full else middle)
    separate_end = last + 2 > capacity
    middle_before_end = bool(remaining) or separate_end
    if not middle_before_end:
        middle_width = 6
    strips_after_middle = full + bool(tail) + separate_end
    if not stage_strips and not strips_after_middle:
        return None

    width = (
        5 * stage_strips + middle_width + middle_before_end + 6 * strips_after_middle
    )
    # The end cannot fit in a full leaf strip, so each full one pays
    # the extra linking row. Only a partial final strip can take the end.
    tallest = max(
        stage_height + 3 if stage_strips else 0,
        middle + 3 if middle_before_end else 0,
        capacity + 3 if full else 0,
        tail + 3 if tail and separate_end else 0,
        4 if separate_end else last + 4,
    )
    return width * tallest


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the four heights around the quadratic layout centre."""
    t = 1 << n
    raw = 6 * (2 * t + 6 * n + 7)
    centre = (3 + isqrt(9 + 12 * (6 * n + 7 + t))) // 2
    return {
        key: _fold(n, max(10, height), t - 1) or raw
        for key, height in zip("ABCD", range(centre - 1, centre + 3), strict=True)
    }
