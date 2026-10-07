"""Alight grid padding."""


def _grid(code: list[str]) -> list[str]:
    """Pad ragged source to a rectangle for in-bounds indexing."""
    width = max((len(line) for line in code), default=0)
    return [line.ljust(width) for line in code]
