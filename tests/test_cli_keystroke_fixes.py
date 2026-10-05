"""The CLI keystroke fixes: fewer retypes, plainer describe, kinder settings."""

import json

import pytest

import esolangs
from tests.cli_support import call_both


def _portable(tmp_path, language="brainfuck", table="0110", settings=None):
    program = esolangs.generate(language, table, settings=settings)
    path = tmp_path / "program.json"
    path.write_text(
        esolangs.dump_program(language, program, settings=settings), encoding="utf-8"
    )
    return path


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


def test_short_settings_and_portable_flags(capsys, tmp_path):
    output, error = call_both(
        [
            "generate",
            "-p",
            "-s",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert error == ""
    assert json.loads(output)["language"] == "Alight"
    path = tmp_path / "program.json"
    path.write_text(output, encoding="utf-8")
    output, error = call_both(["generate", "-p", "brainfuck", "0110"], capsys)
    assert error == ""
    path.write_text(output, encoding="utf-8")
    stdin = esolangs.encode_inputs("brainfuck", [1, 0], "0110")
    output, error = call_both(
        ["run", "-p", "-t", "0110", "--judge", str(path)], capsys, stdin
    )
    assert (output, error) == ("1\n", "")


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


@pytest.mark.parametrize("command", ["run", "debug"])
def test_portable_language_can_be_omitted(command, capsys, tmp_path):
    path = _portable(tmp_path)
    stdin = esolangs.encode_inputs("brainfuck", [1, 0], "0110")
    if command == "run":
        args = ["run", "--portable", "--judge", "--table", "0110", str(path)]
        expected = "1\n"
    else:
        args = ["debug", "--portable", "--steps", "100000", str(path)]
        expected = "halted: yes"
    output, error = call_both(args, capsys, stdin)
    assert expected in output
    assert error == ""


def test_describe_leads_with_the_contract(capsys):
    output, _error = call_both(["describe", "Fargo"], capsys)
    assert output.startswith("Fargo\ninput: one decimal row index")
    assert output.index("input:") < output.index("input_shape")
    assert "proof_status" not in output
    assert "{'labels'" not in output
    assert "Interpreter for Fargo" not in output
    assert "esolangs describe --spec Fargo" in output


def test_describe_template_still_hides_stdin_fields(capsys):
    output, _error = call_both(["describe", "Minifuck"], capsys)
    assert "input_shape" not in output
    assert "generate --bits" in output
