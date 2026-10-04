"""Balanced layouts and CLI sessions retain explicit dialect choices."""

from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.cli_debug import _run_tui_session
from esolangs.tools.alight.balance import _balance_postfix
from esolangs.tui import History, replay
from tests.cli_support import call_both


@pytest.mark.parametrize(
    ("language", "choices"),
    [
        ("Bitdeque", '{"index_base":1}'),
        ("Alight", '{"expression_syntax":"postfix"}'),
        ("Packlang", '{"literal_policy":"binary_digits"}'),
    ],
)
def test_cli_answer_uses_settings(language, choices, capsys):
    assert call_both(
        ["answer", "--settings", choices, language, "0110", "10"], capsys
    ) == ("1\n", "")


def test_cli_debug_uses_settings(tmp_path: Path, capsys):
    source = tmp_path / "eof.bf"
    source.write_text("+,.")
    output, _ = call_both(
        [
            "debug",
            "--settings",
            '{"eof":"unchanged"}',
            "--stdin",
            "",
            "Brainfuck",
            str(source),
        ],
        capsys,
    )
    assert "halted: yes" in output
    assert "output: '\\x01'" in output


@pytest.mark.parametrize("command", ["answer", "debug"])
def test_cli_settings_rejected_before_work(command, capsys):
    rest = ["Fargo", "01", "0"] if command == "answer" else ["Fargo", "missing"]
    with (
        patch("esolangs.cli_debug._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as exc,
    ):
        call_both([command, "--settings", '{"eof":"zero"}', *rest], capsys)
    assert exc.value.code == 2


def test_tui_settings_reach_wrapper():
    settings = DialectSettings(eof="zero")
    with patch("esolangs.cli_debug.run_tui") as run:
        _run_tui_session("Brainfuck", ",.", "", {}, None, settings)
    assert run.call_args.kwargs["settings"] is settings


def test_tui_replay_retains_settings():
    settings = DialectSettings(cell_modulus=2, eof="unchanged")
    history = History("Brainfuck", "++++,.", settings=settings)
    history.budget = 1
    final = history.at(6)
    assert final.output == "\x00"
    assert history.at(1).memory == (1,)
    assert history.at(2) == replay("Brainfuck", "++++,.", "", 2, settings=settings)


def test_postfix_balance_model_checks_rendering():
    with (
        patch("esolangs.tools.alight.balance._alight_folded", return_value="bad"),
        pytest.raises(AssertionError, match="postfix fold model"),
    ):
        _balance_postfix("0110", 2, "x" * 100)
    assert _balance_postfix("01", 1, "x") == "x"


@pytest.mark.parametrize("plain", [False, True])
def test_balanced_bitdeque_setters(plain):
    settings = DialectSettings(index_base=1)
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
    source = tmp_path / "eof.bf"
    source.write_text(",.")
    with (
        patch("tests.test_cli._FakeStdin.isatty", return_value=True),
        patch("esolangs.cli_debug.run_tui") as run,
    ):
        assert call_both(
            [
                "debug",
                "--tui",
                "--settings",
                '{"eof":"zero"}',
                "Brainfuck",
                str(source),
            ],
            capsys,
        ) == ("", "")
    assert run.call_args.kwargs["settings"] == DialectSettings(eof="zero")


@pytest.mark.parametrize("bit", ["0", "1"])
def test_cli_answer_empty_settings_preserve_termination(bit, capsys):
    assert call_both(["answer", "--settings", "{}", "123", "01", bit], capsys) == (
        bit + "\n",
        "",
    )
