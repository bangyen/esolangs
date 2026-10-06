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
    # Two 2-input tables and 3-input parity, which nothing can fold.
    for table in ("0000", dense, "01101001"):
        random.seed(0)
        first = esolangs.generate(language, table)
        random.seed(0)
        second = esolangs.generate(language, table)
        assert first == second
        program = (
            Raster.from_png(first.to_png()) if isinstance(first, Raster) else first
        )
        inputs = len(table).bit_length() - 1
        assert _evaluate(language, program, inputs=inputs) == table


#: A bad table of each kind, and the start of the shared validator's message.
_REFUSALS = {
    "": "truth table must have a power-of-two number of entries (2**n), got 0",
    "0": "truth table needs at least one input (n >= 1)",
    "011": "truth table must have a power-of-two number of entries (2**n), got 3",
    "02": "truth table must contain only '0' and '1', got '02'",
}


@pytest.mark.parametrize("language", GENERATORS)
def test_generators_refuse_bad_tables_in_the_shared_words(language: str) -> None:
    """Every generator refuses through the shared validator."""
    for table, message in _REFUSALS.items():
        with pytest.raises(esolangs.TruthTableError) as caught:
            esolangs.generate(language, table)
        assert str(caught.value).startswith(message), (language, table)
