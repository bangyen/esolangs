"""thisthat instruction and concurrency semantics."""

# ruff: noqa: SLF001 - instruction primitives are the semantic test surface.

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.thisthat import _Machine, _Pointer, run
from esolangs.interpreters.io import ScriptedIO


def test_invalid_programs_abort() -> None:
    with pytest.raises(HaltError, match="at least one"):
        _Machine([], ScriptedIO(""))
    with pytest.raises(HaltError, match="unsupported thisthat cell"):
        _Machine(["▣x"], ScriptedIO(""))
    with pytest.raises(HaltError, match="must be a bit"):
        run(["▣─◇"], ScriptedIO("x\n"))


def test_multiple_starts_halt_everything() -> None:
    machine = _Machine(["▣─◉─▣"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.pointers == ()


def test_specification_truth_machine() -> None:
    source = """     ◇
     ║
    ┌□─◉
▣─◇═◒  ┌┐
    └▶─■┘
       ║
       ◇"""
    for bit in "01":
        io = ScriptedIO(bit + "\n")
        run(source.splitlines(), io)
        assert io.getvalue() == bit


def test_branching_protocol_covers_random_input_plain_and_halted() -> None:
    random = _Machine(["▣═◘═◇"], ScriptedIO(""))
    random.pointers = (
        _Pointer((2, 0), (1, 0), "data", 0),
        _Pointer((2, 0), (3, 0), "data", 1),
    )
    assert len(random.branching_successors(random.branching_snapshot(), 10) or ()) == 2

    reading = _Machine(["▣─◇"], ScriptedIO(""))
    reading.step()
    reading.step()
    assert reading.branching_successors(reading.branching_snapshot(), 10) is None

    plain = _Machine(["▣─◯"], ScriptedIO(""))
    assert len(plain.branching_successors(plain.branching_snapshot(), 10) or ()) == 1

    halted = _Machine(["▣─◉"], ScriptedIO(""))
    while not halted.halted:
        halted.step()
    state = halted.branching_snapshot()
    assert halted.branching_halted(state)
    assert halted.branching_successors(state, 10) == (state,)

    assert not halted.branching_halted(None)
    with pytest.raises(TypeError, match="branch state"):
        halted.branching_successors(None, 10)
    with pytest.raises(TimeoutError, match="random merges"):
        random.branching_successors(random.branching_snapshot(), 1)


def test_unreachable_bad_cell_still_aborts() -> None:
    machine = _Machine(["▣─"], ScriptedIO(""))
    machine.grid = ("▣x",)
    with pytest.raises(HaltError, match="unsupported thisthat cell"):
        machine._advance_one(_Pointer((1, 0), (0, 0)), [])
