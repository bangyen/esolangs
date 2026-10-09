"""The subcommands that run a program and judge what it printed."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from tests.cli.test_cli import _program, call_main
from tests.cli_support import _LOOPS, _refused, call_both
from tests.generator_support import evaluate_generated


# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestTheShellCanJudgeAnAnswer:
    """Some languages could be run from the CLI and not judged from it."""

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
        assert payload["answer_pattern"] is None  # dropped by the reading layout
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
            esolangs.run("LaserFuck", "o+++.\n", stdin="", timeout=5, seed=0)
            for _ in range(4)
        } == {esolangs.run("LaserFuck", "o+++.\n", stdin="", timeout=5, seed=0)}


class TestTheWidthFlagDoesNotEatTheTable:
    """`--width` takes an optional N, so it swallowed the truth table."""

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


@pytest.mark.parametrize("command", ["run", "debug"])
def test_portable_language_can_be_omitted(command, capsys, tmp_path):
    path = _portable(tmp_path)
    stdin = esolangs.encode_inputs("brainfuck", [1, 0], truth_table="0110")
    if command == "run":
        args = ["run", "--portable", str(path)]
        expected = "1"
    else:
        args = ["debug", "--portable", "--steps", "100000", str(path)]
        expected = "halted: yes"
    output, error = call_both(args, capsys, stdin)
    assert expected in output
    assert error == ""


#: Commands refused with exit code 2, and what stderr must say.
#: ``prog:SRC`` is a file holding SRC; a third item is stdin.
_REFUSALS = {
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
