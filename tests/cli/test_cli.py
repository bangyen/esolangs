"""Unit tests for the esolangs command-line interface."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from tests.cli_support import _FakeStdin, _program, _refused
from tests.pick import first

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
            patch.object(sys, "argv", ["esolangs", "generate", "Piet", "0110"]),
            patch.object(sys, "stdin", _FakeStdin("")),
        ):
            main()
        out = capsysbinary.readouterr().out
        assert out.startswith(b"\x89PNG\r\n\x1a\n")
        image = esolangs.Raster.from_png(out)
        assert esolangs.run("Piet", image, stdin="1\n0\n") == "1"

    def test_run_feeds_stdin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from esolangs import tools as boolean

        program = tmp_path / "prog.txt"
        program.write_text(boolean.circlefuck("1101"))
        out = call_main(["run", "Circlefuck", str(program)], capsys, stdin="10")
        assert out == "0"

    def test_run_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "Sophie"], capsys)
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
        pytest.param(["brainfuck", TABLE3, "--width", "20"], 20, True, id="value"),
        # The guard rejects zero and below, not one.
        pytest.param(["brainfuck", "0110", "--width", "1"], None, False, id="one"),
        # ``--width N`` consumes two arguments, not three.
        pytest.param(["--width", "20", "brainfuck", TABLE3], 20, True, id="first"),
        pytest.param(["brainfuck", TABLE3, "--width=20"], 20, False, id="equals"),
        # A bare ``--width`` wraps to the conventional default.
        pytest.param(["brainfuck", TABLE3, "--width"], "default", False, id="bare"),
        # A following word is an argument, not a width.
        pytest.param(["--width", "brainfuck", TABLE3], None, True, id="bare_first"),
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
    from esolangs.tools.wrap import DEFAULT_WIDTH

    out = call_main(["generate", *args], capsys)
    assert out.strip()
    if limit is not None:
        limit = DEFAULT_WIDTH if limit == "default" else limit
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= limit
        assert "\n" in out.rstrip("\n")
    if runs:
        assert esolangs.run("brainfuck", out, stdin="011") == "0"


# ``+.+.+.`` after an 8x8 loop prints A, B, C -- three separate writes, so a
# break on the second one has a run to stop in the middle of.
_ABC = "++++++++[>++++++++<-]>+.+.+."


@pytest.mark.parametrize(
    ("flags", "program", "expected"),
    [
        pytest.param([], _ABC, ["halted: yes", "output: 'ABC'"], id="runs_to_halt"),
        # A step budget stops the run short, which is the point of it.
        pytest.param(["--steps", "5"], _ABC, ["halted: no", "output: ''"], id="steps"),
        pytest.param(["--steps=5"], _ABC, ["halted: no"], id="steps_inline"),
        # The watch history is what the debugger adds over plain stepping.
        pytest.param(
            ["--steps", "3", "--watch-cell", "0"],
            _ABC,
            ["cell 0: [1, 2, 3]"],
            id="watch_cell",
        ),
        # A breakpoint is checked *before* a step, so ``B`` is the last byte.
        pytest.param(
            ["--break-on-output", "B"],
            _ABC,
            ["halted: no", "output: 'AB'"],
            id="break_on_output",
        ),
        pytest.param(
            ["--break-at", "3"], "+++++", ["ip: 3", "halted: no"], id="break_at"
        ),
        pytest.param(
            ["--break-on-cell", "0=3", "--watch-cell", "0"],
            "+++++",
            ["cell 0: [1, 2, 3]"],
            id="break_on_cell",
        ),
        # A short watch history is printed whole.
        pytest.param(
            ["--watch-cell", "0"], "+++", ["cell 0: [1, 2, 3]"], id="short_watch"
        ),
    ],
)
def test_debug_report(
    flags: list[str],
    program: str,
    expected: list[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``esolangs debug`` exposes the breakpoint/watch VM on the CLI."""
    out = call_main(["debug", *flags, "brainfuck", _program(tmp_path, program)], capsys)
    for line in expected:
        assert line in out


