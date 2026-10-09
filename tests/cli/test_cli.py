"""Unit tests for the esolangs command-line interface."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from tests.cli_support import _FakeStdin, _program, _refused

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


class TestWidthOption:
    """``--width`` in all the spellings the parser accepts."""

    def test_width_with_a_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--width N`` bounds the generated program's columns."""
        out = call_main(["generate", "brainfuck", TABLE3, "--width", "20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20
        assert esolangs.run("brainfuck", out, stdin="011") == "0"

    def test_a_width_of_one_is_positive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The guard rejects zero and below, not one."""
        out = call_main(["generate", "brainfuck", "0110", "--width", "1"], capsys)
        assert out.strip()

    def test_the_option_may_come_before_the_positionals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width N`` consumes two arguments, not three."""
        out = call_main(["generate", "--width", "20", "brainfuck", TABLE3], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20
        assert esolangs.run("brainfuck", out, stdin="011") == "0"

    def test_width_with_an_equals_sign(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width=N`` is the same option written the other way."""
        out = call_main(["generate", "brainfuck", TABLE3, "--width=20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20

    def test_bare_width_takes_the_default(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bare ``--width`` wraps to the conventional default."""
        from esolangs.tools.wrap import DEFAULT_WIDTH

        out = call_main(["generate", "brainfuck", TABLE3, "--width"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= DEFAULT_WIDTH
        assert "\n" in out.rstrip("\n")

    def test_bare_width_before_a_non_integer(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A following word is an argument, not a width."""
        out = call_main(["generate", "--width", "brainfuck", TABLE3], capsys)
        assert esolangs.run("brainfuck", out, stdin="011") == "0"


# ``+.+.+.`` after an 8x8 loop prints A, B, C -- three separate writes, so a
# break on the second one has a run to stop in the middle of.
_ABC = "++++++++[>++++++++<-]>+.+.+."


class TestDebugCommand:
    """``esolangs debug`` exposes the breakpoint/watch VM on the CLI."""

    def test_it_runs_to_halt_and_reports_the_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = call_main(["debug", "brainfuck", _program(tmp_path, _ABC)], capsys)
        assert "halted: yes" in out
        assert "output: 'ABC'" in out

    def test_steps_bounds_the_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A step budget stops the run short, which is the point of it."""
        out = call_main(
            ["debug", "--steps", "5", "brainfuck", _program(tmp_path, _ABC)], capsys
        )
        assert "halted: no" in out
        assert "output: ''" in out

    def test_the_option_takes_an_inline_value_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--steps=5`` is the same option written the other way."""
        out = call_main(
            ["debug", "--steps=5", "brainfuck", _program(tmp_path, _ABC)], capsys
        )
        assert "halted: no" in out

    def test_watch_cell_reports_one_value_per_step(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The watch history is what the debugger adds over plain stepping."""
        out = call_main(
            [
                "debug",
                "--steps",
                "3",
                "--watch-cell",
                "0",
                "brainfuck",
                _program(tmp_path, _ABC),
            ],
            capsys,
        )
        assert "cell 0: [1, 2, 3]" in out

    def test_break_on_output_stops_with_the_condition_still_true(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A breakpoint is checked *before* a step, so ``B`` is the last byte."""
        out = call_main(
            ["debug", "--break-on-output", "B", "brainfuck", _program(tmp_path, _ABC)],
            capsys,
        )
        assert "halted: no" in out
        assert "output: 'AB'" in out

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


class TestBreakpointOptions:
    """``--break-at`` and ``--break-on-cell`` on the batch debugger."""

    def test_break_at_stops_on_the_position(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = call_main(
            ["debug", "--break-at", "3", "brainfuck", _program(tmp_path, "+++++")],
            capsys,
        )
        assert "ip: 3" in out
        assert "halted: no" in out

    def test_break_on_cell_stops_with_the_value_still_there(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = call_main(
            [
                "debug",
                "--break-on-cell",
                "0=3",
                "--watch-cell",
                "0",
                "brainfuck",
                _program(tmp_path, "+++++"),
            ],
            capsys,
        )
        assert "cell 0: [1, 2, 3]" in out


class TestTuiFlag:
    """``--tui`` hands the run to the step-through screen."""

    @pytest.fixture(autouse=True)
    def _pretend_a_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Say that a terminal is present, because pytest's stdin is not one."""
        monkeypatch.setattr(_FakeStdin, "isatty", lambda _self: True)

    def test_it_calls_the_screen_with_the_program_and_input(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The key loop owns the terminal, so what is pinned here is the
        # handoff: the flag is recognised, stripped from the positionals,
        # and the right three arguments reach the screen.
        with patch("esolangs.cli_debug.run_tui") as screen:
            call_main(
                [
                    "debug",
                    "--tui",
                    "--stdin",
                    "01",
                    "brainfuck",
                    _program(tmp_path, ",."),
                ],
                capsys,
            )
        screen.assert_called_once()
        language, program, stdin = screen.call_args.args
        assert (language, program, stdin) == ("brainfuck", ",.", "01")

    def test_breakpoints_reach_the_screen(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same flags the batch debugger takes drive the continue key."""
        with patch("esolangs.cli_debug.run_tui") as screen:
            call_main(
                [
                    "debug",
                    "--tui",
                    "--stdin",
                    "",
                    "--break-on-cell",
                    "0=2",
                    "brainfuck",
                    _program(tmp_path, "+++"),
                ],
                capsys,
            )
        stop = screen.call_args.kwargs["stop"]
        assert stop is not None
        # The predicate reads a frame, so it can be checked without a run.
        frame = esolangs.tui.Frame(
            language="brainfuck",
            program="+++",
            ip=2,
            step=2,
            halted=False,
            memory=(2,),
            stack=(),
            output="",
        )
        assert stop(frame)

    def test_a_position_reaches_the_screen_as_a_drawn_mark(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--break-at`` is the one breakpoint that has somewhere to be drawn."""
        with patch("esolangs.cli_debug.run_tui") as screen:
            call_main(
                [
                    "debug",
                    "--tui",
                    "--stdin",
                    "",
                    "--break-at",
                    "2",
                    "brainfuck",
                    _program(tmp_path, "+++"),
                ],
                capsys,
            )
        assert screen.call_args.kwargs["at"] == (2,)
        # A position needs no predicate: the screen stops on what it marks.
        assert screen.call_args.kwargs["stop"] is None

    def test_a_watched_cell_reaches_the_screen(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--watch-cell`` means the same on both sides, shown as a row."""
        with patch("esolangs.cli_debug.run_tui") as screen:
            call_main(
                [
                    "debug",
                    "--tui",
                    "--stdin",
                    "",
                    "--watch-cell",
                    "2",
                    "brainfuck",
                    _program(tmp_path, "+++"),
                ],
                capsys,
            )
        assert screen.call_args.kwargs["watch"] == 2


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


class TestArgumentHygiene:
    """A mistyped command is reported where the mistake is."""

    def test_a_file_named_like_an_option_is_still_reachable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Which is what the old permissiveness was protecting; `--` says so."""
        path = tmp_path / "--x"
        path.write_text("+.")
        out = call_main(["run", "--", "brainfuck", str(path)], capsys)
        assert out == "\x01"

    def test_a_bare_width_explains_the_argument_it_shifted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width abc Sophie 0110`` reported ``unknown language: abc``."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--width", "abc", "Sophie", "0110"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unexpected argument: '0110'" in err
        # The message must name the word that was shifted, not just describe
        # the rule: the complaint was that it never said what 'abc' became.
        assert "'abc' was read as the language" in err

    def test_list_takes_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["list", "extra"], capsys)
        assert exc.value.code == 2


class TestCapabilityListing:
    """`esolangs list` can answer what the README sends a reader to it for."""

    def test_details_marks_generators_templates_and_examples(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = dict(
            line.split(maxsplit=0) and (line[:32].strip(), line[32:].strip())
            for line in call_main(["list", "--details"], capsys).splitlines()
        )
        assert rows["brainfuck"] == "gen ex"
        assert rows["Minifuck"] == "gen tmpl ex"

    def test_the_plain_listing_is_unchanged(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Scripts parse it, so the default output stays bare names."""
        names = call_main(["list"], capsys).split()
        assert "brainfuck" in names


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

    def test_a_short_watch_history_is_printed_whole(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = call_main(
            ["debug", "--watch-cell", "0", "brainfuck", _program(tmp_path, "+++")],
            capsys,
        )
        assert "cell 0: [1, 2, 3]" in out


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
        "generate Piet 0110 --bits 01",
        "raster programs read bits",
    ),
    "generate_unknown_language": ("generate NoSuchLanguage 01", "unknown language"),
    "run_missing_file": ("run Sophie /no/such/file", "cannot read"),
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
    "a_piped_stream_is_refused": ("debug --tui brainfuck prog:,.", "terminal", "Z"),
    "stdin_does_not_buy_a_terminal": (
        "debug --tui --stdin 1 brainfuck prog:,.",
        "terminal",
    ),
    "an_unknown_option_is_named": (
        "debug --frobnicate brainfuck prog:+",
        "unknown option: --frobnicate",
    ),
    "an_extra_argument_is_refused": (
        f"generate brainfuck {TABLE3} extra",
        "unexpected argument: 'extra'",
    ),
}


@pytest.mark.parametrize("case", _REFUSALS.values(), ids=list(_REFUSALS))
def test_a_bad_command_exits_2_and_says_why(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message in _refused(command, tmp_path, capsys, *stdin)
