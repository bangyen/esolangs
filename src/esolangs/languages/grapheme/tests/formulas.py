"""Grapheme's emitted characters: one per command, the literal 2^T long."""


def _chars(n: int, _: str) -> int:
    """17n + 21 + d, d the digits of 2^T (steps equal characters)."""
    return 17 * n + 21 + len(str(2 ** (1 << n)))


FORMULAS = {"scaling": (_chars, True, (3, 5))}
