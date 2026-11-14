"""Execute narrow layouts and retain their bindings across persistence."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from tests.support.evaluation import _evaluate
from tests.support.generator_support import assert_proved_resource_cap, probe_table
from tests.support.pick import languages


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", languages(source_kind="text", boolean_generator=True)
)
@pytest.mark.parametrize("n", [4, 6])
def test_width_one_layouts_compute_the_table(language: str, n: int) -> None:
    table = "".join(str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n))
    try:
        program = esolangs.generate(language, table, width=1)
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(language)
        table = probe_table(language)
        n = len(table).bit_length() - 1
        program = esolangs.generate(language, table, width=1)
    assert _evaluate(language, program, inputs=n) == table


@pytest.mark.parametrize("name", languages(parameterized=True))
@pytest.mark.parametrize("layout", [{"width": 1}, {"balance": True}])
def test_template_layouts_keep_their_bindings(name: str, layout: dict) -> None:
    template = esolangs.generate(name, "0110", **layout)
    restored = esolangs.from_json(name, esolangs.to_json(name, template))
    for row in range(4):
        bits = [int(char) for char in format(row, "02b")]
        code = esolangs.instantiate(name, template, bits, truth_table="0110")
        loaded = esolangs.instantiate(name, restored, bits, truth_table="0110")
        assert code == loaded
        with pytest.raises(TemplateError, match="template"):
            esolangs.instantiate(name, restored, bits, truth_table="0001")


@pytest.mark.parametrize("name", languages(parameterized=True))
def test_relabeling_slots_preserves_layout_provenance(name: str) -> None:
    api = esolangs.Language(name)
    template = api.generate("0110", width=1)
    marker = "\N{SNOWMAN}"
    assert marker not in template.source
    source = list(template.source)
    for start, end in template.spans:
        source[start:end] = marker * (end - start)
    relabeled = replace(
        template,
        source="".join(source),
        bindings=replace(template.bindings, char=marker),
    )
    restored = api.from_json(api.to_json(relabeled))
    for row, answer in enumerate("0110"):
        bits = [row >> 1, row & 1]
        assert api.instantiate(restored, bits, truth_table="0110") == template.fill(
            bits
        )
        assert api.evaluate(restored, bits).answer == answer
    with pytest.raises(TemplateError, match="is not the template"):
        api.instantiate(restored, [0, 1], truth_table="0001")


@pytest.mark.parametrize("name", languages(parameterized=True))
@pytest.mark.parametrize(("table", "width"), [("1111", 2), ("10110100", 15)])
def test_templates_with_overlong_tokens_validate(
    name: str, table: str, width: int
) -> None:
    template = esolangs.generate(name, table, width=width)
    bits = [0] * (len(table).bit_length() - 1)
    assert esolangs.instantiate(
        name, template, bits, truth_table=table
    ) == template.fill(bits)


def test_template_validation_checks_where_newlines_are_inserted() -> None:
    name = next(
        name
        for name in languages(parameterized=True)
        if esolangs.describe(name).width_effect == "none"
        and esolangs.describe(name).answer_mode == "output"
    )
    template = esolangs.generate(name, "0110")
    # Adding a newline to the first command is not a supported layout.
    changed = replace(
        template,
        source=template.source[:1] + "\n" + template.source[1:],
        spans=tuple((start + 1, end + 1) for start, end in template.spans),
    )
    with pytest.raises(TemplateError, match="template"):
        esolangs.instantiate(name, changed, [0, 1], truth_table="0110")
