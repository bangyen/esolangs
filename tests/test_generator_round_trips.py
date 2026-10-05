"""Public generation contracts apply to text and raster languages alike."""

import random

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES

GENERATORS = sorted(
    name for name, lang in LANGUAGES.items() if lang.boolean is not None
)
pytestmark = pytest.mark.medium


@pytest.mark.parametrize("language", GENERATORS)
def test_generated_program_obeys_its_table(language: str) -> None:
    rng = random.Random(20261001)
    dense = "".join(rng.choice("01") for _ in range(4))
    for table in ("0000", dense):
        random.seed(0)
        first = esolangs.generate(language, table)
        random.seed(0)
        second = esolangs.generate(language, table)
        assert first == second
        program = (
            Raster.from_png(first.to_png()) if isinstance(first, Raster) else first
        )
        assert _evaluate(language, program, inputs=2) == table


@pytest.mark.parametrize("language", GENERATORS)
@pytest.mark.parametrize("table", ["", "0", "010", "0121"])
def test_generators_reject_invalid_tables(language: str, table: str) -> None:
    with pytest.raises(esolangs.TruthTableError):
        esolangs.generate(language, table)
