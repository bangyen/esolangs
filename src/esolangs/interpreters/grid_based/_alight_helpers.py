"""Alight grid padding and immutable snapshot values."""


def _grid(code: list[str]) -> list[str]:
    """Pad ragged source to a rectangle for in-bounds indexing."""
    width = max((len(line) for line in code), default=0)
    return [line.ljust(width) for line in code]


def _freeze(value: object) -> object:
    """Freeze nested lists and dictionaries without dropping snapshot state."""
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        # Pending expression tuples contain live lists; freeze their leaves too.
        return tuple(_freeze(v) for v in value)
    return value
