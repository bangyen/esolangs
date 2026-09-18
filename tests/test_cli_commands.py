"""The subcommands that run a program and judge what it printed.

run, debug, answer, evaluate and verify, plus the options they share --
``--judge``, ``--table``, ``--seed``, ``--json`` and ``--width``.
"""

import importlib
import inspect
import json
import random
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import cli_round_trip
from esolangs.cli import HELP
from tests.cli_support import _LOOPS, call_both
from tests.test_cli import _program, call_main


# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
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
            ["run", "--judge", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
            capsys,
        )
        assert out.strip() == "1"

    def test_run_judge_reads_a_halt_as_the_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And the other polarity, from the same program and a different row."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        out = call_main(
            ["run", "--judge", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
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


class TestASeedMakesARunRepeat:
    """LaserFuck's docstring named a remedy no public function offered.

    It said "a caller that needs a particular one passes an ``rng``" -- and
    ``run``, ``make_vm``, ``make_debugger``, ``evaluate`` and ``verify``
    all had no such parameter.  The only route was importing the private
    interpreter module and hand-building an ``IO``.  Ten identical runs of
    ``o+++.`` gave ``3`` five times and nothing five times.

    ``make_vm`` was never affected -- it always seeds from the
    interpreter's own ``reproducible_seed`` -- so stepping repeated and
    running did not, an asymmetry with nothing behind it.
    """

    PROGRAM = "o+++.\n"

    def test_a_seeded_run_repeats(self) -> None:
        """Six runs, one answer."""
        answers = {
            esolangs.run("LaserFuck", self.PROGRAM, "", 5, seed=0) for _ in range(6)
        }
        assert len(answers) == 1

    def test_the_seed_selects_rather_than_fixes_one_outcome(self) -> None:
        """A seed that always gave the same answer would prove nothing.

        Both outcomes this program can produce are reachable, so the draw
        is being fed rather than suppressed.
        """
        by_seed = {
            seed: esolangs.run("LaserFuck", self.PROGRAM, "", 5, seed=seed)
            for seed in range(8)
        }
        assert len(set(by_seed.values())) == 2
        assert by_seed[0] == "3"

    def test_no_seed_is_the_language_as_specified(self) -> None:
        """The default has to stay the system's randomness, not a fixed draw."""
        assert esolangs.run("LaserFuck", self.PROGRAM, "", 5) in {"", "3"}

    def test_a_seed_for_a_language_that_draws_nothing_is_refused(self) -> None:
        """Ignoring it would be right by accident and hide the likelier fault.

        The run repeats whatever happens, so silence would look correct --
        while the probable reading is that the caller has the wrong
        language.
        """
        with pytest.raises(esolangs.ArgumentError, match="draws no random values"):
            esolangs.run("brainfuck", "+++.", "", 5, seed=1)

    def test_the_seven_that_draw_are_the_seven_named(self) -> None:
        """The message lists them, so the list has to be right.

        Recomputed from the interpreters rather than trusted, since a
        language gaining a draw would leave the sentence quietly wrong.
        """
        drawing = [
            name
            for name in esolangs.list_languages()
            if "rng"
            in inspect.signature(
                importlib.import_module(
                    "esolangs.interpreters."
                    + str(esolangs.describe(name)["interpreter"])
                ).run
            ).parameters
        ]
        assert drawing == [
            "COD",
            "LaserFuck",
            "Modulous",
            "Painfuck",
            "Super SNUSP",
        ]
        with pytest.raises(esolangs.ArgumentError) as caught:
            esolangs.run("brainfuck", "+++.", "", 5, seed=1)
        for name in drawing:
            assert name in str(caught.value)

    def test_the_cli_takes_one(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """And repeats, which is the whole point of the flag."""
        path = tmp_path / "lf.txt"
        path.write_text(self.PROGRAM)
        args = ["run", "--timeout", "5", "--seed", "0", "LaserFuck", str(path)]
        assert call_both(args, capsys)[0] == call_both(args, capsys)[0] == "3"

    def test_the_cli_refuses_a_seed_that_is_not_a_number(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Named as a flag problem rather than a ValueError from further in."""
        path = tmp_path / "lf.txt"
        path.write_text(self.PROGRAM)
        with pytest.raises(SystemExit):
            call_main(
                ["run", "--timeout", "5", "--seed", "abc", "LaserFuck", str(path)],
                capsys,
            )
        assert "--seed must be a whole number" in capsys.readouterr().err

    def test_the_help_mentions_it(self) -> None:
        """A flag nobody can find is a flag nobody has."""
        assert "--seed" in HELP["run"]


class TestJsonOutput:
    """The reading layout is lossy, so scripting it meant reparsing prose.

    Three separate losses, all of which `--json` avoids rather than
    documents: a pair prints as ``0 1``, an empty field is dropped instead
    of shown, and the final ``input`` line is a sentence the CLI composes
    that is not a key at all.
    """

    def test_describe_json_is_the_dict_exactly(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Not "close to" -- the same keys and the same values."""
        out, _err = call_both(["describe", "--json", "brainfuck"], capsys)
        assert json.loads(out) == json.loads(json.dumps(esolangs.describe("brainfuck")))

    def test_describe_json_keeps_what_the_layout_drops(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The empty and the paired fields, which the columns cannot carry."""
        payload = json.loads(call_both(["describe", "--json", "brainfuck"], capsys)[0])
        assert payload["answer_pattern"] == ""  # dropped by the reading layout
        assert payload["answer_convention"] is None  # dropped as well
        assert payload["input_encoding"] == ["0", "1"]  # not the string "0 1"
        assert "input" not in payload  # the composed sentence is not a key

    def test_describe_json_works_for_every_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A field that is not JSON-serializable would fail on one language only."""
        for name in esolangs.list_languages():
            out, _err = call_both(["describe", "--json", name], capsys)
            assert json.loads(out)["name"] == name

    def test_describe_json_still_refuses_an_unknown_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The flag must not become a way past the error path."""
        with pytest.raises(SystemExit):
            call_main(["describe", "--json", "nosuchlang"], capsys)
        assert "nosuchlang" in capsys.readouterr().err

    def test_list_json_is_the_names(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Same order, same 65."""
        out, _err = call_both(["list", "--json"], capsys)
        assert json.loads(out) == esolangs.list_languages()

    def test_list_json_details_spells_out_the_markers(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The point of the flag: three booleans instead of a marker column."""
        rows = json.loads(call_both(["list", "--json", "--details"], capsys)[0])
        assert [row["name"] for row in rows] == esolangs.list_languages()
        for row in rows:
            facts = esolangs.describe(row["name"])
            assert row["boolean_generator"] == facts["boolean_generator"]
            assert row["parameterized"] == facts["parameterized"]
            assert row["has_example"] == bool(facts["examples"])

    def test_list_json_agrees_with_the_marker_column(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two renderings of one fact, so they are checked against each other."""
        rows = json.loads(call_both(["list", "--json", "--details"], capsys)[0])
        text, _err = call_both(["list", "--details"], capsys)
        lines = text.splitlines()[1:]  # the legend header
        assert len(lines) == len(rows)
        for line, row in zip(lines, rows, strict=True):
            marks = line[len(row["name"]) :].split()
            assert ("gen" in marks) == row["boolean_generator"]
            assert ("tmpl" in marks) == row["parameterized"]
            assert ("ex" in marks) == row["has_example"]

    def test_both_commands_still_reject_a_stray_argument(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json must not swallow the count check that guards each command."""
        with pytest.raises(SystemExit):
            call_main(["list", "--json", "extra"], capsys)
        with pytest.raises(SystemExit):
            call_main(["describe", "--json", "brainfuck", "extra"], capsys)


class TestTheTableOptionIsUsedByPlainRun:
    """It computed the check and threw the result away."""

    def test_an_out_of_range_row_is_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`check-stdin --table` refused this and `run --table` answered it."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        out, err = call_both(
            ["run", "--table", "0110", "Fargo", str(path)], capsys, stdin="9\n"
        )
        assert out  # still answers: plain `run` warns rather than refusing
        assert "out of range" in err

    def test_a_wrong_bit_count_is_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Clockwise's is a shorter line, invisible without the arity."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("Clockwise", "0110"))
        _out, err = call_both(
            ["run", "--table", "0110", "Clockwise", str(path)], capsys, stdin="101"
        )
        assert "wants 2 bits" in err

    def test_a_correct_input_stays_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A warning that fires on correct input is worth less than none."""
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        _out, err = call_both(
            ["run", "--table", "0110", "Fargo", str(path)],
            capsys,
            stdin=esolangs.encode_inputs("Fargo", [1, 0], "0110"),
        )
        assert err == ""

    def test_a_shape_complaint_is_said_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The library warns too, and both saying it is the old bug."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        _out, err = call_both(
            ["run", "--table", "0110", "Grapheme", str(path)], capsys, stdin="0\n1\n"
        )
        assert err.count("spells its bits") == 1

    def test_the_three_routes_agree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`check-stdin --table`, `run --judge --table` and `run --table`.

        They disagreed about the same stdin: two refused it and the third
        answered a row that does not exist.  They need not have the same
        *severity* -- plain `run` warns by design -- but they must all
        notice.
        """
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        with pytest.raises(SystemExit):
            call_main(["check-stdin", "--table", "0110", "Fargo"], capsys, stdin="9\n")
        assert "out of range" in capsys.readouterr().err
        with pytest.raises(SystemExit):
            call_main(
                ["run", "--judge", "--table", "0110", "Fargo", str(path)],
                capsys,
                stdin="9\n",
            )
        assert "out of range" in capsys.readouterr().err
        _out, err = call_both(
            ["run", "--table", "0110", "Fargo", str(path)], capsys, stdin="9\n"
        )
        assert "out of range" in err


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
        assert "unfilled runs of '$'" in capsys.readouterr().err

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

    def test_a_negative_break_at_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The third integer flag, and the one that had no such guard.

        It passed the is-an-integer check, reached ``break_at``'s own
        validation, and came back out of the catch-all as "this is a bug in
        esolangs" at exit 70 -- a bug report invited by a typo.
        """
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["debug", "--break-at", "-1", "brainfuck", _program(tmp_path, "+")],
                capsys,
            )
        assert exc.value.code == 2
        assert "--break-at must not be negative" in capsys.readouterr().err

    def test_an_internal_fault_is_still_reported_not_raised(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The last resort, planted rather than found.

        ``--break-at -1`` and ``--tui --stdin`` were the only two things in
        this suite that reached the catch-all, and both are refused at exit
        2 now -- so fixing them left the handler with no coverage and no
        test.  A fault has to be planted to exercise it honestly, since by
        construction nothing reachable should arrive there.
        """

        def boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("planted")

        with patch("esolangs.cli.describe", boom), pytest.raises(SystemExit) as exc:
            call_main(["describe", "brainfuck"], capsys)
        assert exc.value.code == 70
        err = capsys.readouterr().err
        assert "internal error: RuntimeError: planted" in err
        assert "not in your program" in err


class TestTheAnswerCommandDoesOneRow:
    """`verify` does every row; nothing did one, so a reader wrote a wrapper."""

    @pytest.mark.parametrize(
        ("bits", "expected"), [("00", "0"), ("01", "1"), ("10", "1"), ("11", "0")]
    )
    def test_it_answers_each_row_of_xor(
        self, bits: str, expected: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Both polarities, so a command that always printed 1 would fail."""
        out = call_main(["answer", "brainfuck", "0110", bits], capsys)
        assert out.strip() == expected

    @pytest.mark.parametrize(
        "name", ["Fargo", "Grapheme", "Clockwise", "Taglate", "Minifuck", "RAM0"]
    )
    def test_it_encodes_the_odd_shapes_for_you(
        self, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Which is the point: the encoding step is the one people get wrong."""
        assert call_main(["answer", name, "0110", "10"], capsys).strip() == "1"

    def test_it_supplies_a_bound_for_a_diverging_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A one-liner that needs a flag for three of sixty is not one."""
        assert call_main(["answer", "123", "0110", "01"], capsys).strip() == "1"
        assert call_main(["answer", "123", "0110", "00"], capsys).strip() == "0"

    @pytest.mark.slow
    def test_it_agrees_with_evaluate_everywhere(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Row by row against the whole-table command, for all sixty."""
        table = "0110"
        for name in esolangs.list_languages():
            for row, bits in enumerate(("00", "01", "10", "11")):
                got = call_main(["answer", name, table, bits], capsys).strip()
                assert got == table[row], f"{name} row {bits}"

    def test_bad_bits_are_refused(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Same refusal `encode` makes on the same argument."""
        with pytest.raises(SystemExit) as exc:
            call_main(["answer", "brainfuck", "0110", "1x"], capsys)
        assert exc.value.code == 2
        assert "bits must be a string of 0s and 1s" in capsys.readouterr().err

    def test_a_missing_argument_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Three positionals, so the shared machinery has to know about it."""
        with pytest.raises(SystemExit) as exc:
            call_main(["answer", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "missing <bits>" in capsys.readouterr().err


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


class TestTheTableOptionClosesTheArityGap:
    """`run` has no arity of its own; the table supplies one."""

    def test_a_wrong_bit_count_on_one_line_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Clockwise's underfeed is a shorter string, invisible without this."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Clockwise", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "--table", "0110", "Clockwise", str(path)],
                capsys,
                stdin="101",
            )
        assert exc.value.code == 2
        assert "wants 2 bits" in capsys.readouterr().err

    def test_an_out_of_range_row_index_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Fargo's 99 is not a row of a four-row table."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "--table", "0110", "Fargo", str(path)],
                capsys,
                stdin="99\n",
            )
        assert exc.value.code == 2
        assert "out of range" in capsys.readouterr().err

    def test_a_bit_string_row_index_is_refused_without_a_table(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The leading-zero rule needs no arity at all."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Fargo", "0010000000000000"))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "--judge", "Fargo", str(path)], capsys, stdin="0010\n")
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "leading zero" in err
        assert err.count("esolangs encode") == 1

    def test_the_right_input_still_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With --table, the correct stdin must stay silent."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Clockwise", "0110"))
        out, err = call_both(
            ["run", "--judge", "--table", "0110", "Clockwise", str(path)],
            capsys,
            stdin=esolangs.encode_inputs("Clockwise", [1, 0], "0110"),
        )
        assert out.strip() == "1"
        assert err == ""


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
        # With `--table`, because `--judge` now refuses a row-index language
        # without one: it cannot check the bit count from a single number,
        # and every other refusal it makes taught readers it would.
        out, err = call_both(
            ["run", "--judge", "--table", "10010110", "Fargo", str(path)],
            capsys,
            stdin="3\n",
        )
        assert out.strip() == "1"
        assert err == ""

    def test_an_out_of_range_index_is_no_longer_answered(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """This used to answer it, and this test used to say so.

        `run` still does not know the program's arity -- that has not
        changed -- but `--judge` no longer pretends it can judge without
        one: for a row-index language it refuses and names the two ways to
        supply the arity.  With `--table` the range check then fires.
        """
        path = tmp_path / "f.txt"
        path.write_text(esolangs.generate("Fargo", "10010110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "--judge", "Fargo", str(path)], capsys, stdin="8\n")
        assert exc.value.code == 2
        assert "cannot be checked from stdin alone" in capsys.readouterr().err

        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "--table", "10010110", "Fargo", str(path)],
                capsys,
                stdin="8\n",
            )
        assert exc.value.code == 2
        assert "out of range" in capsys.readouterr().err


class TestJudgeAdmitsWhatItCannotCheck:
    """It refuses every bad shape and then invented a bit for a bad arity."""

    def test_it_says_so_without_a_table(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Its other refusals teach a reader that --judge is the safe path."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "--judge", "Fargo", str(path)], capsys, stdin="2\n")
        assert exc.value.code == 2
        assert "bit count cannot be checked" in capsys.readouterr().err

    def test_with_a_table_it_refuses_an_out_of_range_row(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Row 5 of a four-row table does not exist."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Fargo", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "--table", "0110", "Fargo", str(path)],
                capsys,
                stdin="5\n",
            )
        assert exc.value.code == 2
        assert "out of range" in capsys.readouterr().err

    def test_the_note_is_absent_when_a_table_is_given(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It must not nag a caller who did the thing it asked for."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            ["run", "--judge", "--table", "0110", "brainfuck", str(path)],
            capsys,
            stdin="1\n0\n",
        )
        assert err == ""


class TestVerifyAndEvaluateTakeAWidth:
    """The CLI half of the same gap, parsed the way ``generate`` parses it."""

    def test_verify_accepts_a_width(self, capsys: pytest.CaptureFixture[str]) -> None:
        """And still says ok, because the wrap did not break the program."""
        out, err = call_both(
            ["verify", "--width", "40", "brainfuck", "10010110"], capsys
        )
        assert out.strip() == "ok"
        assert err == ""

    def test_evaluate_accepts_a_width(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A template language, so the width has to reach ``instantiate``."""
        out, _err = call_both(["evaluate", "--width", "40", "Minifuck", "0110"], capsys)
        assert out.strip() == "0110"

    def test_a_bare_width_takes_the_default(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """As it does on ``generate``, so the next word is the language."""
        out, _err = call_both(["verify", "--width", "brainfuck", "0110"], capsys)
        assert out.strip() == "ok"

    def test_a_width_that_ate_the_table_says_so(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width`` takes an optional N, which is a trap ``generate`` names.

        Without the note the complaint is about a missing truth table, which
        is baffling when you did type one.
        """
        with pytest.raises(SystemExit):
            call_main(["verify", "--width", "0110", "brainfuck"], capsys)
        assert "looks like a truth table" in capsys.readouterr().err

    def test_the_help_mentions_it(self) -> None:
        """A flag nobody can find is a flag nobody has."""
        assert "--width" in HELP["verify"]
        assert "--width" in HELP["evaluate"]


class TestTheRoundTripsFailurePaths:
    """The reporting a mismatch or a refusal goes through."""

    def test_a_generator_refusal_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Nothing ran, so it is the usage class rather than a wrong answer."""
        rng = random.Random(7)
        dense = "".join(rng.choice("01") for _ in range(1 << 11))
        with pytest.raises(SystemExit) as exc:
            call_main(["verify", "Polynomial", dense], capsys)
        assert exc.value.code == 2
        assert "caps at" in capsys.readouterr().err

    def test_a_mismatch_names_the_rows_that_disagree(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No language actually mismatches, so the reporting is driven here.

        Which is the point of testing it: the path that says *what went
        wrong* is the one a reader only ever reaches on a bad day, so it
        must not be the untested one.
        """
        monkeypatch.setattr(cli_round_trip, "evaluate", lambda *_a, **_k: "0000")
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
        monkeypatch.setattr(cli_round_trip, "evaluate", lambda *_a, **_k: "0000")
        assert call_main(["evaluate", "brainfuck", "0110"], capsys).strip() == "0000"


class TestTheAnswerCommandsFailurePaths:
    """What it does when the language or the table is wrong."""

    def test_an_unknown_language_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Resolved through the same suggester as everything else."""
        with pytest.raises(SystemExit) as exc:
            call_main(["answer", "NotALang", "0110", "10"], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_a_malformed_table_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And named as a table, at the usage exit code."""
        with pytest.raises(SystemExit) as exc:
            call_main(["answer", "brainfuck", "011", "10"], capsys)
        assert exc.value.code == 2
        assert "power-of-two" in capsys.readouterr().err

    def test_a_wrong_bit_count_is_named(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The table is right there, so the arity is always checkable here."""
        with pytest.raises(SystemExit) as exc:
            call_main(["answer", "brainfuck", "0110", "101"], capsys)
        assert exc.value.code == 2
        assert "3 bits were given" in capsys.readouterr().err


class TestEvaluateNeedsNoSeed:
    """``run`` takes a seed and ``evaluate``/``verify`` do not, which looks
    like a half-migration and is not.

    ``evaluate`` only ever runs programs this package *generated*, and
    those do not reach the random commands -- so a seed would be surface
    with no behaviour behind it.  Two reporters raised it and neither
    could make it flake; this is the check that says why.
    """

    @pytest.mark.parametrize(
        "language",
        ["COD", "LaserFuck", "Modulous", "Painfuck"],
    )
    def test_a_drawing_language_evaluates_the_same_every_time(
        self, language: str
    ) -> None:
        """The five that draw, less the slowest, four runs each."""
        answers = {esolangs.evaluate(language, "0110", timeout=30) for _ in range(4)}
        assert answers == {"0110"}

    def test_run_still_takes_one_because_it_takes_any_program(self) -> None:
        """The distinction: ``run`` executes what a caller wrote."""
        assert {
            esolangs.run("LaserFuck", "o+++.\n", "", 5, seed=0) for _ in range(4)
        } == {esolangs.run("LaserFuck", "o+++.\n", "", 5, seed=0)}


class TestALeadingZeroIndexNeverCrashes:
    """The message explaining a leading zero crashed on one."""

    @pytest.mark.parametrize("value", ["02", "07", "012", "089"])
    def test_a_non_binary_leading_zero_is_refused_cleanly(self, value: str) -> None:
        """`int('02', 2)` raises, so the friendly message threw a traceback."""
        with pytest.raises(esolangs.ArgumentError, match="leading zero"):
            esolangs.check_stdin("Fargo", f"{value}\n")

    @pytest.mark.parametrize("value", ["00", "01", "010", "011"])
    def test_a_binary_one_still_offers_the_index(self, value: str) -> None:
        """The helpful half must survive the fix to the crashing half."""
        with pytest.raises(esolangs.ArgumentError, match="if those are the input bits"):
            esolangs.check_stdin("Fargo", f"{value}\n")

    def test_the_suggested_index_is_right(self) -> None:
        """`010` as bits is row 2, and the message says so."""
        with pytest.raises(esolangs.ArgumentError, match="the index is 2"):
            esolangs.check_stdin("Fargo", "010\n")


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


class TestDebugReportsALoadFailure:
    """The clause between the template refusal and the interpreter's own."""

    def test_a_program_that_is_really_a_path_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` has refused this for rounds; `debug` shares the check."""
        example = esolangs.describe("brainfuck")["examples"][0]  # type: ignore[index]
        path = tmp_path / "p.txt"
        path.write_text(str(example))
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", str(path)], capsys, stdin="1\n0\n")
        assert exc.value.code == 2
        assert "looks like a path" in capsys.readouterr().err


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
