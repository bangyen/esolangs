"""Polynomial's execution: at most ``C`` commands run on a row."""

from esolangs.languages.polynomial.proof_formulas import steps


def _execution(n: int, _: str) -> int:
    """The stated bound ``C`` on commands run."""
    return steps(n)


FORMULAS = {"execution": (_execution, False, (3, 4, 5))}
