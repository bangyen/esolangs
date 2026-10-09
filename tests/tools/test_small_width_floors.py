"""Execute the narrowest layouts, and fill narrow templates like plain ones."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.exceptions import TemplateError


def languages(**facts: object) -> list[str]:
    """Languages whose ``describe()`` has these facts (no tests/ imports here)."""
    return [
        name
        for name in esolangs.list_languages()
        if all(esolangs.describe(name)[k] == v for k, v in facts.items())
    ]


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", languages(source_kind="text", boolean_generator=True)
)
@pytest.mark.parametrize("n", [4, 6])
def test_width_one_layouts_compute_the_table(language: str, n: int) -> None:
    table = "".join(str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n))
    program = esolangs.generate(language, table, width=1)
    assert _evaluate(language, program, inputs=n) == table


@pytest.mark.parametrize("name", languages(parameterized=True))
def test_narrow_templates_fill_like_their_text(name: str) -> None:
    template = esolangs.generate(name, "0110", width=1)
    for row in range(4):
        bits = [int(char) for char in format(row, "02b")]
        code = esolangs.instantiate(name, template, bits, truth_table="0110")
        plain = esolangs.instantiate(name, str(template), bits, truth_table="0110")
        assert code == plain
        with pytest.raises(TemplateError, match="template"):
            esolangs.instantiate(name, str(template), bits, truth_table="0001")
