"""Malbolge's emitted characters: the digit build ends at its highest live cell."""

from esolangs.languages.malbolge.generator.digits import _SHORT_N


def _chars(n: int, _: str) -> int:
    """13144 characters up to thirteen inputs, the whole 3^10-cell store above."""
    return 13144 if n <= _SHORT_N else 3**10


FORMULAS = {"scaling": (_chars, True, (3, 5))}
