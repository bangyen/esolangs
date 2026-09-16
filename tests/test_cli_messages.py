"""What the CLI says when something is wrong, and when it stays quiet.

A hint that fires on the wrong input is worse than no hint, so each of these
pins both halves: the case it names, and a near miss it must not name.
"""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import main
from tests.cli_support import _LOOPS, call_both
from tests.test_cli import _FakeStdin, _program, call_main

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


class TestModulousSaysWhatWentWrong:
    """Four halts raised ``HaltError`` with the empty string as a message.

    Exit 1 with nothing on stderr is indistinguishable from a crash, and
    the CLI printed literally nothing because the message it forwards was
    ``""``.
    """

    @pytest.mark.parametrize(
        ("program", "expected"),
        [
            ("[POP][END]", "stack is empty"),
            ('[PSH STR "x"][SWP][END]', "SWP needs two values"),
            ("[PRT VAR9][END]", "not a defined variable"),
            ("[RND 0][END]", "at least 1"),
        ],
    )
    def test_each_halt_names_its_cause(self, program: str, expected: str) -> None:
        """Not the class, the sentence: an empty message helps nobody."""
        with pytest.raises(esolangs.HaltError, match=expected):
            esolangs.run("Modulous", program, "")

    def test_no_halt_is_wordless(self) -> None:
        """The general claim, since a fifth site would repeat the bug."""
        for program in ("[POP][END]", '[PSH STR "x"][SWP][END]', "[PRT VAR9][END]"):
            with pytest.raises(esolangs.HaltError) as caught:
                esolangs.run("Modulous", program, "")
            assert str(caught.value).strip(), program


