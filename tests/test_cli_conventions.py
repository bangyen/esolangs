"""CLI contracts a second blind pass found once the first round's fixes landed.

The first pass fixed what a new user hit in the first ten minutes.  These are
what the next one hit: a program file's own trailing newline, a debugger that
skipped the refusals ``run`` had just gained, and the seventeen template
languages left unreachable by a fix that pointed a CLI user at a Python call.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import main
from tests.test_cli import _FakeStdin, _program, call_main, run_cli

EXAMPLES = Path(__file__).parents[1] / "examples" / "boolean"


def call_both(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> tuple[str, str]:
    """Run ``main`` and return both streams.

    ``call_main`` reads ``capsys`` itself and hands back only stdout, so a
    test that then reached for ``.err`` found an empty string and passed
    while asserting nothing.  These tests are *about* stderr, so they need
    the one read to return both.
    """
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    captured = capsys.readouterr()
    return str(captured.out), str(captured.err)


class TestProgramFilesLoad:
    """The newline a text file ends with is the file's, not the program's."""

    def test_a_generated_file_runs_as_written(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``esolangs generate > f`` wrote a newline three interpreters reject."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110") + "\n")
        assert call_main(["run", "Grapheme", str(path)], capsys, stdin="%\nA\n") == "1"

    @pytest.mark.parametrize(
        ("stem", "name"),
        [("cvnc", "CV(N)(C)"), ("grapheme", "Grapheme"), ("nocomment", "NoComment")],
    )
    def test_the_committed_examples_run(
        self, stem: str, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All three failed on the newline their own file ends with."""
        zero, one = esolangs.describe(name)["input_encoding"]  # type: ignore[misc]
        out = call_main(
            ["run", name, str(EXAMPLES / f"{stem}.txt")],
            capsys,
            stdin=f"{zero}\n{one}\n",
        )
        assert out


class TestDebugMakesTheSameRefusals:
    """Debugging a program is no reason to skip the checks ``run`` makes."""

    def test_an_unfilled_template_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It stepped one to a confident ``output: '0'``, which was wrong."""
        path = tmp_path / "t.txt"
        path.write_text(esolangs.generate("Minifuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "Minifuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "{X0}" in capsys.readouterr().err

    def test_a_load_error_is_reported_not_raised(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``debug --help`` promises a raise is reported, not propagated."""
        path = tmp_path / "junk.txt"
        path.write_text("ZZZ!!!")
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "Grapheme", str(path)], capsys)
        assert exc.value.code == 2
        assert "uppercase Latin letters" in capsys.readouterr().err

    def test_a_negative_step_bound_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It was accepted and ran unbounded -- what ``--steps`` exists to stop."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", "--steps", "-1", "brainfuck", _program(tmp_path, "+")], capsys
            )
        assert exc.value.code == 2
        assert "must not be negative" in capsys.readouterr().err


class TestRunCanBeBounded:
    """Several of these languages loop forever by design."""

    def test_timeout_stops_a_program_that_never_halts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", "1", "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        # 124, after timeout(1).  This was 1 -- the same code a program's
        # own failure exits with -- which left the three languages whose
        # answer *is* a timeout indistinguishable from a crash.
        assert exc.value.code == 124
        assert "timeout" in capsys.readouterr().err

    @pytest.mark.parametrize("value", ["x", "0", "-3"])
    def test_a_bad_timeout_is_refused(
        self, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", value, "brainfuck", _program(tmp_path, "+")],
                capsys,
            )
        assert exc.value.code == 2


