"""Mammalian source wrapping and balancing on four-character cells."""

from __future__ import annotations

from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _span, _wrap_grid, balance_score


def _mammalian(program: str, width: int) -> str:
    """Wrap Mammalian on four-character cells, one cell per ``SEED``.

    ``SEED`` forms nearly every long run; the other words span two or three cells.
    """
    tokens = program.split()
    if not tokens:
        return program
    return _wrap_grid(tokens, width, 4, left_aligned=True)


def _balance_mammalian(program: str) -> str:
    """Choose the squarest four-character cell layout."""
    tokens = program.split()
    if not tokens:
        return program
    aligned = [token.ljust(_span(len(token), 4) * 5 - 1) for token in tokens]
    width = balanced_token_width(aligned, " ", rstrip_rows=True)
    return min(program, _mammalian(program, width), key=balance_score)
