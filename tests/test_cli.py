"""Unit tests for the esolangs command-line interface.

The subprocess tests exercise the real ``python -m esolangs.cli`` entry
point; the in-process tests exercise every branch of ``main`` so the CLI is
fully covered by the suite (subprocesses do not contribute to coverage).
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main

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


class _FakeStdin:
    def __init__(self, data: str) -> None:
        self.data = data

    def isatty(self) -> bool:
        return False

    def read(self) -> str:
        return self.data


def call_main(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> str:
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    return str(capsys.readouterr().out)


class TestSubprocess:
    def test_list(self) -> None:
        result = run_cli("list")
        assert result.returncode == 0
        assert "Sophie" in result.stdout

    def test_generate(self) -> None:
        result = run_cli("generate", "Sophie", "0110")
        assert result.returncode == 0
        assert esolangs.run("Sophie", result.stdout, "0\n1\n") == "1"

    def test_run(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "0110"))
        result = run_cli("run", "Sophie", str(program), stdin="0\n1\n")
        assert result.returncode == 0
        assert result.stdout == "1"


class TestInProcess:
    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = call_main(["list"], capsys)
        assert "Sophie" in out

    def test_generate(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = call_main(["generate", "Sophie", "0110"], capsys)
        assert esolangs.run("Sophie", out, "0\n1\n") == "1"

    def test_generate_unknown_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "NoSuchLanguage", "01"], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_generate_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "Sophie"], capsys)
        assert exc.value.code == 2

    def test_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "0110"))
        out = call_main(["run", "Sophie", str(program)], capsys, stdin="0\n1\n")
        assert out == "1"

    def test_run_feeds_stdin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from esolangs.tools import boolean

        program = tmp_path / "prog.txt"
        program.write_text(boolean.circlefuck("1101"))
        out = call_main(["run", "Circlefuck", str(program)], capsys, stdin="1\n0\n")
        assert out == "0"

    def test_run_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "Sophie", "/no/such/file"], capsys)
        assert exc.value.code == 2
        assert "cannot read" in capsys.readouterr().err

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

    def test_unknown_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["no.such.command"], capsys)
        assert exc.value.code == 2
        assert "unknown command" in capsys.readouterr().err

    def test_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main([], capsys)
        assert exc.value.code == 2


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", "Sophie", "0110"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out, "0\n1\n") == "1"


class TestWidthOption:
    """``--width`` in all the spellings the parser accepts."""

    def test_width_with_a_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--width N`` bounds the generated program's columns."""
        out = call_main(["generate", "brainfuck", TABLE3, "--width", "20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20
        assert esolangs.run("brainfuck", out, "0\n1\n1\n") == "0"

    def test_width_with_an_equals_sign(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width=N`` is the same option written the other way."""
        out = call_main(["generate", "brainfuck", TABLE3, "--width=20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20

    def test_bare_width_takes_the_default(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bare ``--width`` wraps to the conventional default.

        The common case is "wrap this so I can read it", which needs no
        number; the option is only followed by one when the caller wants a
        width other than the default.
        """
        from esolangs.tools.wrap import DEFAULT_WIDTH

        out = call_main(["generate", "brainfuck", TABLE3, "--width"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= DEFAULT_WIDTH
        assert "\n" in out.rstrip("\n")

    def test_bare_width_before_a_non_integer(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A following word is an argument, not a width.

        Reading the language name as a width would silently generate the
        wrong thing, so only an integer is taken as the option's value.
        """
        out = call_main(["generate", "--width", "brainfuck", TABLE3], capsys)
        assert esolangs.run("brainfuck", out, "0\n1\n1\n") == "0"

    def test_width_rejects_a_non_integer_after_equals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width=x`` has no integer to parse, so it is refused."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", TABLE3, "--width=x"], capsys)
        assert exc.value.code == 2
        assert "must be an integer" in capsys.readouterr().err

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_width_rejects_a_non_positive_value(
        self, value: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A width of zero or less bounds nothing."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", TABLE3, "--width", value], capsys)
        assert exc.value.code == 2
        assert "must be positive" in capsys.readouterr().err


# ``+.+.+.`` after an 8x8 loop prints A, B, C -- three separate writes, so a
# break on the second one has a run to stop in the middle of.
_ABC = "++++++++[>++++++++<-]>+.+.+."


def _program(tmp_path: Path, source: str) -> str:
    """Write ``source`` to a file and return its path."""
    path = tmp_path / "prog.b"
    path.write_text(source)
    return str(path)


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
        """A debugged program is one the caller is already unsure of.

        Reading with no input raises, and the state up to the fault is
        exactly what the caller asked to see -- so it is printed, not
        turned into a traceback.  The raise names how much input the
        program wanted against how much it got, which is the whole
        diagnosis for this fault and is what a bare ``EOFError`` -- whose
        message is the empty string -- could never carry.
        """
        out = call_main(["debug", "brainfuck", _program(tmp_path, ",.")], capsys)
        assert "raised: InputExhaustedError" in out
        assert "0 lines supplied" in out
        assert "halted: no" in out

    def test_unknown_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "NoSuchLanguage", _program(tmp_path, "+")], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", "/no/such/file"], capsys)
        assert exc.value.code == 2
        assert "cannot read" in capsys.readouterr().err

    def test_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "usage: esolangs debug" in capsys.readouterr().err

    @pytest.mark.parametrize("option", ["--steps", "--watch-cell"])
    def test_a_non_integer_option_is_refused(
        self, option: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", option, "x", "brainfuck", _program(tmp_path, "+")], capsys
            )
        assert exc.value.code == 2
        assert "must be an integer" in capsys.readouterr().err

    def test_an_option_with_no_value_is_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The trailing option has nothing to consume, so it is an error
        rather than a silently missing bound."""
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", "prog.b", "--steps"], capsys)
        assert exc.value.code == 2
        assert "--steps needs a value" in capsys.readouterr().err


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

    def test_an_unknown_option_is_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It used to be kept as a positional and blamed on the language."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", "--frobnicate", "brainfuck", _program(tmp_path, "+")], capsys
            )
        assert exc.value.code == 2
        assert "unknown option: --frobnicate" in capsys.readouterr().err

    def test_a_file_named_like_an_option_is_still_reachable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Which is what the old permissiveness was protecting; `--` says so."""
        path = tmp_path / "--x"
        path.write_text("+.")
        out = call_main(["run", "--", "brainfuck", str(path)], capsys)
        assert out == "\x01"

    def test_an_extra_argument_is_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It used to be dropped, making a wrong command a wrong answer."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", TABLE3, "extra"], capsys)
        assert exc.value.code == 2
        assert "unexpected argument: 'extra'" in capsys.readouterr().err

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
        assert "{X0}" in result.stderr
        assert "Traceback" not in result.stderr

    def test_the_readme_suffolk_flow_completes(self, tmp_path: Path) -> None:
        """generate then run, the README's first pair, for all four rows."""
        generated = run_cli("generate", "Suffolk", "0110")
        path = tmp_path / "su.txt"
        path.write_text(generated.stdout.rstrip("\n"))
        got = "".join(
            run_cli("run", "Suffolk", str(path), stdin=f"{a}\n{b}\n").stdout
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

    def test_a_double_dash_ends_the_width_option_too(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--`` is positional-from-here for every parser, not just one."""
        out = call_main(["generate", "--", "brainfuck", TABLE3], capsys)
        assert esolangs.run("brainfuck", out, "0\n1\n1\n") == "0"


class TestGenerateArgumentTypes:
    """``generate``'s own arguments are checked before a generator runs."""

    def test_a_non_integer_width_from_the_api_is_refused(self) -> None:
        """The CLI parses its width; a Python caller can pass anything."""
        with pytest.raises(ValueError, match="width must be an integer"):
            esolangs.generate("brainfuck", "0110", width="80")  # type: ignore[arg-type]
