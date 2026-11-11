"""Streetcode's emitted area: the tree below four inputs, the race from four."""


def _gap(n: int) -> int:
    """G: the flat street's mouth spacing, 51 columns or the room, per level."""
    return sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))
