"""Unit tests for the esolangs command-line interface."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from esolangs.registry import LANGUAGES
from tests.support.cli_support import _FakeStdin, _program, _refused
from tests.support.pick import first
from tests.support.reference import REFERENCE

_RASTER = first(source_kind="raster", boolean_generator=True)
_GZIP = next(n for n, lang in LANGUAGES.items() if lang.compressed_source)

RASTER = first(source_kind="raster", boolean_generator=True)
TEMPLATED = first(parameterized=True)

# A 3-input parity table.  Parity depends on every input, so the program is
# long enough to have something to wrap -- an echo-one-input table folds
# down to a few characters and the width options below would be no-ops.
TABLE3 = "01101001"


def run_cli(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "esolangs.cli", *args],
        capture_output=True,
        text=True,
        input=stdin,
    )


def call_main(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> str:
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    return str(capsys.readouterr().out)


class TestInProcess:
    def test_generating_a_raster_writes_png_bytes(
        self, capsysbinary: pytest.CaptureFixture[bytes]
    ) -> None:
        """Raster ``generate`` writes the image to the byte stream."""
        with (
            patch.object(sys, "argv", ["esolangs", "generate", _RASTER, "0110"]),
            patch.object(sys, "stdin", _FakeStdin("")),
        ):
            main()
        out = capsysbinary.readouterr().out
        assert out.startswith(b"\x89PNG\r\n\x1a\n")
        image = esolangs.Raster.from_png(out)
        stdin = esolangs.encode_inputs(_RASTER, [1, 0])
        assert (
            esolangs.read_answer(_RASTER, esolangs.run(_RASTER, image, stdin=stdin))
            == "1"
        )

    def test_an_oversized_scale_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It rendered outside the error handler: internal error, exit 70."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--scale", "999999999", _RASTER, "0110"], capsys)
        assert exc.value.code == 2
        assert "pixel limit" in capsys.readouterr().err

    @pytest.mark.parametrize("closed_streams", ["stdout", "both"])
    def test_a_closed_stdout_object_exits_120(self, closed_streams: str) -> None:
        """A closed stream object exited 70 (or raised, stderr closed too)."""
        import io

        closed = io.TextIOWrapper(io.BytesIO())
        closed.close()
        with (
            patch.object(sys, "argv", ["esolangs", "list"]),
            patch.object(sys, "stdout", closed),
            patch.object(
                sys, "stderr", closed if closed_streams == "both" else io.StringIO()
            ),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 120

    def test_help_for_an_unknown_command_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`help zzz` printed the usage and exited 0."""
        with pytest.raises(SystemExit) as exc:
            call_main(["help", "zzz"], capsys)
        assert exc.value.code == 2
        assert "unknown command: zzz" in capsys.readouterr().err

    def test_partial_output_on_a_pipe_is_byte_exact(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A failed run added "\\n" to a pipe, against `run --help`."""
        path = tmp_path / "p.txt"
        path.write_text("+.,")
        with pytest.raises(SystemExit):
            call_main(["run", REFERENCE, str(path)], capsys)
        assert capsys.readouterr().out == "\x01"

    def test_max_memory_names_the_flags(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "p.txt"
        path.write_text("+")
        with pytest.raises(SystemExit):
            call_main(["run", "--max-memory", "1000", REFERENCE, str(path)], capsys)
        assert "--max-memory requires --isolated" in capsys.readouterr().err

    def test_spec_json_is_the_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--spec --json`` printed every fact, ignoring ``--spec``."""
        out = call_main(["describe", "--spec", "--json", REFERENCE], capsys)
        assert json.loads(out) == esolangs.describe(REFERENCE)["spec"]

    def test_run_feeds_stdin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.txt"
        program.write_text(esolangs.generate(REFERENCE, "1101"))
        stdin = esolangs.encode_inputs(REFERENCE, [1, 0])
        out = call_main(["run", REFERENCE, str(program)], capsys, stdin=stdin)
        assert esolangs.read_answer(REFERENCE, out) == "0"

    def test_run_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", REFERENCE], capsys)
        assert exc.value.code == 2

    def test_run_unknown_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.txt"
        program.write_text("anything")
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "NoSuchLanguage", str(program)], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main([], capsys)
        assert exc.value.code == 2


