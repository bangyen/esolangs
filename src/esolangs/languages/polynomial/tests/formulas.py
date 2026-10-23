"""Polynomial's execution: one pass over at most ``A`` instructions."""

from esolangs.languages.polynomial.proof_formulas import commands


def _execution(n: int, _: str) -> int:
    """The stated bound ``A`` on commands run."""
    return commands(n)


FORMULAS = {"execution": (_execution, False, (3, 4, 5))}
