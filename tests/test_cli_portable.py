"""CLI disk round trips retain dialect choices without repeated options."""

import ast
import json
import sys
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.tagged import _Tagged
from esolangs.tui import History, replay
from tests.cli_support import call_both
from tests.test_cli import _FakeStdin
from tests.test_public_dialects import CASES


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
@pytest.mark.parametrize("balance", [False, True])
def test_portable_generation_restores_every_row(
    tmp_path, capsys, language, settings, balance
):
    path = save_generated(
        tmp_path, capsys, language, settings, *(["--balance"] if balance else [])
    )
    restored = esolangs.load_program(language, path.read_text(encoding="utf-8"))
    assert restored.settings == settings
    assert _evaluate(language, restored, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
def test_run_and_debug_restored_program(tmp_path, capsys, language, settings):
    embedded = esolangs.describe(language)["parameterized"]
    path = save_generated(
        tmp_path, capsys, language, settings, *(["--bits", "10"] if embedded else [])
    )
    stdin = "" if embedded else esolangs.encode_inputs(language, [1, 0], "0110")
    output, error = call_both(
        [
            "run",
            "--portable",
            "--judge",
            "--table",
            "0110",
            "--timeout",
            "10",
            language,
            str(path),
        ],
        capsys,
        stdin,
    )
    assert (output, error) == ("1\n", "")
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
@pytest.mark.parametrize("scale", [1, 2])
def test_cli_scaled_raster(tmp_path, capsys, scale):
    settings = DialectSettings()
    path = save_generated(tmp_path, capsys, "Line", settings, "--scale", str(scale))
    restored = esolangs.load_program("Line", path.read_text(encoding="utf-8"))
    assert _evaluate("Line", restored, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Alight", "Packlang", "Grapheme"])
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
            "--judge",
            "--table",
            "01",
            language,
            str(path),
        ],
        capsys,
        stdin,
    )
    assert (output, error) == ("1\n", "")


@pytest.mark.medium
@pytest.mark.parametrize("command", ["run", "debug"])
def test_partial_override_inherits_cell_modulus(tmp_path, capsys, command):
    source = _Tagged(
        "SEED " * 255 + "DIGEST PRONOUNCE",
        "SLOW ACV MAMMALIAN",
        DialectSettings(cell_modulus=256, io_modulus=255),
    )
    path = tmp_path / "program.json"
    path.write_text(
        esolangs.dump_program("SLOW ACV MAMMALIAN", source), encoding="utf-8"
    )
    output, error = call_both(
        [
            command,
            "--portable",
            "--settings",
            '{"io_modulus":256}',
            "SLOW ACV MAMMALIAN",
            str(path),
        ],
        capsys,
    )
    assert error == ""
    if command == "run":
        assert output == chr(255)
    else:
        assert "halted: yes" in output
        assert "output: 'ÿ'" in output


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


@pytest.mark.medium
@pytest.mark.parametrize("override", [None, "between_letters"])
def test_tui_replay_preserves_restored_choices(tmp_path, capsys, monkeypatch, override):
    source = _Tagged(
        "FAFYPPPP", "Grapheme", DialectSettings(integer_conversion="after_each_letter")
    )
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program("Grapheme", source), encoding="utf-8")
    monkeypatch.setattr(_FakeStdin, "isatty", lambda _self: True)
    options = (
        []
        if override is None
        else ["--settings", json.dumps({"integer_conversion": override})]
    )
    with patch("esolangs.cli_debug.run_tui") as screen:
        call_both(
            [
                "debug",
                "--portable",
                "--tui",
                "--stdin",
                "",
                *options,
                "Grapheme",
                str(path),
            ],
            capsys,
        )
    language, restored, stdin = screen.call_args.args
    assert restored.settings == source.settings
    settings = screen.call_args.kwargs.get("settings")
    history = History(language, restored, stdin, settings=settings)
    history.budget = 1
    assert history.at(8).output == ("10" if override is None else "1")
    assert history.retained < history.top
    assert history.at(4) == replay(language, restored, stdin, 4, settings=settings)
    assert history.at(4).output == ("10" if override is None else "1")


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


@pytest.mark.medium
def test_portable_choices_and_memory_budget_reach_worker(tmp_path, capsys, monkeypatch):
    command = "run"
    from esolangs import _isolated

    budget = 96 * 1024 * 1024
    source = esolangs.generate(
        "Grapheme",
        "01",
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program("Grapheme", source), encoding="utf-8")
    monkeypatch.setattr(_isolated.sys, "platform", "linux")
    calls = []
    runner = vars(esolangs)["_run_isolated"]

    def capture(*args, **kwargs):
        # Check dispatch on every host; the separate Linux test enforces the cap.
        calls.append(kwargs.pop("max_memory"))
        assert kwargs["settings"] == source.settings
        return runner(*args, **kwargs)

    monkeypatch.setattr(esolangs, "_run_isolated", capture)
    options = ["--isolated"]
    output, error = call_both(
        [
            command,
            "--portable",
            *options,
            "--max-memory",
            str(budget),
            "Grapheme",
            str(path),
        ],
        capsys,
        esolangs.encode_inputs("Grapheme", [1]),
    )
    assert (output, error) == ("1", "")
    assert calls == [budget]


def test_portable_memory_budget_rejected_before_file_read(capsys):
    command = "run"
    module = "cli_run"
    options = ["--isolated"]
    with (
        patch(f"esolangs.{module}._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(
            [
                command,
                "--portable",
                *options,
                "--max-memory",
                "0",
                "Brainfuck",
                "never-read.json",
            ],
            capsys,
        )
    assert caught.value.code == 2
    assert "max_memory must be positive" in capsys.readouterr().err


@pytest.mark.medium
@pytest.mark.skipif(sys.platform != "linux", reason="Linux RLIMIT_AS only")
def test_portable_program_executes_with_real_memory_cap(tmp_path, capsys):
    command = "run"
    source = esolangs.generate(
        "Grapheme",
        "01",
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program("Grapheme", source), encoding="utf-8")
    options = ["--isolated"]
    output, error = call_both(
        [
            command,
            "--portable",
            *options,
            "--max-memory",
            str(96 * 1024 * 1024),
            "Grapheme",
            str(path),
        ],
        capsys,
        esolangs.encode_inputs("Grapheme", [1]),
    )
    assert (output, error) == ("1", "")