@pytest.mark.parametrize(
    ("args", "limit", "runs"),
    [
        # ``--width N`` bounds the generated program's columns.
        pytest.param([REFERENCE, TABLE3, "--width", "20"], 20, True, id="value"),
        # The guard rejects zero and below, not one.
        pytest.param([REFERENCE, "0110", "--width", "1"], None, False, id="one"),
        # ``--width N`` consumes two arguments, not three.
        pytest.param(["--width", "20", REFERENCE, TABLE3], 20, True, id="first"),
        pytest.param([REFERENCE, TABLE3, "--width=20"], 20, False, id="equals"),
        # A bare ``--width`` wraps to the conventional default.
        pytest.param([REFERENCE, TABLE3, "--width"], "default", False, id="bare"),
        # A following word is an argument, not a width.
        pytest.param(["--width", REFERENCE, TABLE3], None, True, id="bare_first"),
    ],
)
def test_width_option(
    args: list[str],
    limit: int | str | None,
    capsys: pytest.CaptureFixture[str],
    *,
    runs: bool,
) -> None:
    """``--width`` in all the spellings the parser accepts."""
    from esolangs.generation.wrap import DEFAULT_WIDTH

    out = call_main(["generate", *args], capsys)
    assert out.strip()
    if limit is not None:
        limit = DEFAULT_WIDTH if limit == "default" else limit
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= limit
        assert "\n" in out.rstrip("\n")
    if runs:
        assert esolangs.run(REFERENCE, out, stdin="011") == "0"