class TestDebugCommand:
    def test_a_raise_is_reported_rather_than_propagated(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A debugged program is one the caller is already unsure of."""
        # Reported, not propagated -- the whole report is printed -- and
        # *then* exit 1, matching what `run` has always called a program's
        # own failure.  `debug` used to exit 0 for every outcome alike, so
        # a script could not tell a crash from a clean halt.
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", _program(tmp_path, ",.")], capsys)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "raised: InputExhaustedError" in out
        assert "0 characters supplied" in out
        assert "halted: no" in out


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

    @pytest.mark.parametrize("command", ["list", "generate", "run", "debug"])
    def test_each_command_expands_its_own_options(
        self, command: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``debug --help`` used to print its usage line and stop there."""
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--help"], capsys)
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert f"usage: esolangs {command}" in out
        assert len(out.splitlines()) > 3, "a usage line alone is not help"

    def test_debug_help_names_every_option_it_takes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            call_main(["debug", "--help"], capsys)
        out = capsys.readouterr().out
        for option in ("--steps", "--watch-cell", "--break-on-output"):
            assert option in out


# Each case generates a program and runs it through a real subprocess --
# 22.3s over nine tests, the fast band's single largest class.
@pytest.mark.medium
class TestProgramFailuresAreReported:
    """An interpreter's failure is a message and an exit code, not a stack."""

    def test_reading_past_the_input_is_a_clean_message(self, tmp_path: Path) -> None:
        """The traceback leaked src/ paths and an empty EOFError message."""
        result = run_cli("run", "brainfuck", str(_program(tmp_path, ",.")), stdin="")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "read past the end of input" in result.stderr

    def test_an_unfilled_template_is_refused_by_name(self, tmp_path: Path) -> None:
        """Minifuck ran it and printed a confident wrong answer."""
        generated = run_cli("generate", "Minifuck", "0110")
        path = tmp_path / "mf.txt"
        path.write_text(generated.stdout.rstrip("\n"))
        result = run_cli("run", "Minifuck", str(path))
        assert result.returncode == 2
        assert "unfilled runs of '$'" in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.slow
    def test_the_readme_suffolk_flow_completes(self, tmp_path: Path) -> None:
        """Generate then run, the README's first pair, for all four rows."""
        generated = run_cli("generate", "Suffolk", "0110")
        path = tmp_path / "su.txt"
        path.write_text(generated.stdout.rstrip("\n"))
        got = "".join(
            run_cli(
                "run",
                "Suffolk",
                str(path),
                stdin=esolangs.encode_inputs("Suffolk", [a, b]),
            ).stdout
            for a in (0, 1)
            for b in (0, 1)
        )
        assert got == "0110"


class TestOutputAndAbridging:
    """The two output conventions: byte-exact when piped, readable when not."""

    def test_a_trailing_newline_is_added_only_for_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Piped output is compared and diffed, so it stays byte-exact."""
        program = _program(tmp_path, "+.")
        with patch.object(sys.stdout, "isatty", lambda: True):
            assert call_main(["run", "brainfuck", str(program)], capsys) == "\x01\n"
        assert call_main(["run", "brainfuck", str(program)], capsys) == "\x01"

    def test_a_long_watch_history_is_abridged(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It was one line of 486 values, which buries the ends."""
        program = _program(tmp_path, "+" * 200)
        out = call_main(
            ["debug", "--watch-cell", "0", "brainfuck", str(program)], capsys
        )
        assert "more ..." in out
        assert len(out.splitlines()[-1]) < 400


class TestGenerateArgumentTypes:
    """``generate``'s own arguments are checked before a generator runs."""

    def test_a_non_integer_width_from_the_api_is_refused(self) -> None:
        """The CLI parses its width; a Python caller can pass anything."""
        with pytest.raises(ValueError, match="width must be an integer"):
            esolangs.generate("brainfuck", "0110", width="80")  # type: ignore[arg-type]


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
    "unknown_language": ("debug NoSuchLanguage prog:+", "unknown language"),
    "missing_file": ("debug brainfuck /no/such/file", "cannot read"),
    "missing_args": ("debug brainfuck", "usage: esolangs debug"),
    "a_non_integer_option_is_refused---steps": (
        "debug --steps x brainfuck prog:+",
        "must be an integer",
    ),
    "a_non_integer_option_is_refused---watch-cell": (
        "debug --watch-cell x brainfuck prog:+",
        "must be an integer",
    ),
    "an_option_with_no_value_is_refused": (
        "debug brainfuck prog.b --steps",
        "--steps needs a value",
    ),
    "a_malformed_cell_breakpoint_is_refused-x=1": (
        "debug --break-on-cell=x=1 brainfuck prog:+",
        "INDEX=VALUE",
    ),
    "a_malformed_cell_breakpoint_is_refused-0=y": (
        "debug --break-on-cell=0=y brainfuck prog:+",
        "INDEX=VALUE",
    ),
    "a_non_integer_break_at_is_refused": (
        "debug --break-at x brainfuck prog:+",
        "must be an integer",
    ),
    "a_negative_cell_breakpoint_index_is_refused": (
        "debug --break-on-cell=-1=3 brainfuck prog:+",
        "index must not be negative",
    ),
    "removed_tui_is_refused": (
        "debug --tui brainfuck prog:+",
        "unknown option: --tui",
    ),
    "an_unknown_option_is_named": (
        "debug --frobnicate brainfuck prog:+",
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
    "a_negative_watch_cell_is_refused": (
        "debug --watch-cell -1 brainfuck prog:+++",
        "must not be negative",
    ),
    "encode_refuses_a_language_that_reads_nothing": (
        f"encode {TEMPLATED!r} 01",
        "reads no stdin",
    ),
    "a_repeated_option_is_refused": (
        f"generate --bits 10 --bits 01 {TEMPLATED!r} 0110",
        "more than once",
    ),
    "encode_refuses_a_non_binary_bit_string": ("encode brainfuck 2x", "0s and 1s"),
    "an_empty_break_on_output_is_refused": (
        "debug --break-on-output '' brainfuck prog:+++",
        "needs some text",
    ),
    "read_answer_says_so_when_given_nothing": (
        "read-answer brainfuck",
        "nothing on stdin",
    ),
    "a_negative_step_bound_is_refused": (
        "debug --steps -1 brainfuck prog:+",
        "must not be negative",
    ),
    "a_negative_break_at_is_refused": (
        "debug --break-at -1 brainfuck prog:+",
        "--break-at must not be negative",
    ),
    "a_swallowed_table_is_named": ("generate brainfuck --width 0110", "--width"),
}


@pytest.mark.parametrize("case", _REFUSALS.values(), ids=list(_REFUSALS))
def test_a_bad_command_exits_2_and_says_why(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message in _refused(command, tmp_path, capsys, *stdin)
