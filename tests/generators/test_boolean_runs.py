"""The run form of every parameterized generator's template."""

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from esolangs.generation.helpers import runs
from esolangs.registry import recover_setters, render_template
from tests.support.pick import languages
from tests.support.reference import REFERENCE
from tests.support.witness_tables import row_bits

_PARAMETERIZED = languages(parameterized=True, boolean_generator=True)


@pytest.mark.parametrize("language", _PARAMETERIZED)
def test_every_run_is_its_setters_width(language: str) -> None:
    """``$`` occurs exactly ``sum(len(zero))`` times, in one run per input."""
    template = esolangs.generate(language, "0110")
    assert template.inputs == 2
    assert template.count(template.char) == sum(
        len(zero) for zero, _one in template.setters
    )
    spans = runs(template, template.char, template.setters)
    assert [end - start for start, end in spans] == [
        len(zero) for zero, _one in template.setters
    ]


@pytest.mark.parametrize("language", _PARAMETERIZED)
@pytest.mark.parametrize("table", ["00", "0000", "0110"])
def test_the_template_is_every_programs_length(language: str, table: str) -> None:
    """Filling a run with either setter leaves the length alone."""
    template = esolangs.generate(language, table)
    n = template.inputs
    for row in range(2**n):
        bits = row_bits(row, n)
        program = esolangs.instantiate(language, template, bits)
        assert len(program) == len(template), ("fill width", language, bits)
        assert template.char not in program


@pytest.mark.parametrize("language", _PARAMETERIZED)
@pytest.mark.parametrize("table", ["00", "0000"])
def test_length_check_rejects_unequal_fills(language: str, table: str, monkeypatch):
    instantiate = esolangs.instantiate
    changed = []

    def unequal(name, template, bits):
        program = instantiate(name, template, bits)
        changed.append(any(bits))
        return program + (" " if any(bits) else "")

    monkeypatch.setattr(esolangs, "instantiate", unequal)
    with pytest.raises(AssertionError, match="fill width"):
        test_the_template_is_every_programs_length(language, table)
    assert any(changed), "the control never changed a fill's width"


def test_a_language_that_reads_its_inputs_has_no_runs() -> None:
    """Rendering or recovering for a stdin language refuses, not asserts."""
    with pytest.raises(TemplateError, match="reads its inputs"):
        render_template(REFERENCE, "$", 1)
    with pytest.raises(TemplateError, match="reads its inputs"):
        recover_setters(REFERENCE, "$")