class TestHelp:
    """Every command documents itself, because `--help` is what gets typed."""

    @pytest.mark.parametrize("flag", ["--help", "-h", "help"])
    def test_the_top_level_flag_is_not_an_unknown_command(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It used to exit 2 with ``unknown command: --help``."""
        with pytest.raises(SystemExit) as exc:
            call_main([flag], capsys)
        assert exc.value.code == 0
        assert "usage: esolangs <command>" in capsys.readouterr().out

    @pytest.mark.parametrize("command", ["list", "generate", "run"])
    def test_each_command_expands_its_own_options(
        self, command: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``--help`` used to print its usage line and stop there."""
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--help"], capsys)
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert f"usage: esolangs {command}" in out
        assert len(out.splitlines()) > 3, "a usage line alone is not help"


# Each case generates a program and runs it through a real subprocess --
# 22.3s over nine tests, the fast band's single largest class.
@pytest.mark.medium
class TestProgramFailuresAreReported:
    """An interpreter's failure is a message and an exit code, not a stack."""

    def test_reading_past_the_input_is_a_clean_message(self, tmp_path: Path) -> None:
        """The traceback leaked src/ paths and an empty EOFError message."""
        result = run_cli("run", REFERENCE, str(_program(tmp_path, ",.")), stdin="")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "read past the end of input" in result.stderr

    def test_an_unfilled_template_is_refused_by_name(self, tmp_path: Path) -> None:
        """An unfilled run once ran, and printed a confident wrong answer."""
        name = first(parameterized=True, boolean_generator=True)
        generated = run_cli("generate", name, "0110")
        path = tmp_path / "template.txt"
        path.write_text(generated.stdout.rstrip("\n"))
        result = run_cli("run", name, str(path))
        assert result.returncode == 2
        char = esolangs.generate(name, "0110").char
        assert f"unfilled runs of {char!r}" in result.stderr
        assert "Traceback" not in result.stderr


class TestOutputAndAbridging:
    """The two output conventions: byte-exact when piped, readable when not."""

    def test_a_trailing_newline_is_added_only_for_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Piped output is compared and diffed, so it stays byte-exact."""
        program = _program(tmp_path, "+.")
        with patch.object(sys.stdout, "isatty", lambda: True):
            assert call_main(["run", REFERENCE, str(program)], capsys) == "\x01\n"
        assert call_main(["run", REFERENCE, str(program)], capsys) == "\x01"

    def test_binary_programs_refuse_a_terminal(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PNG and gzip bytes went to the terminal unannounced."""
        with patch.object(sys.stdout, "isatty", lambda: True):
            for args in (["generate", _RASTER, "0110"], ["generate", _GZIP, "01"]):
                with pytest.raises(SystemExit) as exit_:
                    call_main(args, capsys)
                assert exit_.value.code == 2
                assert "redirect stdout" in capsys.readouterr().err


class TestGenerateArgumentTypes:
    """``generate``'s own arguments are checked before a generator runs."""

    def test_a_non_integer_width_from_the_api_is_refused(self) -> None:
        """The CLI parses its width; a Python caller can pass anything."""
        with pytest.raises(ValueError, match="width must be an integer"):
            esolangs.generate(REFERENCE, "0110", width="80")


#: Commands refused with exit code 2, and what stderr must say.
#: ``prog:SRC`` is a file holding SRC; a third item is stdin.
_REFUSALS = {
    "generate_bits_refuses_a_raster": (
        f"generate {RASTER} 0110 --bits 01",
        "raster programs read bits",
    ),
    "generate_unknown_language": ("generate NoSuchLanguage 01", "unknown language"),
    "run_missing_file": ("run brainfuck /no/such/file", "cannot read"),
    "unknown_command": ("no.such.command", "unknown command"),
    "width_rejects_a_non_integer_after_equals": (
        f"generate brainfuck {TABLE3} --width=x",
        "must be an integer",
    ),
    "width_rejects_a_non_positive_value-0": (
        f"generate brainfuck {TABLE3} --width 0",
        "must be positive",
    ),
    "unknown_language": ("run NoSuchLanguage prog:+", "unknown language"),
    "missing_args": ("run brainfuck", "usage: esolangs run"),
    "an_option_with_no_value_is_refused": (
        "run brainfuck prog.b --timeout",
        "--timeout needs a value",
    ),
    "removed_debug_is_refused": ("debug brainfuck prog:+", "unknown command"),
    "an_unknown_option_is_named": (
        "run --frobnicate brainfuck prog:+",
        "unknown option: --frobnicate",
    ),
    "an_extra_argument_is_refused": (
        f"generate brainfuck {TABLE3} extra",
        "unexpected argument: 'extra'",
    ),
    "a_repeated_width_quotes_its_value": (
        "generate --width 77 --width 33 brainfuck 0110",
        "first was '77'",
    ),
    "a_missing_argument_is_named": ("generate brainfuck", "missing <truth-table>"),
    "swapped_arguments_are_recognized_as_swapped": (
        "generate 0110 brainfuck",
        "looks like a truth table",
    ),
    "a_misspelled_option_is_suggested": (
        "generate --wdith 40 brainfuck 0110",
        "did you mean --width",
    ),
    "read_answer_reports_an_unknown_language": (
        "read-answer Nonexistent",
        "unknown language",
        "1",
    ),
    "read_answer_reports_an_unreadable_output": (
        "read-answer brainfuck",
        "no answer this could read",
        "no digits here!",
    ),
    "a_genuine_extra_argument_still_says_so": (
        "describe brainfuck zzz",
        "unexpected argument",
    ),
    "an_unknown_subcommand_is_suggested": ("lst", "did you mean list"),
    "encode_refuses_a_language_that_reads_nothing": (
        f"encode {TEMPLATED!r} 01",
        "reads no stdin",
    ),
    "a_repeated_option_is_refused": (
        f"generate --bits 10 --bits 01 {TEMPLATED!r} 0110",
        "more than once",
    ),
    "encode_refuses_a_non_binary_bit_string": ("encode brainfuck 2x", "0s and 1s"),
    "read_answer_says_so_when_given_nothing": (
        "read-answer brainfuck",
        "nothing on stdin",
    ),
    "a_swallowed_table_is_named": ("generate brainfuck --width 0110", "--width"),
}


@pytest.mark.parametrize("case", _REFUSALS.values(), ids=list(_REFUSALS))
def test_a_bad_command_exits_2_and_says_why(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message in _refused(command, tmp_path, capsys, *stdin)
