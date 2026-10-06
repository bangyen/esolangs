"""The subcommands that run a program and judge what it printed."""

import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.cli import HELP
from tests.cli_support import _LOOPS, call_both
from tests.generator_support import evaluate_generated
from tests.stdin_check import _check_stdin
from tests.test_cli import _program, call_main


# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestTheShellCanJudgeAnAnswer:
    """Nine languages could be run from the CLI and not judged from it."""

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
        assert "--timeout" in err
        assert "observe" in err

    def test_read_answer_says_so_when_given_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An empty pipe is a mistake, not an answer of zero."""
        with pytest.raises(SystemExit) as exc:
            call_main(["read-answer", "brainfuck"], capsys, stdin="")
        assert exc.value.code == 2
        assert "nothing on stdin" in capsys.readouterr().err

    def test_run_read_answer_prints_the_bit_for_a_dump(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A Painter Ant's grid, reduced through the separate answer reader."""
        program = esolangs.instantiate(
            "A Painter Ant", esolangs.generate("A Painter Ant", "0110"), [0, 1]
        )
        out = call_main(["run", "A Painter Ant", _program(tmp_path, program)], capsys)
        assert esolangs.read_answer("A Painter Ant", out).strip() == "1"

    def test_run_timeout_is_the_one_for_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """For the four that answer by diverging, the timeout carries the 1."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
                capsys,
            )
        assert exc.value.code == 124
        assert "answers 1 by not terminating" in capsys.readouterr().err

    def test_run_halt_is_the_zero_for_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And the other polarity, from the same program and a different row."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        out, err = call_both(
            ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
            capsys,
        )
        assert out == ""
        assert err == ""


class TestASeedMakesARunRepeat:
    """LaserFuck's docstring named a remedy no public function offered."""

    PROGRAM = "o+++.\n"

    def test_a_seeded_run_repeats(self) -> None:
        """Six runs, one answer."""
        answers = {
            esolangs.run("LaserFuck", self.PROGRAM, "", 5, seed=0) for _ in range(6)
        }
        assert len(answers) == 1

    def test_the_seed_selects_rather_than_fixes_one_outcome(self) -> None:
        """A seed that always gave the same answer would prove nothing."""
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
        """Ignoring it would be right by accident and hide the likelier fault."""
        with pytest.raises(esolangs.ArgumentError, match="draws no random values"):
            esolangs.run("brainfuck", "+++.", "", 5, seed=1)

    def test_a_seed_of_an_unseedable_type_is_an_argument_error(self) -> None:
        """``random.Random`` raised a bare TypeError through the public API."""
        with pytest.raises(esolangs.ArgumentError):
            esolangs.run("LaserFuck", self.PROGRAM, "", 5, seed=object())

    def test_a_surrogate_string_seed_is_an_argument_error(self) -> None:
        """A surrogate is a ``UnicodeEncodeError``, also not an EsolangError."""
        with pytest.raises(esolangs.ArgumentError):
            esolangs.run("LaserFuck", self.PROGRAM, "", 5, seed="\ud800")

    def test_the_languages_that_draw_are_the_ones_named(self) -> None:
        """The message lists them, so the list has to be right."""
        drawing = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["interpreter"] is not None
            if "rng"
            in inspect.signature(
                importlib.import_module(
                    "esolangs.interpreters."
                    + str(esolangs.describe(name)["interpreter"])
                ).run
            ).parameters
        ]
        assert drawing == [
            "Befunge",
            "Befunge-98",
            "Fish",
            "LaserFuck",
            "Modulous",
            "Painfuck",
            "Super SNUSP",
            "Thue",
            "thisthat",
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
    """The reading layout is lossy, so scripting it meant reparsing prose."""

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
        """The third integer flag, and the one that had no such guard."""
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
        """The last resort, planted rather than found."""

        def boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("planted")

        with patch("esolangs.cli.describe", boom), pytest.raises(SystemExit) as exc:
            call_main(["describe", "brainfuck"], capsys)
        assert exc.value.code == 70
        err = capsys.readouterr().err
        assert "internal error: RuntimeError: planted" in err
        assert "not in your program" in err


class TestPrivateEvaluationNeedsNoSeed:
    """``run`` takes a seed and the private evaluation harness does not, which looks
    like a half-migration and is not.
    """

    @pytest.mark.parametrize(
        "language",
        ["LaserFuck", "Modulous", "Painfuck"],
    )
    def test_a_drawing_language_evaluates_the_same_every_time(
        self, language: str
    ) -> None:
        """The four that draw, less the slowest, four runs each."""
        answers = {evaluate_generated(language, "0110", timeout=30) for _ in range(4)}
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
            _check_stdin("Fargo", f"{value}\n")

    @pytest.mark.parametrize("value", ["00", "01", "010", "011"])
    def test_a_binary_one_still_offers_the_index(self, value: str) -> None:
        """The helpful half must survive the fix to the crashing half."""
        with pytest.raises(esolangs.ArgumentError, match="if those are the input bits"):
            _check_stdin("Fargo", f"{value}\n")

    def test_the_suggested_index_is_right(self) -> None:
        """`010` as bits is row 2, and the message says so."""
        with pytest.raises(esolangs.ArgumentError, match="the index is 2"):
            _check_stdin("Fargo", "010\n")

    def test_a_large_binary_index_is_refused_without_rendering_it(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="15001 input bits") as caught:
            _check_stdin("Fargo", "0" + "1" * 15000)
        assert "leading zero" in str(caught.value)
        assert len(str(caught.value)) < 200


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
        debugger = debugger_api.make_debugger("Circuit Diagram", program, stdin)
        assert debugger.ip is None
        debugger.break_at(3)
        debugger.break_at((1, 2))


def test_run_reports_an_interpreter_warning_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import warnings

    def run(*_args, **_kwargs):
        warnings.warn("interpreter notice", UserWarning, stacklevel=1)
        return "result"

    monkeypatch.setattr("esolangs.cli_run.run", run)
    out, err = call_both(
        ["run", "--timeout", "1", "brainfuck", _program(tmp_path, ".")], capsys
    )
    assert out == "result"
    assert err.count("interpreter notice") == 1


def _portable(tmp_path, language="brainfuck", table="0110", settings=None):
    program = esolangs.generate(language, table, settings=settings)
    path = tmp_path / "program.json"
    path.write_text(
        esolangs.dump_program(language, program, settings=settings), encoding="utf-8"
    )
    return path


def test_set_pairs_match_settings_json(capsys):
    by_set, _ = call_both(
        ["generate", "--set", "expression_syntax=postfix", "Alight", "0110"], capsys
    )
    by_json, _ = call_both(
        [
            "generate",
            "--settings",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert by_set == by_json


def test_short_settings_and_portable_flags(capsys, tmp_path):
    output, error = call_both(
        [
            "generate",
            "-p",
            "-s",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert error == ""
    assert json.loads(output)["language"] == "Alight"
    path = tmp_path / "program.json"
    path.write_text(output, encoding="utf-8")
    output, error = call_both(["generate", "-p", "brainfuck", "0110"], capsys)
    assert error == ""
    path.write_text(output, encoding="utf-8")
    stdin = esolangs.encode_inputs("brainfuck", [1, 0], "0110")
    output, error = call_both(["run", "-p", str(path)], capsys, stdin)
    assert output.strip() == "1"
    assert error == ""


def test_unknown_settings_key_suggests_the_fix(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(
            [
                "generate",
                "--settings",
                '{"expressoin_syntax":"postfix"}',
                "Alight",
                "0110",
            ],
            capsys,
        )
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "did you mean expression_syntax" in error
    assert "Alight accepts: expression_syntax" in error


@pytest.mark.parametrize("command", ["run", "debug"])
def test_portable_language_can_be_omitted(command, capsys, tmp_path):
    path = _portable(tmp_path)
    stdin = esolangs.encode_inputs("brainfuck", [1, 0], "0110")
    if command == "run":
        args = ["run", "--portable", str(path)]
        expected = "1"
    else:
        args = ["debug", "--portable", "--steps", "100000", str(path)]
        expected = "halted: yes"
    output, error = call_both(args, capsys, stdin)
    assert expected in output
    assert error == ""


def test_describe_leads_with_the_contract(capsys):
    output, _error = call_both(["describe", "Fargo"], capsys)
    assert output.startswith("Fargo\ninput: one decimal row index")
    assert output.index("input:") < output.index("input_shape")
    assert "proof_status" not in output
    assert "{'labels'" not in output
    assert "Interpreter for Fargo" not in output
    assert "esolangs describe --spec Fargo" in output


def test_describe_template_still_hides_stdin_fields(capsys):
    output, _error = call_both(["describe", "Minifuck"], capsys)
    assert "input_shape" not in output
    assert "generate --bits" in output
