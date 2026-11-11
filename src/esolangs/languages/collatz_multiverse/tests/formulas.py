"""Constant-closure terms for the four-row source envelope."""

from esolangs.languages.collatz_multiverse.proof_formulas import _constants


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Charge each constant's two assignments and their line separators."""
    width = 0
    for k in _constants(n):
        c = (k - 2) % 4
        width += len(f"k{k} = negativeOne x + k{(k - c) // 2}, NOT PRINT.") + 1
        width += len(f"k{k} = k2 x + {'k' + str(c) if c else 'z'}, NOT PRINT.") + 1
    return {"Q": width}
