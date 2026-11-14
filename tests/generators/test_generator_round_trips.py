"""Public generation contracts apply to text and raster languages alike."""

import random

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from tests.support.evaluation import _evaluate
from tests.support.generator_support import assert_proved_resource_cap
from tests.support.pick import languages

GENERATORS = sorted(
    name for name, lang in LANGUAGES.items() if lang.backend is not None
)
pytestmark = pytest.mark.medium

_SLOT_ORDER_TABLES = ("0110", "01101001", "10101010", "11110000", "00111100")


@pytest.mark.parametrize("language", GENERATORS)
def test_generated_program_obeys_its_table(language: str) -> None:
    rng = random.Random(20261001)
    dense = "".join(rng.choice("01") for _ in range(4))
    # Two 2-input tables and 3-input parity, which nothing can fold.
    tables = load_certification(LANGUAGES[language]).benchmark_tables
    if tables:
        assert_proved_resource_cap(language)
    tables = tables or ("0000", dense, "01101001")
    if LANGUAGES[language].parameterized:
        tables = tuple(dict.fromkeys((*tables, *_SLOT_ORDER_TABLES)))
    for table in tables:
        random.seed(0)
        first = esolangs.generate(language, table)
        random.seed(0)
        second = esolangs.generate(language, table)
        assert first == second
        program = esolangs.from_json(language, esolangs.to_json(language, first))
        inputs = len(table).bit_length() - 1
        assert _evaluate(language, program, inputs=inputs) == table, (
            "answers",
            language,
            table,
        )


@pytest.mark.parametrize("language", languages(parameterized=True))
def test_round_trip_rejects_swapped_inputs(language: str, monkeypatch) -> None:
    instantiate = esolangs.instantiate
    changed = []

    def swapped(name, template, bits, **options):
        swapped_bits = list(reversed(bits))
        changed.append(swapped_bits != list(bits))
        return instantiate(name, template, swapped_bits, **options)

    monkeypatch.setattr(esolangs, "instantiate", swapped)
    with pytest.raises(AssertionError, match="answers"):
        test_generated_program_obeys_its_table(language)
    assert any(changed), "the control never permuted distinct input bits"


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
    if esolangs.describe(language).parameterized:
        source = esolangs.from_json(language, esolangs.to_json(language, source))
        assert (
            _evaluate(
                language, source, inputs=len(table).bit_length() - 1, isolated=True
            )
            == table
        )
        return
    esolangs.to_file(language, source, path)
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
