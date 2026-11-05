"""A Painter Ant through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from tests.support.cli_support import _program, call_both, call_main
from tests.support.generator_support import evaluate_generated
from tests.support.screen_support import _worst


class TestAMultiWordNameSuggestsQuoting:
    """`describe A Painter Ant` blamed the third word."""

    def test_the_joined_positionals_are_suggested(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["describe", "A", "Painter", "Ant"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "quote" in err.lower()
        assert "A Painter Ant" in err


class TestAPaintersMarkMustBeInAGrid:
    """Its pattern was ``([o@])``, so any stray ``o`` read as a zero."""

    def test_garbage_is_refused(self) -> None:
        with pytest.raises(esolangs.ProgramError):
            esolangs.read_answer("A Painter Ant", "hello world")

    def test_a_real_grid_still_reads(self) -> None:
        assert evaluate_generated("A Painter Ant", "0110") == "0110"


class TestPrintedCommandsCanBePasted:
    """The tool emitted commands it cannot itself parse."""

    def test_the_quoted_command_actually_runs(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out, _err = call_both(["describe", "--spec", "A Painter Ant"], capsys)
        assert out.startswith("Interpreter for A Painter Ant")


def test_a_painter_ant_is_the_one_that_cannot_be_stepped() -> None:
    """Stated as data: three million steps leave it with no output."""
    unsteppable = [
        n
        for n in esolangs.list_languages()
        if not esolangs.describe(n)["steppable_to_answer"]
    ]
    assert unsteppable == ["A Painter Ant"]

    from .oracle_checks import check_raw_a_painter_ant

    check_raw_a_painter_ant()


def test_run_read_answer_prints_the_bit_for_a_dump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    program = esolangs.instantiate(
        "A Painter Ant", esolangs.generate("A Painter Ant", "0110"), [0, 1]
    )
    out = call_main(["run", "A Painter Ant", _program(tmp_path, program)], capsys)
    assert esolangs.read_answer("A Painter Ant", out).strip() == "1"


@pytest.mark.medium
def test_unsupported_stepping_candidate_is_bounded() -> None:
    assert _worst("a_painter_ant", "nn$", "00", [0], 0.02) == (1, 0)
    assert _worst("a_painter_ant", "N$", "00", [1], 0.5) == (0, 0)


@pytest.mark.parametrize(
    ("source", "expected"), [("", "o"), ("P", "@"), ("ns", ".\no")]
)
def test_periodic_completion_renders_at_the_repeated_pass_boundary(source, expected):
    from esolangs.languages.a_painter_ant.interpreter import _Machine
    from esolangs.runtime._drive import drive_periodic
    from esolangs.runtime.io import ScriptedIO

    io = ScriptedIO()
    machine = _Machine(source, io)
    cycle = drive_periodic(machine, len(machine.prog))
    assert cycle.state == machine.snapshot()
    assert machine.ip == 0
    assert io.getvalue() == expected
    assert not machine.halted
    machine.step()
    assert io.getvalue() == expected


def test_native_completion_preserves_the_periodic_evidence():
    from esolangs.languages.a_painter_ant.interpreter import _execute, run
    from esolangs.runtime._lifecycle import Completion
    from esolangs.runtime.io import ScriptedIO

    io = ScriptedIO()
    report = _execute("P", io)
    assert report.kind is Completion.PERIODIC
    assert report.cycle is not None
    assert report.cycle.commands_per_pass == 1
    assert report.cycle.repeat_pass > report.cycle.first_pass
    assert io.getvalue() == "@"
    assert run("P", ScriptedIO()) is None
