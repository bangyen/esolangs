"""Evaluation and discovery use the same specification choices as execution."""

import json

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate, _iter_evaluate
from tests.cli_support import call_both
from tests.test_public_dialects import CASES, Unreadable


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
def test_evaluation_keeps_generation_settings(language, settings):
    table = "0110"
    program = esolangs.generate(language, table, settings=settings)
    assert _evaluate(language, program, inputs=2, settings=settings) == table
    assert (
        "".join(
            _iter_evaluate(
                language, program, inputs=2, settings=settings, isolated=True
            )
        )
        == table
    )
    bound = esolangs.Language(language)
    assert _evaluate(bound.name, program, inputs=2, settings=settings) == table
    assert (
        "".join(_iter_evaluate(bound.name, program, inputs=2, settings=settings))
        == table
    )


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    ("language", "settings"),
    [
        ("Brainfuck", DialectSettings(cell_modulus=255)),
        ("123", DialectSettings(cell_modulus=255)),
    ],
)
def test_evaluation_refuses_settings_before_source_reads(
    language, settings, streaming, isolated
):
    runner = _iter_evaluate if streaming else _evaluate
    with pytest.raises(esolangs.ArgumentError):
        list(
            runner(
                language, Unreadable(), inputs=1, settings=settings, isolated=isolated
            )
        )


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_empty_settings_survive_termination_evaluation(isolated):
    source = esolangs.generate("123", "01")
    assert (
        _evaluate(
            "123", source, inputs=1, settings=DialectSettings(), isolated=isolated
        )
        == "01"
    )


@pytest.mark.medium
def test_every_reported_default_and_choice_is_accepted():
    for language in esolangs.list_languages():
        schema = esolangs.describe(language)["dialect_settings"]
        defaults = {key: item["default"] for key, item in schema.items()}
        DialectSettings(**defaults).options(language)
        for key, item in schema.items():
            values = item["choices"]
            if values is None:
                values = (item["minimum"], None)
            for value in values:
                selected = defaults | {key: value}
                for dependency in item["requires"].get(str(value), ()):
                    selected[dependency] = 8
                DialectSettings(**selected).options(language)
            if item["minimum"] is not None:
                with pytest.raises(esolangs.ArgumentError):
                    DialectSettings(**(defaults | {key: item["minimum"] - 1})).options(
                        language
                    )


def test_metadata_is_a_fresh_copy():
    info = esolangs.describe("Grapheme")["dialect_settings"]
    info["integer_conversion"]["default"] = "after_each_letter"
    again = esolangs.describe("Grapheme")["dialect_settings"]
    assert again["integer_conversion"]["default"] == "between_letters"


def test_cli_json_describes_dialect_choices(capsys):
    output, _ = call_both(["describe", "--json", "Grapheme"], capsys)
    schema = json.loads(output)["dialect_settings"]
    assert schema["integer_conversion"]["default"] == "between_letters"
    assert schema["integer_conversion"]["requires"] == {}
