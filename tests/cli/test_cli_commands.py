"""The subcommands that run a program and judge what it printed."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from tests.cli.test_cli import _program, call_main
from tests.cli_support import call_both
from tests.generator_support import evaluate_generated
from tests.pick import languages


# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 5.2s over 33 tests: drives the CLI as a subprocess.
@pytest.mark.medium
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

    @pytest.mark.parametrize("language", languages(random=True, boolean_generator=True))
    def test_a_drawing_language_evaluates_the_same_every_time(
        self, language: str
    ) -> None:
        """Every language that draws, four runs each."""
        answers = {evaluate_generated(language, "0110", timeout=30) for _ in range(4)}
        assert answers == {"0110"}


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
