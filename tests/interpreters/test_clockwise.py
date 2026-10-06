from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.clockwise import run
from esolangs.interpreters.io import IO, ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestClockwise:
    def test_truth_machine_zero(self) -> None:
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_the_accumulator_counts_past_one(self) -> None:
        """``+`` adds rather than sets, and ``;`` emits the low bit of a count."""
        assert run_and_capture(["++;S;S;S;S;S;+;R", "R              R"]) == "\x01"
        assert run_and_capture(["+;S;S;S;S;S;++;R", "R              R"]) == "@"

    def test_a_read_bit_leaves_the_accumulator_set(self) -> None:
        """``.`` puts the bit *into* the accumulator, sign and all."""
        assert run_and_capture([".+?", "R R"], inputs=["A"]) == ""

    def test_every_input_character_contributes_its_bits(self) -> None:
        """The bits of a second character are appended, not substituted."""
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["AB"]) == "AB"

    def test_a_bang_turns_when_the_accumulator_is_zero(self) -> None:
        """``!`` is the inverse of ``?``, and no program here used one."""
        assert run_and_capture(["  !", "! !"]) == ""
        # mixed with R corners, the ring still closes
        assert run_and_capture(["  !", "R R"]) == ""

    def test_unclosed_ring_rejected(self) -> None:
        with raises_message(ValueError, "Clockwise ring is not closed"):
            run_and_capture(["+;S"])

    def test_leaving_the_grid_is_rejected_rather_than_turned(self) -> None:
        """The edge does not turn a pointer that would otherwise leave."""
        with raises_message(ValueError, "Clockwise ring is not closed"):
            run_and_capture(["  ?", "R  "])


class TestMachineState:
    def test_a_ring_with_no_read_never_touches_the_input(self) -> None:
        """The bits are read at construction, but only if a ``.`` is there."""
        from esolangs.interpreters.grid_based.clockwise import _Machine

        io = ScriptedIO("A\n")
        _Machine(["+;S;S;S;S;S;+;R", "R             R"], io)
        assert io.position() == 0


class TestMove:
    """``move`` decides the turn, the step, and whether the ring goes on."""

    def test_a_position_off_the_grid_is_a_malformed_ring(self) -> None:
        """Each side of both bounds is rejected before the cell is read."""
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["  R", "R R"]
        for row, col in ((2, 0), (-1, 0), (0, 3), (0, -1)):
            with raises_message(ValueError, "Clockwise ring is not closed"):
                move(row, col, 0, grid, 0)

    def test_the_origin_is_only_ever_entered_heading_left_or_up(self) -> None:
        """The heading-right exception guards a state no caller can build."""
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["RR", "RR"]
        assert move(0, 1, 1, grid, 0)[:3] == (0, 0, 2)
        assert move(1, 0, 2, grid, 0)[:3] == (0, 0, 3)
        with raises_message(ValueError, "Clockwise ring is not closed"):
            move(0, -1, 3, grid, 0)

    def test_a_question_turns_once_when_nonzero(self) -> None:
        """``?`` tests whether ``acc`` is nonzero; its turn is one quarter."""
        from esolangs.interpreters.grid_based.clockwise import move

        counts = (0, 1, 2, 3, 4, -1)
        assert [move(1, 1, 0, ["???"] * 3, acc)[2] for acc in counts] == [
            0,
            1,
            1,
            1,
            1,
            1,
        ]
        assert [move(1, 1, 0, ["!!!"] * 3, acc)[2] for acc in (0, 1, 2)] == [1, 0, 0]
        assert [move(1, 1, 0, ["RRR"] * 3, acc)[2] for acc in (0, 1, 2)] == [1, 1, 1]


class TestStepMachine:
    def test_step_tracks_position_heading_and_accumulator(self) -> None:
        from esolangs.interpreters.grid_based.clockwise import _Machine

        machine = _Machine(["+;S;S;S;S;S;+;R", "R             R"], IO())
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 0, 0, 0)
        machine.step()  # + at the origin: acc 1, head right
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 1, 0, 1)
        machine.step()  # ; at row 0, col 1: parity bit queued
        assert (machine.row, machine.col, machine.r) == (0, 2, 0)
        machine.step()  # S at row 0, col 2: acc zeroed
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 3, 0, 0)

    def test_a_read_keeps_the_counts_above_the_low_bit(self) -> None:
        """``.`` clears the low bit and adds the input one, keeping the rest."""
        from esolangs.interpreters.grid_based.clockwise import _Machine

        machine = _Machine(["++.R", "  ?R", "R R "], ScriptedIO("A"))
        for _ in range(3):
            machine.step()
        assert machine.acc == 3

    def test_snapshot_includes_the_input_bits_and_their_rotation(self) -> None:
        """A consuming ``.`` rotates the input bit list, changing the snapshot."""
        from esolangs.interpreters.grid_based.clockwise import _Machine

        machine = _Machine(
            ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"],
            ScriptedIO("0"),
        )
        assert machine.io.position() == 1  # the whole input line was read up front
        for _ in range(3):
            machine.step()  # no '.' yet: the input is untouched
        before = machine.snapshot()
        machine.step()  # the '.' at (4,0) consumes the first bit and rotates it
        assert machine.snapshot() != before
        assert "".join(machine.inp) == "1100000"


def test_reading_with_no_input_is_eof() -> None:
    """Bits are read up front, so an empty queue is exhausted input."""
    from esolangs.interpreters.io import ScriptedIO

    with pytest.raises(EOFError) as caught:
        run(".", ScriptedIO(""))
    assert "0 characters supplied, read 1" in str(caught.value)
    assert any("1 input character" in note for note in caught.value.__notes__)


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.clockwise import _Machine

    return _Machine(code, IO())


class TestContract(EmptyProgramContract, CycleContract, StateViewContract):
    """The shared shapes."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    empty_program: ClassVar[list[str]] = []
    empty_raises = "Clockwise program cannot be empty"
    halting_program: ClassVar[list[str]] = ["+;S;S;S;S;S;+;R", "R             R"]
    # `out` holds the parity bits not yet flushed as a byte, so it fills as
    # the ring runs rather than only at the end.
    state_views: ClassVar[tuple[str, ...]] = ("out", "inp", "ip", "memory")
    viewing_program: ClassVar[list[str]] = ["+;S;S;S;S;S;+;R", "R             R"]
    # The machine hook supplies no stdin, so the input cursor has
    # nothing to consume and cannot move.
    constant_views: ClassVar[frozenset[str]] = frozenset({"inp"})
    looping_program: ClassVar[list[str]] = ["SS?R ", "+?+S-", "R!!RS"]


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_out_is_the_output_buffer_and_inp_the_input(self) -> None:
        """Two steps in, one parity bit is queued and no input has been read."""
        machine = _machine(["+;S;S;S;S;S;+;R", "R             R"])
        machine.step()
        machine.step()
        assert machine.out == ("1",)
        assert machine.inp == ()

    def test_ip_carries_the_heading_and_memory_the_accumulator(self) -> None:
        """``ip`` is three numbers, not two."""
        machine = _machine(["+;S;S;S;S;S;+;R", "R             R"])
        machine.step()
        machine.step()
        assert machine.ip == (0, 2, 0)
        assert machine.memory == [1]
