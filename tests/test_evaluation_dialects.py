"""Evaluation and discovery use the same specification choices as execution."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from tests.cli_support import call_both
from tests.test_public_dialects import CASES, Unreadable


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
def test_evaluation_keeps_generation_settings(language, settings):
    table = "0110"
    program = esolangs.generate(language, table, settings=settings)
    assert esolangs.evaluate(language, program, inputs=2, settings=settings) == table
    assert (
        "".join(
            esolangs.iter_evaluate(
                language, program, inputs=2, settings=settings, isolated=True
            )
        )
        == table
    )
    bound = esolangs.Language(language)
    assert bound.evaluate(program, inputs=2, settings=settings) == table
    assert "".join(bound.iter_evaluate(program, inputs=2, settings=settings)) == table


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 40])
@pytest.mark.parametrize("isolated", [False, True])
def test_plain_bitdeque_templates_use_the_selected_setters(width, isolated):
    table = "10010110"
    settings = DialectSettings(index_base=1)
    source = str(esolangs.generate("Bitdeque", table, width, settings=settings))
    assert (
        esolangs.evaluate(
            "Bitdeque", source, inputs=3, settings=settings, isolated=isolated
        )
        == table
    )


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_eof_setting_changes_the_evaluated_table(isolated):
    assert (
        esolangs.evaluate(
            "Brainfuck",
            ",,.",
            inputs=1,
            settings=DialectSettings(eof="unchanged"),
            isolated=isolated,
        )
        == "01"
    )
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.evaluate("Brainfuck", ",,.", inputs=1, isolated=isolated)
    assert any("row 0" in note for note in caught.value.__notes__)
    assert any("answered (none)" in note for note in caught.value.__notes__)


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    ("language", "settings"),
    [
        ("Brainfuck", DialectSettings(boundary="wrap")),
        ("123", DialectSettings(eof="zero")),
    ],
)
def test_evaluation_refuses_settings_before_source_reads(
    language, settings, streaming, isolated
):
    runner = esolangs.iter_evaluate if streaming else esolangs.evaluate
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
        esolangs.evaluate(
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


def test_metadata_names_dependencies_and_distinct_eof_defaults():
    brainfuck = esolangs.describe("Brainfuck")["dialect_settings"]
    assert brainfuck["eof"]["default"] == "error"
    assert esolangs.describe("Unary")["dialect_settings"]["eof"]["default"] == "zero"
    assert brainfuck["cell_modulus"]["minimum"] == 2
    assert brainfuck["cell_modulus"]["nullable"]
    assert brainfuck["boundary"]["requires"] == {"wrap": ("tape_size",)}
    line = esolangs.describe("Line")["dialect_settings"]
    assert line["boundary"]["requires"] == {
        "wrap": ("tape_size",),
        "clamp": ("tape_size",),
    }
    mammalian = esolangs.describe("SLOW ACV MAMMALIAN")["dialect_settings"]
    assert mammalian["cell_modulus"]["choices"] == (255, 256)
    assert not mammalian["cell_modulus"]["nullable"]
    assert esolangs.describe("Fargo")["dialect_settings"] == {}


def test_metadata_is_a_fresh_copy():
    info = esolangs.describe("Brainfuck")["dialect_settings"]
    info["eof"]["default"] = "zero"
    info["boundary"]["requires"].clear()
    again = esolangs.describe("Brainfuck")["dialect_settings"]
    assert again["eof"]["default"] == "error"
    assert again["boundary"]["requires"] == {"wrap": ("tape_size",)}


@pytest.mark.medium
def test_cli_evaluates_plain_template_with_shared_settings(tmp_path: Path, capsys):
    settings = DialectSettings(index_base=1)
    path = tmp_path / "bitdeque.txt"
    path.write_text(str(esolangs.generate("Bitdeque", "0110", 1, settings=settings)))
    output, _ = call_both(
        [
            "evaluate",
            "--settings",
            '{"index_base":1}',
            "--table",
            "0110",
            "Bitdeque",
            str(path),
        ],
        capsys,
    )
    assert output.strip() == "0110"


def test_cli_evaluation_rejects_settings_before_io(capsys):
    with (
        patch(
            "esolangs.cli_round_trip._read_program", side_effect=AssertionError("read")
        ),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(
            [
                "evaluate",
                "--settings",
                '{"boundary":"wrap"}',
                "--inputs",
                "1",
                "Brainfuck",
                "missing",
            ],
            capsys,
        )
    assert caught.value.code == 2


def test_cli_json_describes_dialect_choices(capsys):
    output, _ = call_both(["describe", "--json", "Unary"], capsys)
    schema = json.loads(output)["dialect_settings"]
    assert schema["eof"]["default"] == "zero"
    assert schema["boundary"]["requires"] == {"wrap": ["tape_size"]}
