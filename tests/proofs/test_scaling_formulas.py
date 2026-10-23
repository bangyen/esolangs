"""The Scaling column's size bounds hold at small n, over every row.

A cell stating ``at most <formula> characters`` (or ``lines``/``rows``/
``cells``/``codels``/``pixels``; a ``worst`` one must also be reached) is
measured on the generated program: characters are ``len``, lines and rows are
newline-separated, cells are the bounding rectangle (``grid_area``), and a
raster's codels or pixels are its rows times its width.  A 2D grid language
states cells, a raster language codels or pixels.  Two such
bounds were false while nothing measured them: one 14T where parity reaches
15T - 14, one 6n + 3T rows reaching 17 at n=1.
"""

import re

import pytest

import esolangs
from esolangs.generation.helpers import grid_area
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES
from tests.proofs._formula import exact_at, ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs.test_execution_formulas import _tables
from tests.support.generator_support import CHECK

#: A stated size bound: the unit follows its formula.
_SIZE = re.compile(
    r"^(?:at most|worst) (.+?) (characters|lines|rows|cells|codels|pixels)\b"
)

#: A raster is judged by its rows times its width, at the default scale of 1.
_RASTER = {"codels", "pixels"}


def _raster_area(program: object) -> int:
    assert isinstance(program, Raster)
    return len(program.rows) * len(program.rows[0])


FORMULAS = ledger_formulas(lambda row: row.scaling_clause, {}, {}, column="scaling")
_UNIT = {
    row.generator: match.group(2)
    for row in load_ledger().rows
    if (match := _SIZE.match(row.scaling_clause))
}


#: From 19 inputs one build passes the fast band (S*bleq's packed decoder, 1.8 s).
_MEDIUM_FROM = 19


@pytest.mark.parametrize(
    ("name", "n"),
    [
        pytest.param(name, n, marks=[pytest.mark.medium] if n >= _MEDIUM_FROM else [])
        for name in sorted(FORMULAS)
        for n in FORMULAS[name][2]
    ],
)
def test_size_formulas_hold(name: str, n: int) -> None:
    formula, exact, _ = FORMULAS[name]
    reached = False
    for table in _tables(name, n):
        program = esolangs.generate(name, table)
        text = str(program)
        size = (
            len(text)
            if _UNIT[name] == "characters"
            else grid_area(text)
            if _UNIT[name] == "cells"
            else _raster_area(program)
            if _UNIT[name] in _RASTER
            else text.count("\n") + 1
        )
        claim = formula(n, text)
        assert size <= claim, f"{name} n={n} {table}: {size} > {claim} {_UNIT[name]}"
        reached |= size == claim
    assert reached or not exact_at(exact, n), (
        f"{name} n={n}: no table reaches the formula"
    )


def test_every_size_cell_is_checked() -> None:
    """A Scaling clause stating a size bound has a formula here, and back."""
    assert set(FORMULAS) == set(_UNIT), CHECK


def test_grid_sizes_are_cells() -> None:
    """A 2D grid is judged by area, so its stated size bound counts cells."""
    wrong = sorted(
        name
        for name, unit in _UNIT.items()
        if LANGUAGES[name].grid != (unit == "cells")
    )
    assert not wrong, f"{wrong}: a grid states cells, any other source does not"
