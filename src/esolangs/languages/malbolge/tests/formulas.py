"""Malbolge's emitted characters: the digit build ends at its highest live cell."""

from esolangs.languages.malbolge.generator.digits import _SHORT_N

#: Highest live cell + 1 at fourteen and fifteen inputs.
_SHORT_CHARS = {14: 19683, 15: 52480}


def _chars(n: int, _: str) -> int:
    """13144 characters to thirteen inputs, 19683 and 52480 at fourteen and
    fifteen, the whole 3^10-cell store from sixteen."""
    return 13144 if n <= _SHORT_N else _SHORT_CHARS.get(n, 3**10)


FORMULAS = {"scaling": (_chars, True, (3, 5))}
