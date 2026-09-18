"""The run form of six parameterized generators' templates.

Each generator here emits its public template itself -- every input as a
run of :data:`~esolangs.tools.helpers.TEMPLATE_CHAR` exactly as wide as
that input's setter, one run per input in name order -- with no ``{Xi}``
mark left for :func:`~esolangs.registry.render_template` to render.
"""

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from esolangs.registry import recover_setters, render_template
from esolangs.tools.helpers import TEMPLATE_CHAR, runs

#: A language and a table its generator builds quickly.
_CASES = [
    ("Back", "01101001"),
    ("Eval", "01101001"),
    ("NoComment", "01101001"),
    ("RAM0", "01101001"),
    ("123", "0110"),
    ("Minifuck", "01"),
]


@pytest.mark.parametrize(("language", "table"), _CASES)
def test_the_generator_emits_the_public_runs_itself(language: str, table: str) -> None:
    """The generator's own output is the public template: runs, no marks."""
    from esolangs.registry import LANGUAGES, resolve

    generator = LANGUAGES[resolve(language)].boolean
    assert generator is not None
    raw = str(generator(table))
    template = esolangs.generate(language, table)
    assert "{X" not in raw
    assert raw == str(template)


@pytest.mark.parametrize(("language", "table"), _CASES)
def test_every_run_is_its_setters_width(language: str, table: str) -> None:
    """``$`` occurs exactly ``sum(len(zero))`` times, in one run per input."""
    template = esolangs.generate(language, table)
    n = len(table).bit_length() - 1
    assert template.inputs == n
    assert template.count(TEMPLATE_CHAR) == sum(
        len(zero) for zero, _one in template.setters
    )
    spans = runs(template, TEMPLATE_CHAR, template.setters)
    assert [end - start for start, end in spans] == [
        len(zero) for zero, _one in template.setters
    ]


@pytest.mark.parametrize(("language", "table"), _CASES)
def test_the_template_is_every_programs_length(language: str, table: str) -> None:
    """Filling a run with either setter leaves the length alone."""
    template = esolangs.generate(language, table)
    n = template.inputs
    for row in range(2**n):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        program = esolangs.instantiate(language, template, bits)
        assert len(program) == len(template), (language, bits)
        assert TEMPLATE_CHAR not in program


def test_a_language_that_reads_its_inputs_has_no_runs() -> None:
    """Rendering or recovering for a stdin language refuses, not asserts."""
    with pytest.raises(TemplateError, match="reads its inputs"):
        render_template("brainfuck", "$", 1)
    with pytest.raises(TemplateError, match="reads its inputs"):
        recover_setters("brainfuck", "$")
