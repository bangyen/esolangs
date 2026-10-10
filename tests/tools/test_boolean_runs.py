"""The run form of every parameterized generator's template."""

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from esolangs.registry import recover_setters, render_template
from esolangs.tools.helpers import runs
from tests.pick import languages
from tests.witness_tables import row_bits

#: Every template language, on XOR.
_CASES = [
    (name, "0110") for name in languages(parameterized=True, boolean_generator=True)
]


@pytest.mark.parametrize(("language", "table"), _CASES)
def test_every_run_is_its_setters_width(language: str, table: str) -> None:
    """``$`` occurs exactly ``sum(len(zero))`` times, in one run per input."""
    template = esolangs.generate(language, table)
    n = len(table).bit_length() - 1
    assert template.inputs == n
    assert template.count(template.char) == sum(
        len(zero) for zero, _one in template.setters
    )
    spans = runs(template, template.char, template.setters)
    assert [end - start for start, end in spans] == [
        len(zero) for zero, _one in template.setters
    ]


@pytest.mark.parametrize(("language", "table"), _CASES)
def test_the_template_is_every_programs_length(language: str, table: str) -> None:
    """Filling a run with either setter leaves the length alone."""
    template = esolangs.generate(language, table)
    n = template.inputs
    for row in range(2**n):
        bits = row_bits(row, n)
        program = esolangs.instantiate(language, template, bits)
        assert len(program) == len(template), (language, bits)
        assert template.char not in program


def test_a_language_that_reads_its_inputs_has_no_runs() -> None:
    """Rendering or recovering for a stdin language refuses, not asserts."""
    with pytest.raises(TemplateError, match="reads its inputs"):
        render_template("brainfuck", "$", 1)
    with pytest.raises(TemplateError, match="reads its inputs"):
        recover_setters("brainfuck", "$")
