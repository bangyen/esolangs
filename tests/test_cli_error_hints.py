"""CLI hints survive rendering and suggest usable shell inputs."""

from pathlib import Path

import pytest

import esolangs
from tests.cli_support import call_both


def _failure(args: list[str], capsys: pytest.CaptureFixture[str], code: int = 2):
    with pytest.raises(SystemExit) as caught:
        call_both(args, capsys)
    assert caught.value.code == code
    captured = capsys.readouterr()
    return captured.out, captured.err


@pytest.mark.parametrize(
    ("bad", "good", "hint"),
    [
        ("0120", "0110", "without spaces or separators"),
        ("010", "0110", "two inputs need four"),
        ("1", "11", "constant with one input"),
    ],
)
def test_truth_table_hint_and_corrected_cli_program(bad, good, hint, tmp_path, capsys):
    out, err = _failure(["generate", "brainfuck", bad], capsys)
    assert out == ""
    assert err.count("hint:") == 1
    assert hint in err
    program, err = call_both(["generate", "brainfuck", good], capsys)
    assert err == ""
    path = tmp_path / "generated.bf"
    path.write_text(program)
    bits = "01" if len(good) == 4 else "0"
    stdin, err = call_both(["encode", "brainfuck", bits], capsys)
    assert err == ""
    answer, err = call_both(["run", "brainfuck", str(path)], capsys, stdin)
    assert answer.strip() == "1"
    assert err == ""


def test_template_hint_names_cli_bits_and_correction_runs(tmp_path, capsys):
    _, err = _failure(["generate", "--bits", "0", "Minifuck", "0110"], capsys)
    assert "hint: pass exactly 2 0/1 digits to --bits, one per input" in err
    assert "instantiate()" not in err
    program, err = call_both(["generate", "--bits", "01", "Minifuck", "0110"], capsys)
    assert err == ""
    path = tmp_path / "generated.mini"
    path.write_text(program)
    answer, err = call_both(["run", "Minifuck", str(path)], capsys)
    assert answer.strip() == "1"
    assert err == ""


def test_reader_template_hint_names_cli_encode(capsys):
    _, err = _failure(["generate", "--bits", "01", "brainfuck", "0110"], capsys)
    assert "hint: pipe input from esolangs encode brainfuck <bits>" in err
    assert "stdin=encode_inputs" not in err


def test_timeout_hint_names_cli_flag_and_correction_runs(tmp_path, capsys):
    path = tmp_path / "program.bf"
    path.write_text("+.")
    _, err = _failure(["run", "--timeout", "0", "brainfuck", str(path)], capsys)
    assert err.startswith("--timeout must be positive, got 0.0\n")
    assert "hint: set a timeout in seconds, for example --timeout 5.0" in err
    output, err = call_both(["run", "--timeout", "5.0", "brainfuck", str(path)], capsys)
    assert output == "\x01"
    assert err == ""


def test_generator_cap_hint_reaches_cli(capsys):
    _, err = _failure(["generate", "Befunge", "0010" * (1 << 12)], capsys)
    assert "fixed 80x25 grid" in err
    assert err.count("hint:") == 1


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "hint", "code", "output"),
    [
        ("brainfuck", "[", "close this '[' with ']'", 2, ""),
        ("Modulous", "[PSH INT 65][PRT][SWP]", "push two values before SWP", 1, "A\n"),
        ("brainfuck", "+.,", "at least 1 input character", 1, "\x01\n"),
    ],
)
def test_isolated_cli_preserves_error_hint_and_partial_output(
    language, source, hint, code, output, tmp_path: Path, capsys
):
    path = tmp_path / "program.txt"
    path.write_text(source)
    direct = _failure(["run", language, str(path)], capsys, code)
    isolated = _failure(["run", "--isolated", language, str(path)], capsys, code)
    assert direct == isolated
    assert direct[0] == output
    assert hint in direct[1]
    assert direct[1].count("hint:") == 1


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "kind"),
    [
        ("brainfuck", "[", esolangs.ProgramError),
        ("Modulous", "[SWP]", esolangs.HaltError),
        ("brainfuck", ",", esolangs.InputExhaustedError),
    ],
)
def test_isolated_worker_preserves_exact_diagnostic_and_notes(language, source, kind):
    errors = []
    for isolated in (False, True):
        with pytest.raises(kind) as caught:
            esolangs.run(language, source, isolated=isolated)
        errors.append(caught.value)
    assert type(errors[0]) is type(errors[1])
    assert str(errors[0]) == str(errors[1])
    assert errors[0].__notes__ == errors[1].__notes__
    if kind is esolangs.InputExhaustedError:
        assert errors[0].unit == errors[1].unit == "character"
    assert sum(note.startswith("hint:") for note in errors[1].__notes__) == 1


def test_cli_note_translation_preserves_multiline_diagnostic_and_api_notes():
    from esolangs.cli_hints import _cli_error_text

    error = esolangs.ArgumentError("bad timeout=5.0\nscale=1")
    error.add_note("hint: set timeout=5.0 or scale=1")
    error.add_note("unrelated context")
    assert _cli_error_text(error) == (
        "bad timeout=5.0\nscale=1\nhint: set --timeout 5.0 or --scale 1"
    )
    assert error.__notes__ == ["hint: set timeout=5.0 or scale=1", "unrelated context"]


def test_text_generator_scale_hint_uses_cli_flag(capsys):
    _, err = _failure(["generate", "--scale", "2", "brainfuck", "0110"], capsys)
    assert "hint: omit --scale for text languages" in err


def test_template_rewording_keeps_notes_and_quotes_language():
    from esolangs.cli_hints import _template_hint

    error = esolangs.TemplateError(
        "unfilled slots; fill them with esolangs.instantiate("
    )
    error.add_note("hint: keep the original template")
    assert _template_hint(error, "A Painter Ant") == (
        "unfilled slots; fill them with: esolangs generate --bits <bits> "
        '"A Painter Ant" <table>\nhint: keep the original template'
    )