class TestSmallerReportsFromRoundFifteen:
    """Each one was information that was wrong or hard to find."""

    def test_a_bad_truth_table_echoes_the_argument(self) -> None:
        """It printed ``sorted(set(...))``: "nonsense" came back as "enos"."""
        with pytest.raises(esolangs.TruthTableError, match="got 'nonsense'"):
            esolangs.generate("brainfuck", "nonsense")

    def test_it_also_names_the_offending_character(self) -> None:
        """So a long table does not have to be diffed by eye."""
        with pytest.raises(esolangs.TruthTableError, match="at position 2"):
            esolangs.generate("brainfuck", "01x1")

    def test_check_stdin_admits_it_checked_only_the_shape(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The dedicated checker was weaker than `run` and did not say so."""
        # No note: it printed one whenever `--table` was absent, which is
        # every plain shape check, and advice on correct input is what this
        # CLI has spent rounds removing.  `check-stdin --help` says what the
        # flag adds.
        _out, err = call_both(["check-stdin", "brainfuck"], capsys, stdin="1\n0\n")
        assert err == ""
        assert "--table" in cli.HELP["check-stdin"]

    def test_a_never_written_cell_reports_a_verdict_not_a_wall(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Four hundred Nones with the answer at the far right of the line."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out = call_main(
            ["debug", "--steps", "40", "--watch-cell", "999", "brainfuck", str(path)],
            capsys,
            stdin="1\n0\n",
        )
        assert "never written in 40 step(s)" in out
        assert "None" not in out

    @pytest.mark.parametrize(
        ("name", "phrase"),
        [
            ("Clockwise", "every bit on one line"),
            ("Fargo", "one decimal row index"),
            ("Taglate", "padded with a leading"),
            ("brainfuck", "one line per bit"),
        ],
    )
    def test_describe_spells_the_stdin_out(
        self, name: str, phrase: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader had two fields to compose; templates got a sentence."""
        out = call_main(["describe", name], capsys)
        assert phrase in out


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
        """It was silently ignored: two identical programs, one asked to differ.

        Clockwise used to be the example and now stacks its tree to a
        width; CV(N)(C) cannot follow it, because its loader rejects a
        newline outright rather than choosing not to use one.
        """
        _out, err = call_both(["generate", "--width", "10", "CV(N)(C)", "0100"], capsys)
        assert "no effect on CV(N)(C)" in err

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


# 1.8s over 45 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 1.8s over 45 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 1.8s over 45 tests: drives the CLI as a subprocess.
@pytest.mark.medium
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
        # Exits 1 now -- a raise is the program's own failure, which is what
        # `run` has always called exit 1 -- but the report is still printed
        # first, which is the property under test.
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", _program(tmp_path, ",.")], capsys)
        assert exc.value.code == 1
        out = capsys.readouterr().out
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
        # 124 now, matching `run`: a bound that fired is not the same
        # outcome as a program that broke, and a script could not tell.
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", "--timeout", _LOOPS, "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        assert exc.value.code == 124
        assert "stopped: timeout" in capsys.readouterr().out


class TestTheLastResortPaths:
    """Refusals a reader only meets when something has already gone wrong.

    None of these are reachable from an ordinary command, which is why they
    had no tests -- and why the file having been edited is what surfaced
    them: the coverage rule is per touched *file*, so inheriting an
    untested corner is part of editing one.
    """

    def test_an_oversized_program_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A megabyte is far past anything this package generates."""
        path = tmp_path / "huge.bf"
        path.write_text("+" * (1024 * 1024 + 1))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "larger than" in capsys.readouterr().err

    def test_a_surrogate_outside_the_escape_range_is_left_alone(self) -> None:
        """``_smuggled_bytes`` gives up rather than guessing at a stray point.

        ``surrogateescape`` only round-trips the low-surrogate band it
        reserves for smuggled bytes.  Anything outside it is a code point
        the program meant rather than a byte the stream hid, so there is
        nothing to report about it.

        The band is described rather than written out: an escape for one
        of those code points inside a docstring compiles to a real
        surrogate, and pytest's assertion rewriter cannot re-serialize the
        module afterwards.
        """
        assert cli._smuggled_bytes("\udfff") is None  # noqa: SLF001 - private path

    def test_output_a_terminal_cannot_encode_is_written_as_bytes(self) -> None:
        """A lone surrogate reaches the byte stream rather than raising."""
        written: list[bytes] = []

        class _Narrow(io.StringIO):
            # utf-8, because the fallback re-encodes with ``surrogatepass``
            # and that is only defined for the utf codecs -- an ascii
            # stream would fail there for a different reason than the one
            # under test.
            encoding = "utf-8"
            buffer = type(
                "_Bytes",
                (),
                {
                    "write": lambda _s, data: written.append(data),
                    "flush": lambda _s: None,
                },
            )()

            def write(self, text: str) -> int:
                raise UnicodeEncodeError("ascii", text, 0, 1, "narrow")

        with patch.object(sys, "stdout", _Narrow()):
            cli._write_output("\ud800")  # noqa: SLF001 - the path is private
        assert written, "nothing reached the byte stream"

    def test_a_value_error_from_the_screen_is_a_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``run_tui`` reports an unusable terminal as a message, not a crash."""

        def boom(*_args: object, **_kwargs: object) -> None:
            raise ValueError("no room to draw")

        with (
            patch("esolangs.cli.run_tui", boom),
            patch.object(_FakeStdin, "isatty", lambda _self: True),
            pytest.raises(SystemExit) as exc,
        ):
            call_main(["debug", "--tui", "brainfuck", _program(tmp_path, "+")], capsys)
        assert exc.value.code == 2
        assert "no room to draw" in capsys.readouterr().err


class TestTheLastResortPathsContinued:
    """The rest of the corners, each reached deliberately."""

    def test_a_surrogate_pair_that_round_trips_reports_nothing(self) -> None:
        """Two escaped bytes can form a character, and then nothing is wrong.

        Each half is a byte ``surrogateescape`` hid, but together they are
        valid UTF-8 -- so the round trip succeeds and there is no decode
        error to hand back, which is the one way out of this function that
        neither returns early nor reports.
        """
        smuggled = "".join(chr(0xDC00 + byte) for byte in (0xC3, 0xA9))
        assert cli._smuggled_bytes(smuggled) is None  # noqa: SLF001 - private path

    def test_output_survives_a_stream_with_no_byte_buffer(self) -> None:
        """Some streams are text only, and then the escape is the best there is."""
        written: list[str] = []

        class _TextOnly(io.StringIO):
            encoding = "ascii"
            buffer = None

            def write(self, text: str) -> int:
                if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
                    raise UnicodeEncodeError("ascii", text, 0, 1, "narrow")
                written.append(text)
                return len(text)

        with patch.object(sys, "stdout", _TextOnly()):
            cli._write_output("a\udc80b")  # noqa: SLF001 - private path
        assert written
        assert "\\udc80" in written[0]

    def test_partial_output_already_ending_in_a_newline_gains_no_second_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The prefix is terminated so a pipe reads clean lines, once.

        A failed run writes what the program managed to print, and adds the
        newline only when the program did not -- otherwise a program whose
        last act was a newline would be followed by a blank line that it
        never printed.
        """
        failure = esolangs.HaltError("stopped")
        failure.partial_output = "Hi\n"
        cli._emit_partial(failure)  # noqa: SLF001 - private path
        assert capsys.readouterr().out == "Hi\n"

    def test_a_value_error_from_the_run_is_a_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bare ``ValueError`` out of the debugger names the language."""

        def boom(*_args: object, **_kwargs: object) -> None:
            raise ValueError("not a position")

        with (
            patch("esolangs.cli.make_debugger", boom),
            pytest.raises(SystemExit) as exc,
        ):
            call_main(["debug", "brainfuck", _program(tmp_path, "+")], capsys)
        assert exc.value.code == 2
        assert "brainfuck: not a position" in capsys.readouterr().err
