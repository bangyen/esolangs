"""Public generation contracts apply to text and raster languages alike."""

import random

import pytest

import esolangs
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES
from tests.support.evaluation import _evaluate
from tests.support.generator_support import assert_proved_resource_cap

GENERATORS = sorted(
    name for name, lang in LANGUAGES.items() if lang.boolean is not None
)
pytestmark = pytest.mark.medium


@pytest.mark.parametrize("language", GENERATORS)
def test_generated_program_obeys_its_table(language: str) -> None:
    rng = random.Random(20261001)
    dense = "".join(rng.choice("01") for _ in range(4))
    # Two 2-input tables and 3-input parity, which nothing can fold.
    tables = LANGUAGES[language].benchmark_tables
    if tables:
        assert_proved_resource_cap(language)
    for table in tables or ("0000", dense, "01101001"):
        random.seed(0)
        first = esolangs.generate(language, table)
        random.seed(0)
        second = esolangs.generate(language, table)
        assert first == second
        program = (
            Raster.from_png(first.to_png())
            if isinstance(first, Raster)
            else esolangs.load_program(language, esolangs.dump_program(language, first))
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


@pytest.mark.slow
@pytest.mark.parametrize("language", GENERATORS)
def test_saved_program_executes_in_a_fresh_process(language, tmp_path) -> None:
    from tests.support.generator_support import probe_table

    table = probe_table(language, "00101101")
    source = esolangs.generate(language, table)
    path = tmp_path / "program"
    if esolangs.describe(language)["parameterized"]:
        source = esolangs.load_program(
            language, esolangs.dump_program(language, source)
        )
        assert (
            _evaluate(
                language, source, inputs=len(table).bit_length() - 1, isolated=True
            )
            == table
        )
        return
    esolangs.save_program(source, path)
    assert (
        _evaluate(language, path, inputs=len(table).bit_length() - 1, isolated=True)
        == table
    )


@pytest.mark.slow
@pytest.mark.parametrize("language", GENERATORS)
@pytest.mark.parametrize("options", [{"width": 5}, {"balance": True}])
def test_layout_options_preserve_answers(language, options) -> None:
    from tests.support.generator_support import probe_table

    table = probe_table(language, "00101101")
    program = esolangs.generate(language, table, **options)
    assert _evaluate(language, program, inputs=len(table).bit_length() - 1) == table
