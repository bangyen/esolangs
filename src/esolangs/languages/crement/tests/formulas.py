"""Crement's source lines: the generic maximum survives from n=3."""

from esolangs.languages.crement.proof_formulas import lines


def _lines(n: int, _: str) -> int:
    return lines(n)


FORMULAS = {"scaling": (_lines, True, (1, 2, 3, 4, 5))}
