"""The run form of every parameterized generator's template."""

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from tests.support.pick import languages
from tests.support.reference import REFERENCE
from tests.support.witness_tables import row_bits

_PARAMETERIZED = languages(parameterized=True, boolean_generator=True)


@pytest.mark.parametrize("language", _PARAMETERIZED)
@pytest.mark.parametrize("table", ["00", "0000", "0110"])
def test_the_template_is_every_programs_length(language: str, table: str) -> None:
    """Filling a run with either setter leaves the length alone."""
    template = esolangs.generate(language, table)
    assert isinstance(template, esolangs.TemplateArtifact)
    n = template.bindings.inputs
    assert n == len(table).bit_length() - 1
    assert all(len(zero) == len(one) for zero, one in template.bindings.setters)
    for row in range(2**n):
        bits = row_bits(row, n)
        program = esolangs.instantiate(language, template, bits)
        assert len(program.source) == len(template.source), (
            "fill width",
            language,
            bits,
        )
        assert template.bindings.char not in program.source


@pytest.mark.parametrize("language", _PARAMETERIZED)
@pytest.mark.parametrize("table", ["00", "0000"])
def test_length_check_rejects_unequal_fills(language: str, table: str, monkeypatch):
    instantiate = esolangs.instantiate
    changed = []

    def unequal(name, template, bits, **options):
        program = instantiate(name, template, bits, **options)
        changed.append(any(bits))
        return esolangs.ProgramArtifact(
            program.source + (" " if any(bits) else ""),
            program.language,
            settings=program.settings,
        )

    monkeypatch.setattr(esolangs, "instantiate", unequal)
    with pytest.raises(AssertionError, match="fill width"):
        test_the_template_is_every_programs_length(language, table)
    assert any(changed), "the control never changed a fill's width"


def test_a_language_that_reads_its_inputs_has_no_runs() -> None:
    """A stdin reader has no input bindings to instantiate."""
    with pytest.raises(TemplateError, match="reads its inputs"):
        esolangs.instantiate(REFERENCE, esolangs.generate(REFERENCE, "01"), [0])