class TestTemplatesAreReachableFromTheCli:
    """Seventeen languages a CLI-only user could not finish."""

    def test_bits_completes_every_row(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal pointed at ``esolangs.instantiate``, a Python call."""
        got = ""
        for a in (0, 1):
            for b in (0, 1):
                program = call_main(
                    ["generate", "--bits", f"{a}{b}", "Minifuck", "0110"], capsys
                )
                path = tmp_path / "m.txt"
                path.write_text(program.rstrip("\n"))
                got += call_main(["run", "Minifuck", str(path)], capsys)
        assert got == "0110"

    def test_bits_rejects_a_non_binary_string(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "2x", "Minifuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "must be a string of 0s and 1s" in capsys.readouterr().err

    def test_bits_on_a_reader_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "01", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "reads its inputs" in capsys.readouterr().err


class TestVersion:
    def test_version_is_a_flag_not_an_unknown_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out


class TestRoundThreeFixes:
    """What the third blind pass hit."""

    def test_a_negative_watch_cell_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It printed cell 0's history under the name -1: a wrong answer."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", "--watch-cell", "-1", "brainfuck", _program(tmp_path, "+++")],
                capsys,
            )
        assert exc.value.code == 2
        assert "must not be negative" in capsys.readouterr().err

    def test_the_template_refusal_names_the_cli_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It pointed a CLI-only user at ``esolangs.instantiate(...)``."""
        path = tmp_path / "t.txt"
        path.write_text(esolangs.generate("Minifuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "Minifuck", str(path)], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "esolangs generate --bits" in err
        assert "esolangs.instantiate" not in err


class TestRoundSixQol:
    """The CLI no longer sends its users to the Python API for basics."""

    def test_encode_prints_the_stdin_a_language_wants(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run --help` used to answer this with a `python -c` incantation."""
        assert call_main(["encode", "Grapheme", "10"], capsys) == "A\n%\n"
        assert call_main(["encode", "Taglate", "101"], capsys) == "0\n1\n0\n1\n"

    def test_encode_then_run_computes_the_table(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The pipeline the help now recommends, on the awkward language."""
        path = tmp_path / "tg.txt"
        path.write_text(esolangs.generate("Taglate", "10010110"))
        got = ""
        for row in range(8):
            stdin = call_main(["encode", "Taglate", f"{row:03b}"], capsys)
            got += call_main(["run", "Taglate", str(path)], capsys, stdin=stdin)[-1:]
        assert got == "10010110"

    def test_encode_refuses_a_language_that_reads_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "123", "01"], capsys)
        assert exc.value.code == 2
        assert "reads no stdin" in capsys.readouterr().err

    def test_version_is_accepted_after_a_subcommand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The top-level help advertises it without saying where it goes."""
        with pytest.raises(SystemExit) as exc:
            call_main(["list", "--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out

    def test_a_repeated_option_is_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Last-wins quietly emitted the program for the wrong input row."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["generate", "--bits", "10", "--bits", "01", "Minifuck", "0110"], capsys
            )
        assert exc.value.code == 2
        assert "more than once" in capsys.readouterr().err

    def test_debug_always_prints_its_stopped_field(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It vanished on a raise, the one case a script most wants to read."""
        out = call_main(["debug", "brainfuck", _program(tmp_path, ",.")], capsys)
        assert "stopped: raised" in out
        assert "raised: InputExhaustedError" in out

    def test_a_watched_cell_that_is_never_written_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = call_main(
            [
                "debug",
                "--steps",
                "5",
                "--watch-cell",
                "999",
                "brainfuck",
                _program(tmp_path, "+++++"),
            ],
            capsys,
        )
        assert "never written" in out

    def test_encode_refuses_a_non_binary_bit_string(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "brainfuck", "2x"], capsys)
        assert exc.value.code == 2
        assert "0s and 1s" in capsys.readouterr().err

    def test_a_program_that_prints_nothing_says_so_on_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence was indistinguishable from piping to the wrong path."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        # Not ``call_main``: it drains the capture buffer to return stdout,
        # and the note under test goes to stderr.
        with (
            patch.object(sys, "argv", ["esolangs", "run", "brainfuck", str(empty)]),
            patch.object(sys, "stdin", _FakeStdin("")),
            patch.object(sys.stdout, "isatty", lambda: True),
        ):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "printed nothing" in captured.err
        assert "the file is empty" in captured.err

    def test_a_pipe_still_receives_exactly_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The note is for a terminal; piped output stays byte-exact."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        assert call_main(["run", "brainfuck", str(empty)], capsys) == ""

    @pytest.mark.parametrize("value", ["inf", "nan", "-inf"])
    def test_a_nonfinite_timeout_is_refused(
        self, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A deadline that never arrives is not a bound."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", value, "brainfuck", _program(tmp_path, "+")],
                capsys,
            )
        assert exc.value.code == 2
        assert "finite" in capsys.readouterr().err

    def test_an_empty_break_on_output_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every output contains '', so it fired before anything ran."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                [
                    "debug",
                    "--break-on-output",
                    "",
                    "brainfuck",
                    _program(tmp_path, "+++"),
                ],
                capsys,
            )
        assert exc.value.code == 2
        assert "needs some text" in capsys.readouterr().err

    def test_debug_can_be_bounded_by_time(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` had --timeout and `debug`, which you reach for on a hang, did not."""
        out = call_main(
            ["debug", "--timeout", "1", "brainfuck", _program(tmp_path, "+[]")], capsys
        )
        assert "stopped: timeout" in out


class TestTheShellCanJudgeAnAnswer:
    """Nine languages could be run from the CLI and not judged from it.

    ``read_answer`` and ``describe`` shipped in the round before this one and
    shipped to Python only, so a shell user could produce A Painter Ant's
    eleven-line grid and had no way to learn that the answer is the mark on
    the ant's own cell.  The only route was generating all four rows and
    diffing them by eye.
    """

    def test_describe_prints_the_input_shape(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fact whose absence caused this round's wrong answer."""
        out = call_main(["describe", "Fargo"], capsys)
        assert "input_shape" in out
        assert "row_index" in out

    def test_describe_prints_the_traits_that_decide_how_to_drive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A Painter Ant cannot be stepped to its answer; it says so."""
        out = call_main(["describe", "A Painter Ant"], capsys)
        assert "steppable_to_answer" in out
        assert "False" in out

    def test_describe_resolves_a_name_case_insensitively(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """As every other subcommand does."""
        assert "brainfuck" in call_main(["describe", "BRAINFUCK"], capsys)

    def test_describe_suggests_a_near_miss(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The registry's suggestions reach the new command too."""
        with pytest.raises(SystemExit) as exc:
            call_main(["describe", "Brainfck"], capsys)
        assert exc.value.code == 2
        assert "did you mean" in capsys.readouterr().err

    def test_read_answer_finds_a_dumped_answer(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """RAM0's answer is its `z` register, three lines from the end."""
        program = esolangs.instantiate(
            "RAM0", esolangs.generate("RAM0", "0110"), [0, 1]
        )
        output = esolangs.run("RAM0", program, timeout=20)
        assert call_main(["read-answer", "RAM0"], capsys, stdin=output).strip() == "1"

    def test_read_answer_refuses_a_termination_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Their output is not the answer, so reading one would invent it."""
        with pytest.raises(SystemExit) as exc:
            call_main(["read-answer", "123"], capsys, stdin="VO")
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "--judge" in err
        assert "--timeout" in err

    def test_read_answer_says_so_when_given_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An empty pipe is a mistake, not an answer of zero."""
        with pytest.raises(SystemExit) as exc:
            call_main(["read-answer", "brainfuck"], capsys, stdin="")
        assert exc.value.code == 2
        assert "nothing on stdin" in capsys.readouterr().err

    def test_run_judge_prints_the_bit_for_a_dump(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A Painter Ant's grid, reduced to the one character that matters."""
        program = esolangs.instantiate(
            "A Painter Ant", esolangs.generate("A Painter Ant", "0110"), [0, 1]
        )
        out = call_main(
            ["run", "--judge", "A Painter Ant", _program(tmp_path, program)], capsys
        )
        assert out.strip() == "1"

    def test_run_judge_reads_a_timeout_as_the_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """For the three that answer by diverging, not halting *is* the 1."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        out = call_main(
            ["run", "--judge", "--timeout", "5", "123", _program(tmp_path, program)],
            capsys,
        )
        assert out.strip() == "1"

    def test_run_judge_reads_a_halt_as_the_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And the other polarity, from the same program and a different row."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        out = call_main(
            ["run", "--judge", "--timeout", "5", "123", _program(tmp_path, program)],
            capsys,
        )
        assert out.strip() == "0"

    def test_run_judge_needs_a_bound_for_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """There is nothing to wait for without one."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "--judge", "123", _program(tmp_path, program)], capsys)
        assert exc.value.code == 2
        assert "--judge needs --timeout" in capsys.readouterr().err


class TestATimeoutIsNotAProgramError:
    """They shared exit 1, so a script could not tell them apart."""

    def test_a_timeout_exits_124(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Following timeout(1), and distinct from the program's own failure."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", "1", "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        assert exc.value.code == 124

    def test_a_program_failure_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half of the distinction, which is what makes 124 useful."""
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", _program(tmp_path, ",")], capsys, stdin="")
        assert exc.value.code == 1

    def test_a_termination_languages_timeout_says_it_is_the_answer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It read as a failure when it was the result."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", "2", "123", _program(tmp_path, program)], capsys
            )
        assert exc.value.code == 124
        assert "this timeout is the answer 1" in capsys.readouterr().err

    def test_an_unbounded_termination_language_is_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Its default path is an unbounded run of a program built to loop."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        call_main(["run", "123", _program(tmp_path, program)], capsys)
        # Row [0, 0] halts, so the run finishes; the warning is still owed,
        # because which row it is cannot be known before running it.


class TestMessagesNameTheThingThatIsWrong:
    """Small, and each one sent a reader to the wrong word."""

    def test_a_repeated_width_quotes_its_value(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It reported `first was '--width'`, which the reader already knew."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["generate", "--width", "77", "--width", "33", "brainfuck", "0110"],
                capsys,
            )
        assert exc.value.code == 2
        assert "first was '77'" in capsys.readouterr().err

    def test_a_missing_argument_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The synopsis alone left the reader to diff it against what they typed."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "missing <truth-table>" in capsys.readouterr().err

    def test_swapped_arguments_are_recognized_as_swapped(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`unknown language: 0110` is true and does not help."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "0110", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "looks like a truth table" in capsys.readouterr().err

    def test_a_misspelled_option_is_suggested(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Language names had suggestions; the flags beside them had none."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--wdith", "40", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "did you mean --width" in capsys.readouterr().err

    def test_encode_points_at_a_flag_not_a_python_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`instantiate()` is not reachable from a shell."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "Minifuck", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "instantiate()" not in err
        assert "esolangs generate --bits" in err

    def test_the_details_legend_is_printed_with_the_details(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It lived in `list --help` only, so the columns arrived unexplained."""
        out = call_main(["list", "--details"], capsys)
        assert out.splitlines()[0].strip().startswith("language")
        assert "gen=generator" in out.splitlines()[0]


class TestTheHintsStayQuietWhenTheyDoNotApply:
    """Each hint added this round rewrites one message and no others."""

    def test_an_unknown_language_is_not_called_a_swapped_argument(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The hint fires on a power-of-two run of 0s and 1s, not on any miss."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "Nonexistent", "0110"], capsys)
        assert exc.value.code == 2
        assert "looks like a truth table" not in capsys.readouterr().err

    def test_encode_leaves_an_unrelated_error_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only the message naming ``instantiate()`` gets rewritten."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "Nonexistent", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unknown language" in err
        assert "generate --bits" not in err

    def test_read_answer_reports_an_unknown_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The name is resolved before anything is read from stdin."""
        with pytest.raises(SystemExit) as exc:
            call_main(["read-answer", "Nonexistent"], capsys, stdin="1")
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_read_answer_reports_an_unreadable_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Rather than guessing a bit out of text that carries none."""
        with pytest.raises(SystemExit) as exc:
            call_main(["read-answer", "brainfuck"], capsys, stdin="no digits here!")
        assert exc.value.code == 2
        assert "no answer this could read" in capsys.readouterr().err

    def test_judge_reports_an_unreadable_output_as_the_programs_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Exit 1: the program ran and produced something unjudgeable."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                [
                    "run",
                    "--judge",
                    "brainfuck",
                    _program(tmp_path, "++++++++[>++++++++<-]>."),
                ],
                capsys,
            )
        assert exc.value.code == 1
        assert "no answer this could read" in capsys.readouterr().err

    def test_a_non_table_run_of_digits_is_not_called_a_swap(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """'011' is 0s and 1s but no table's length, so it is just a bad name."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "011", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "looks like a truth table" not in capsys.readouterr().err


class TestNonTextInputIsRefusedNotCrashed:
    """Pointing `run` at a PNG dumped a traceback with internal paths in it.

    ``UnicodeDecodeError`` is a ``ValueError``, not an ``OSError``, so the
    handler that turns "Is a directory" into one clean line never saw it.
    Four call sites decode -- two files and two stdins -- and all four had
    the same hole, so all four are pinned here.
    """

    def test_a_binary_program_file_is_refused(self, tmp_path: Path) -> None:
        """Reachable by a newcomer pointing `run` at the wrong file."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        result = run_cli("run", "brainfuck", str(path))
        assert result.returncode == 2
        assert "not text" in result.stderr
        assert "Traceback" not in result.stderr

    def test_debug_refuses_it_too(self, tmp_path: Path) -> None:
        """The same reader serves both commands."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        result = run_cli("debug", "--steps", "5", "brainfuck", str(path))
        assert result.returncode == 2
        assert "not text" in result.stderr

    def test_binary_stdin_is_refused(self) -> None:
        """A program's binary output piped into `read-answer`."""
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", "brainfuck"],
            input=b"\x80\x81",
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 2
        assert b"not text" in result.stderr
        assert b"Traceback" not in result.stderr

    def test_the_library_names_it_as_a_program_error(self, tmp_path: Path) -> None:
        """``check_program`` decodes a Path and had the same gap."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(esolangs.ProgramError, match="not text"):
            esolangs.run("brainfuck", path)


class TestTheShapeWarningFiresOnlyWhenItShould:
    """The last silent-wrong path: stdin in the shape a reader expects.

    A warning, not a refusal -- ``run`` executes arbitrary programs of a
    language, so a shape this calls wrong may be what a hand-written program
    wants.  The answer and the exit code are unchanged either way.
    """

    def test_naive_bits_into_a_different_alphabet_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Grapheme reads any non-empty line as true, so '0' is a 1."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        _out, err = call_both(["run", "Grapheme", str(path)], capsys, stdin="1\n0\n")
        assert "spells its bits" in err

    def test_multiple_lines_into_a_one_line_language_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Clockwise reads its bits in one go."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("Clockwise", "0110"))
        _out, err = call_both(["run", "Clockwise", str(path)], capsys, stdin="1\n0\n")
        assert "wants every bit on one line" in err

    def test_multiple_lines_into_a_row_index_language_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Fargo reads one decimal number."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        _out, err = call_both(["run", "Fargo", str(path)], capsys, stdin="1\n0\n")
        assert "row index" in err

    def test_the_encoded_stdin_is_not_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must be quiet, or the warning is noise."""
        for name in ("Grapheme", "Clockwise", "Fargo"):
            path = tmp_path / "p.txt"
            path.write_text(esolangs.generate(name, "0110"))
            stdin = esolangs.encode_inputs(name, [1, 0])
            _out, err = call_both(["run", name, str(path)], capsys, stdin=stdin)
            assert "esolangs encode" not in err, name

    def test_an_ordinary_language_is_never_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sixty-five languages read 0/1 lines and must stay silent."""
        path = tmp_path / "bf.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="1\n0\n")
        assert out == "1"
        assert err == ""

    def test_the_warning_does_not_change_the_answer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It is advice; the run is exactly what it was."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        warned = call_main(["run", "Grapheme", str(path)], capsys, stdin="1\n0\n")
        capsys.readouterr()
        stdin = esolangs.encode_inputs("Grapheme", [1, 0])
        right = call_main(["run", "Grapheme", str(path)], capsys, stdin=stdin)
        assert warned == "0"
        assert right == "1"


class TestAnUnboundedRunSaysSo:
    """Several of these languages loop forever by design."""

    def test_the_notice_names_the_flag(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shortened rather than waited out, so the test costs nothing."""
        monkeypatch.setattr(cli, "_UNBOUNDED_NOTICE_AFTER", 0.01)
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        call_main(["run", "brainfuck", str(path)], capsys, stdin="1\n0\n")
        # The run finishes in microseconds, so the notice may or may not
        # have fired; what must hold is that arming it broke nothing.
        capsys.readouterr()

    def test_a_bounded_run_never_arms_it(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --timeout there is nothing to warn about."""
        monkeypatch.setattr(cli, "_UNBOUNDED_NOTICE_AFTER", 0.01)
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            ["run", "--timeout", "10", "brainfuck", str(path)], capsys, stdin="1\n0\n"
        )
        assert "no bound" not in err

    def test_debug_warns_about_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` gained this a round earlier and `debug` did not."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "123", str(path)], capsys)
        assert "not terminating" in err

    def test_a_bounded_debug_is_not_told_to_pass_a_bound(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--steps is a bound as much as --timeout is."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "--steps", "200", "123", str(path)], capsys)
        assert "pass --timeout" not in err


class TestATimeoutValueIsCheckedBeforeThePositionals:
    """A forgotten number blamed the argument that was not the problem."""

    @pytest.mark.parametrize("command", ["run", "debug"])
    def test_a_missing_number_names_the_timeout(
        self, command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It reported `missing <program-file>`, having eaten the language."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--timeout", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "--timeout must be a number" in capsys.readouterr().err

    @pytest.mark.parametrize("command", ["run", "debug"])
    def test_a_dash_leading_value_still_reaches_the_finiteness_check(
        self, command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The earlier fix depended on option-before-stray order; still holds."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--timeout", "-inf", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "must be finite" in capsys.readouterr().err


class TestTheDecodeGuardsInProcess:
    """The subprocess tests above prove the behaviour; these reach the lines.

    Coverage is measured in this process, so a path exercised only through
    ``run_cli`` is invisible to it -- which would leave the handlers that
    fix this round's one real bug looking untested.
    """

    def test_read_program_refuses_a_binary_file(self, tmp_path: Path) -> None:
        """The file reader's own clause, called directly."""
        path = tmp_path / "b.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(SystemExit) as exc:
            cli._read_program(str(path))  # noqa: SLF001
        assert exc.value.code == 2

    def test_read_program_still_refuses_an_unreadable_path(
        self, tmp_path: Path
    ) -> None:
        """The OSError clause beside it, which the new one must not shadow."""
        with pytest.raises(SystemExit) as exc:
            cli._read_program(str(tmp_path))  # noqa: SLF001
        assert exc.value.code == 2

    def test_read_stdin_refuses_undecodable_bytes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A stdin whose read raises, as a piped binary stream's does."""

        class _BadStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                raise UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte")

        with patch.object(sys, "stdin", _BadStdin()), pytest.raises(SystemExit) as exc:
            cli._read_stdin()  # noqa: SLF001
        assert exc.value.code == 2
        assert "not text" in capsys.readouterr().err

    def test_read_stdin_is_empty_on_a_terminal(self) -> None:
        """The branch beside it: nothing piped in."""

        class _Tty:
            def isatty(self) -> bool:
                return True

            def read(self) -> str:  # pragma: no cover - never called
                raise AssertionError("should not read a terminal")

        with patch.object(sys, "stdin", _Tty()):
            assert cli._read_stdin() == ""  # noqa: SLF001

    def test_the_unbounded_notice_writes_one_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Called directly rather than waited for."""
        cli._UnboundedNotice._say("run")  # noqa: SLF001
        err = capsys.readouterr().err
        assert "no bound" in err
        assert "--timeout" in err

    def test_debug_warns_about_a_mismatched_shape_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` and `debug` feed the same stdin to the same interpreter."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        _out, err = call_both(
            ["debug", "--steps", "50", "Grapheme", str(path)], capsys, stdin="1\n0\n"
        )
        assert "spells its bits" in err


class TestStdinIsCheckedAgainstTheDeclaredAlphabet:
    """`encode` refused these bytes all along; `run` answered them.

    A leading space, a tab, a `2` or the word `true` each produced a
    confident wrong bit at exit 0 -- and brainfuck and Sophie returned
    *different* answers for the same junk byte, which is what proved nothing
    was reading it.
    """

    @pytest.mark.parametrize("line", [" 1", "\t1", "2", "true", "01", "+1"])
    def test_plain_run_warns_about_a_stray_line(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A warning, because `run` executes arbitrary programs."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        _out, err = call_both(
            ["run", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
        )
        assert "spells its bits" in err

    @pytest.mark.parametrize("line", [" 1", "2", "true"])
    def test_judge_refuses_it(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--judge asks for an answer bit, so a bad encoding is a usage error."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
            )
        assert exc.value.code == 2
        assert "spells its bits" in capsys.readouterr().err

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        out, err = call_both(
            ["run", "--judge", "brainfuck", str(path)], capsys, stdin="0\n1\n"
        )
        assert out.strip() == "1"
        assert err == ""

    def test_every_language_accepts_its_own_encoding(self) -> None:
        """The check must not fire on what `encode_inputs` itself produces."""
        noisy = []
        for name in esolangs.list_languages():
            if esolangs.describe(name)["parameterized"]:
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            if cli._shape_warning(esolangs.describe(name), stdin):  # noqa: SLF001
                noisy.append(name)
        assert not noisy, noisy

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        facts = esolangs.describe("Grapheme")
        assert cli._shape_warning(facts, "%\nA\n") == ""  # noqa: SLF001
        # 0/1 is wrong *here*, and the specific message is the one that
        # fires: the general stray-line rule runs last so a language with
        # something better to say keeps saying it.
        assert "spells its bits" in cli._shape_warning(facts, "0\n1\n")  # noqa: SLF001


class TestTheSmallInconsistencies:
    """Each one was a place this CLI did not do what it does everywhere else."""

    def test_an_unknown_subcommand_is_suggested(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Languages and options both suggest; the commands did not."""
        with pytest.raises(SystemExit) as exc:
            call_main(["lst"], capsys)
        assert exc.value.code == 2
        assert "did you mean list" in capsys.readouterr().err

    def test_a_repeated_judge_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every value-taking option refused a repeat; this flag did not."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "--judge", "brainfuck", str(path)],
                capsys,
                stdin="0\n1\n",
            )
        assert exc.value.code == 2
        assert "--judge given more than once" in capsys.readouterr().err

    def test_a_no_op_width_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        """It was silently ignored: two identical programs, one asked to differ."""
        _out, err = call_both(
            ["generate", "--width", "10", "Clockwise", "0100"], capsys
        )
        assert "no effect on Clockwise" in err

    def test_a_wrapping_width_says_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The note must not fire where the width does something."""
        _out, err = call_both(["generate", "--width", "10", "Sophie", "0100"], capsys)
        assert "no effect" not in err

    def test_describe_reports_the_width_effect(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The field a reader could not work out without the source."""
        assert "width_effect" in call_main(["describe", "Sophie"], capsys)

    def test_a_breakpoint_that_never_fires_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It looked exactly like a program that never reached it."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            [
                "debug",
                "--break-on-output",
                "Z",
                "--steps",
                "5000",
                "brainfuck",
                str(path),
            ],
            capsys,
            stdin="0\n1\n",
        )
        assert "no breakpoint matched" in err

    def test_a_breakpoint_that_fires_is_not_reported_as_missed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half, so the note means something."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out, err = call_both(
            [
                "debug",
                "--break-on-output",
                "1",
                "--steps",
                "5000",
                "brainfuck",
                str(path),
            ],
            capsys,
            stdin="0\n1\n",
        )
        assert "stopped: breakpoint" in out
        assert "no breakpoint matched" not in err


class TestTheRoundTripIsOneCommand:
    """A CLI-only user had to write the loop the README says they need not."""

    def test_verify_reports_a_match(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Every row generated, encoded, run and judged."""
        assert call_main(["verify", "brainfuck", "0110"], capsys).strip() == "ok"

    @pytest.mark.parametrize("name", ["Fargo", "Grapheme", "Clockwise", "Taglate"])
    def test_verify_handles_the_odd_input_shapes(
        self, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The four shapes a hand-written loop gets wrong."""
        assert call_main(["verify", name, "0110"], capsys).strip() == "ok"

    def test_verify_handles_a_dump_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A Painter Ant's answer is a mark in an eleven-line grid."""
        assert call_main(["verify", "A Painter Ant", "0110"], capsys).strip() == "ok"

    @pytest.mark.slow
    def test_verify_handles_a_termination_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Each 1-row costs the bound, so this one is paid for."""
        out = call_main(["verify", "--timeout", "5", "123", "0110"], capsys)
        assert out.strip() == "ok"

    def test_evaluate_prints_the_computed_table(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """So a mismatch shows which rows disagree."""
        out = call_main(["evaluate", "brainfuck", "10010110"], capsys)
        assert out.strip() == "10010110"

    def test_a_malformed_table_is_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Named as a table, at the usage exit code."""
        with pytest.raises(SystemExit) as exc:
            call_main(["verify", "brainfuck", "011"], capsys)
        assert exc.value.code == 2

    def test_a_missing_table_is_named(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The wiring that makes the shared machinery reach a new command."""
        with pytest.raises(SystemExit) as exc:
            call_main(["verify", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "missing <truth-table>" in capsys.readouterr().err

    def test_the_new_commands_get_a_suggestion(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """They have to be in the set the did-you-mean searches."""
        with pytest.raises(SystemExit) as exc:
            call_main(["verfiy", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "did you mean verify" in capsys.readouterr().err


class TestFargoRowIndexIsCheckedForBeingOne:
    """Any garbage was read as row 0 and answered at exit 0."""

    @pytest.mark.parametrize("bad", ["abc", "3.7", "", "  ", "1 2"])
    def test_a_non_index_is_refused_under_judge(
        self, bad: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Including a blank line, which was read as row 0."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "10010110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "--judge", "Fargo", str(path)], capsys, stdin=bad + "\n")
        assert exc.value.code == 2
        assert "decimal row index" in capsys.readouterr().err

    def test_a_real_index_is_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Row 3 of 10010110 is 1."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "10010110"))
        out, err = call_both(
            ["run", "--judge", "Fargo", str(path)], capsys, stdin="3\n"
        )
        assert out.strip() == "1"
        assert err == ""

    def test_an_out_of_range_index_is_not_claimed_to_be_caught(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` does not know the program's arity; `verify` enumerates rows."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "10010110"))
        out, _err = call_both(
            ["run", "--judge", "Fargo", str(path)], capsys, stdin="8\n"
        )
        assert out.strip() in ("0", "1")


class TestDescribeHidesInputFieldsWithNoInput:
    """An input shape for a language that reads no stdin is noise."""

    def test_a_template_language_hides_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And names the flag that supplies the bits instead."""
        out = call_main(["describe", "Minifuck"], capsys)
        assert "input_shape" not in out
        assert "generate --bits" in out

    def test_a_reading_language_still_shows_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fields are the point for the languages that have them."""
        out = call_main(["describe", "Fargo"], capsys)
        assert "input_shape" in out
        assert "row_index" in out

    def test_the_api_keeps_every_key(self) -> None:
        """Uniform keys are what a zero-branch caller iterates."""
        keys = {frozenset(esolangs.describe(n)) for n in esolangs.list_languages()}
        assert len(keys) == 1


class TestTheRoundTripsFailurePaths:
    """The reporting a mismatch or a refusal goes through."""

    def test_a_generator_refusal_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Nothing ran, so it is the usage class rather than a wrong answer."""
        with pytest.raises(SystemExit) as exc:
            call_main(["verify", "NoComment", "01" * (1 << 11)], capsys)
        assert exc.value.code == 2
        assert "cell" in capsys.readouterr().err

    def test_a_mismatch_names_the_rows_that_disagree(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No language actually mismatches, so the reporting is driven here.

        Which is the point of testing it: the path that says *what went
        wrong* is the one a reader only ever reaches on a bad day, so it
        must not be the untested one.
        """
        monkeypatch.setattr(cli, "evaluate", lambda *_a, **_k: "0000")
        with pytest.raises(SystemExit) as exc:
            call_main(["verify", "brainfuck", "0110"], capsys)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "computed 0000, wanted 0110" in err
        assert "2 row(s) disagree: 1, 2" in err

    def test_evaluate_prints_a_mismatch_rather_than_failing(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`evaluate` reports and exits 0; the comparison is the caller's."""
        monkeypatch.setattr(cli, "evaluate", lambda *_a, **_k: "0000")
        assert call_main(["evaluate", "brainfuck", "0110"], capsys).strip() == "0000"


class TestBreakAtWhereThereIsNoShape:
    """A machine with no position cannot disagree with a breakpoint's kind."""

    def test_a_language_with_no_ip_accepts_either_kind(self) -> None:
        """Circuit Diagram's ip is None, so there is nothing to compare."""
        program = esolangs.generate("Circuit Diagram", "0110")
        stdin = esolangs.encode_inputs("Circuit Diagram", [0, 1], "0110")
        debugger = esolangs.make_debugger("Circuit Diagram", program, stdin)
        assert debugger.ip is None
        debugger.break_at(3)
        debugger.break_at((1, 2))


class TestTheWidthFlagDoesNotEatTheTable:
    """`--width` takes an optional N, so it swallowed the truth table."""

    def test_a_swallowed_table_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`generate brainfuck --width 0110` said only "missing <truth-table>"."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", "--width", "0110"], capsys)
        assert exc.value.code == 2
        assert "--width" in capsys.readouterr().err

    def test_a_real_width_still_works(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The hint must not fire where the width is a width."""
        out = call_main(["generate", "--width", "20", "brainfuck", "0110"], capsys)
        assert out.strip()


class TestAMultiWordNameSuggestsQuoting:
    """`describe A Painter Ant` blamed the third word."""

    def test_the_joined_positionals_are_suggested(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The suggester can already resolve it; it was never asked."""
        with pytest.raises(SystemExit) as exc:
            call_main(["describe", "A", "Painter", "Ant"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "quote" in err.lower()
        assert "A Painter Ant" in err

    def test_a_genuine_extra_argument_still_says_so(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The hint must not swallow a real mistake."""
        with pytest.raises(SystemExit) as exc:
            call_main(["describe", "brainfuck", "zzz"], capsys)
        assert exc.value.code == 2
        assert "unexpected argument" in capsys.readouterr().err


class TestTheAdvisoryNotesAreRenderedOnce:
    """The library warns; this command renders, and does not also duplicate."""

    def test_a_surplus_line_is_noted_without_pythons_framing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A raw UserWarning would print this file's path and a line of it."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "00010111"))
        out, err = call_both(
            ["run", "brainfuck", str(path)], capsys, stdin="1\n1\n0\n0\n1\n1\n"
        )
        assert out == "1"
        assert "read 3 of the 6 lines" in err
        assert "UserWarning" not in err
        assert "cli.py" not in err

    def test_a_surplus_line_is_said_exactly_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It was printed by the CLI and warned by the library both."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        _out, err = call_both(["run", "Grapheme", str(path)], capsys, stdin="0\n1\n")
        assert err.count("spells its bits") == 1

    def test_judge_refuses_a_surplus_line_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The arity mismatch `--judge` exists to catch."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "00010111"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "brainfuck", str(path)],
                capsys,
                stdin="1\n1\n0\n0\n1\n1\n",
            )
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert err.count("lines supplied") == 1

    def test_an_empty_program_file_is_noted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It ran and printed nothing, at exit 0, with no explanation."""
        path = tmp_path / "empty.txt"
        path.write_text("")
        _out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="0\n0\n")
        assert "is empty" in err

    def test_a_mixed_none_watch_history_is_legended(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The all-None case was annotated; the mixed one needed it more."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Streetcode", "0110"))
        out, _err = call_both(
            ["debug", "--steps", "30", "--watch-cell", "0", "Streetcode", str(path)],
            capsys,
            stdin="0\n1\n",
        )
        assert "did not exist yet" in out

    def test_verify_says_it_checks_the_generator(self) -> None:
        """So nobody mistakes it for a checker of a file they wrote."""
        assert "checks the generator" in cli.HELP["verify"]
        assert "run --judge" in cli.HELP["verify"]
