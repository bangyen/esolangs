"""CLI disk round trips retain dialect choices without repeated options."""

import ast
import json
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.tagged import _Tagged
from tests.cli_support import call_both
from tests.test_dialects import CASES


def save_generated(tmp_path, capsys, language, settings, *options, table="0110"):
    output, error = call_both(
        [
            "generate",
            "--portable",
            "--settings",
            json.dumps(settings.options(language)),
            *options,
            language,
            table,
        ],
        capsys,
    )
    assert error == ""
    path = tmp_path / "program.json"
    path.write_text(output, encoding="utf-8")
    return path


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
def test_run_and_debug_restored_program(tmp_path, capsys, language, settings):
    embedded = esolangs.describe(language)["parameterized"]
    path = save_generated(
        tmp_path, capsys, language, settings, *(["--bits", "10"] if embedded else [])
    )
    stdin = (
        "" if embedded else esolangs.encode_inputs(language, [1, 0], truth_table="0110")
    )
    output, error = call_both(
        [
            "run",
            "--portable",
            "--timeout",
            "10",
            language,
            str(path),
        ],
        capsys,
        stdin,
    )
    assert esolangs.read_answer(language, output) == "1"
    assert error == ""
    output, error = call_both(
        [
            "debug",
            "--portable",
            "--steps",
            "100000",
            "--stdin",
            stdin,
            language,
            str(path),
        ],
        capsys,
    )
    assert "halted: yes\n" in output
    assert "stopped: halted\n" in output
    assert "raised:" not in output
    assert error == ""
    # Some dialects print a final state; judge the debugger's raw output too.
    raw = output.split("output: ", 1)[1].splitlines()[0]
    assert esolangs.read_answer(language, ast.literal_eval(raw)) == "1"


@pytest.mark.medium
@pytest.mark.parametrize("language", [name for name, _ in CASES])
def test_portable_isolated_cli(tmp_path, capsys, language):
    settings = dict(CASES)[language]
    path = save_generated(tmp_path, capsys, language, settings, table="01")
    source = esolangs.load_program(language, path.read_text(encoding="utf-8"))
    assert _evaluate(language, source, inputs=1, isolated=True, max_output=16) == "01"
    if esolangs.describe(language)["parameterized"]:
        source = esolangs.instantiate(language, source, [1])
        stdin = ""
    else:
        stdin = esolangs.encode_inputs(language, [1])
    path.write_text(esolangs.dump_program(language, source), encoding="utf-8")
    output, error = call_both(
        [
            "run",
            "--portable",
            "--isolated",
            language,
            str(path),
        ],
        capsys,
        stdin,
    )
    assert esolangs.read_answer(language, output) == "1"
    assert error == ""


@pytest.mark.parametrize("command", ["run", "debug"])
@pytest.mark.parametrize(
    "choices",
    [
        {"tape_size": None, "boundary": "wrap"},
        {"expression_syntax": "postfix"},
    ],
)
def test_invalid_overrides_fail_before_stdin(tmp_path, capsys, command, choices):
    source = _Tagged("+.", "brainfuck", DialectSettings())
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program("Brainfuck", source), encoding="utf-8")
    with (
        patch(
            f"esolangs.cli_{'run' if command == 'run' else 'debug'}._read_stdin",
            side_effect=AssertionError("read stdin"),
        ),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(
            [
                command,
                "--portable",
                "--settings",
                json.dumps(choices),
                "Brainfuck",
                str(path),
            ],
            capsys,
        )
    assert caught.value.code == 2
    assert "dialect setting" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "debug"])
@pytest.mark.parametrize("content", [b"\xff", b"{}", b"not json"])
def test_bad_portable_files_report_without_traceback(
    tmp_path, capsys, command, content
):
    path = tmp_path / "program.json"
    path.write_bytes(content)
    with pytest.raises(SystemExit) as caught:
        call_both([command, "--portable", "Brainfuck", str(path)], capsys)
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "portable program" in error
    assert "Traceback" not in error


@pytest.mark.parametrize("command", ["generate", "run", "debug"])
def test_duplicate_portable_flag(command, capsys):
    with pytest.raises(SystemExit) as caught:
        call_both([command, "--portable", "--portable"], capsys)
    assert caught.value.code == 2
    assert "--portable given more than once" in capsys.readouterr().err


@pytest.mark.medium
def test_raw_file_named_portable_flag(tmp_path, capsys, monkeypatch):
    (tmp_path / "--portable").write_text("+.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    output, error = call_both(["run", "--", "Brainfuck", "--portable"], capsys)
    assert (output, error) == ("\x01", "")


@pytest.mark.parametrize("command", ["run", "debug"])
def test_unknown_portable_language_fails_before_file_read(command, capsys):
    module = f"cli_{command}"
    with (
        patch(f"esolangs.{module}._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both([command, "--portable", "NotALang", "never-read.json"], capsys)
    assert caught.value.code == 2
    assert "unknown language" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "debug"])
@pytest.mark.parametrize("explicit", [False, True])
def test_portable_source_acquired_once(command, explicit, capsys):
    payload = esolangs.dump_program("brainfuck", "+.").encode()
    with patch("esolangs.cli_io._bounded_read", side_effect=[payload]) as read:
        args = [command, "--portable", "--timeout", "0.5"]
        if explicit:
            args.append("brainfuck")
        output, error = call_both([*args, "one-shot.json"], capsys)
    read.assert_called_once_with("one-shot.json", 0.5)
    assert error == ""
    assert output
