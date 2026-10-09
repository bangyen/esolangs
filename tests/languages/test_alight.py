"""Alight through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from tests.cli_support import call_both
from tests.test_dialects import Unreadable


def test_set_pairs_match_settings_json(capsys):
    by_set, _ = call_both(
        ["generate", "--set", "expression_syntax=postfix", "Alight", "0110"], capsys
    )
    by_json, _ = call_both(
        [
            "generate",
            "--settings",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert by_set == by_json


def test_unknown_settings_key_suggests_the_fix(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(
            [
                "generate",
                "--settings",
                '{"expressoin_syntax":"postfix"}',
                "Alight",
                "0110",
            ],
            capsys,
        )
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "did you mean expression_syntax" in error
    assert "Alight accepts: expression_syntax" in error


@pytest.mark.parametrize("inputs", [1, 6])
def test_balanced_postfix_chunks_execute(inputs):
    table = "01" * (1 << (inputs - 1))
    settings = DialectSettings(expression_syntax="postfix")
    program = esolangs.generate("Alight", table, balance=True, settings=settings)
    assert _evaluate("Alight", program, inputs=inputs, settings=settings) == table


@pytest.mark.medium
def test_cli_generate_and_run_share_settings(tmp_path: Path, capsys):
    choices = '{"expression_syntax":"postfix"}'
    generated, _ = call_both(
        ["generate", "--settings", choices, "Alight", "0110"], capsys
    )
    path = tmp_path / "alight.txt"
    path.write_text(generated)
    for isolated in ([], ["--isolated"]):
        output, _ = call_both(
            ["run", "--settings", choices, *isolated, "Alight", str(path)],
            capsys,
            stdin="10",
        )
        assert output.strip() == "1"


def test_single_choice_languages_refuse_other_keys():
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Alight", Unreadable(), settings=DialectSettings(cell_modulus=255))


@pytest.mark.medium
def test_postfix_one_entry_chunks():
    # Width 1 forces 64 one-entry chunks; parity would hide reversed inputs.
    table = "".join(str(((row * 37) ^ (row >> 1)).bit_count() % 2) for row in range(64))
    settings = DialectSettings(expression_syntax="postfix")
    source = esolangs.generate("Alight", table, width=1, settings=settings)
    assert _evaluate("Alight", source, inputs=6, settings=settings) == table


def test_foreign_language_guard_precedes_retained_choices():
    source = esolangs.generate(
        "Alight", "01", settings=DialectSettings(expression_syntax="postfix")
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run("Brainfuck", source)
