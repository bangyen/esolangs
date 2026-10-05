"""Balanced layouts and CLI sessions retain explicit dialect choices."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.cli_debug import _run_tui_session
from esolangs.tools.alight.balance import _balance_postfix
from esolangs.tui import History, replay
from tests.cli_support import call_both


@pytest.mark.parametrize(
    ("language", "choices"),
    [
        ("Grapheme", '{"integer_conversion":"after_each_letter"}'),
        ("Alight", '{"expression_syntax":"postfix"}'),
        ("Packlang", '{"literal_policy":"binary_digits"}'),
    ],
)
def test_settings_reach_evaluation(language, choices, capsys):
    program, error = call_both(
        ["generate", "--settings", choices, language, "0110"], capsys
    )
    assert error == ""
    settings = DialectSettings(**json.loads(choices))
    assert _evaluate(language, program, inputs=2, settings=settings) == "0110"


def test_cli_debug_uses_settings(tmp_path: Path, capsys):
    source = tmp_path / "conversion.grapheme"
    source.write_text("FAFY")
    output, _ = call_both(
        [
            "debug",
            "--settings",
            '{"integer_conversion":"after_each_letter"}',
            "Grapheme",
            str(source),
        ],
        capsys,
    )
    assert "halted: yes" in output
    assert "output: '10'" in output


def test_cli_settings_rejected_before_work(capsys):
    with (
        patch("esolangs.cli_debug._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as exc,
    ):
        call_both(
            [
                "debug",
                "--settings",
                '{"integer_conversion":"after_each_letter"}',
                "Fargo",
                "missing",
            ],
            capsys,
        )
    assert exc.value.code == 2


def test_tui_settings_reach_wrapper():
    settings = DialectSettings(integer_conversion="after_each_letter")
    with patch("esolangs.cli_debug.run_tui") as run:
        _run_tui_session("Grapheme", "FAFY", "", {}, None, settings)
    assert run.call_args.kwargs["settings"] is settings


def test_tui_replay_retains_settings():
    settings = DialectSettings(integer_conversion="after_each_letter")
    history = History("Grapheme", "FAFYPPPP", settings=settings)
    history.budget = 1
    assert history.at(8).output == "10"
    assert history.at(4).output == "10"
    assert history.at(2) == replay("Grapheme", "FAFYPPPP", "", 2, settings=settings)


def test_postfix_balance_model_checks_rendering():
    with (
        patch("esolangs.tools.alight.balance._alight_folded", return_value="bad"),
        pytest.raises(AssertionError, match="postfix fold model"),
    ):
        _balance_postfix("0110", 2, "x" * 100)
    assert _balance_postfix("01", 1, "x") == "x"


@pytest.mark.parametrize("plain", [False, True])
def test_balanced_bitdeque_setters(plain):
    settings = DialectSettings()
    table = "10010110"
    program = esolangs.generate("Bitdeque", table, balance=True, settings=settings)
    for row, expected in enumerate(table):
        source = str(program) if plain else program
        bits = tuple(map(int, format(row, "03b")))
        filled = esolangs.instantiate(
            "Bitdeque", source, bits, truth_table=table, settings=settings
        )
        assert esolangs.run("Bitdeque", filled, settings=settings) == expected


def test_cli_tui_uses_settings(tmp_path: Path, capsys):
    source = tmp_path / "conversion.grapheme"
    source.write_text("FAFY")
    with (
        patch("tests.test_cli._FakeStdin.isatty", return_value=True),
        patch("esolangs.cli_debug.run_tui") as run,
    ):
        assert call_both(
            [
                "debug",
                "--tui",
                "--settings",
                '{"integer_conversion":"after_each_letter"}',
                "Grapheme",
                str(source),
            ],
            capsys,
        ) == ("", "")
    assert run.call_args.kwargs["settings"] == DialectSettings(
        integer_conversion="after_each_letter"
    )


def test_empty_settings_preserve_termination(capsys):
    program, error = call_both(["generate", "--settings", "{}", "123", "01"], capsys)
    assert error == ""
    assert _evaluate("123", program, inputs=1, settings=DialectSettings()) == "01"
