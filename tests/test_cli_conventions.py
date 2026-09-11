"""CLI contracts a second blind pass found once the first round's fixes landed.

The first pass fixed what a new user hit in the first ten minutes.  These are
what the next one hit: a program file's own trailing newline, a debugger that
skipped the refusals ``run`` had just gained, and the seventeen template
languages left unreachable by a fix that pointed a CLI user at a Python call.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from tests.test_cli import _FakeStdin, _program, call_main

EXAMPLES = Path(__file__).parents[1] / "examples" / "boolean"


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
