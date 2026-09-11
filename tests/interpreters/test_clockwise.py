"""Unit tests for the Clockwise interpreter."""

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


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestClockwise:
    def test_output_character(self) -> None:
        """Pushing bits 1000001 outputs 'A'."""
        code = ["+;S;S;S;S;S;+;R", "R             R"]
        assert run_and_capture(code) == "A"

    def test_truth_machine_zero(self) -> None:
        """Truth-machine with input 0 halts after outputting '0'."""
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_the_accumulator_counts_past_one(self) -> None:
        """``+`` adds rather than sets, and ``;`` emits the low bit of a count.

        Every ring here incremented from zero and emitted before
        incrementing again, so the accumulator never held more than one at
        an output -- where adding one and assigning one agree, and taking
        it modulo 2 agrees with any larger modulus.  Two increments before
        the emit separate all three: the bit is 0, since 2 is even.
        """
        assert run_and_capture(["++;S;S;S;S;S;+;R", "R              R"]) == "\x01"
        assert run_and_capture(["+;S;S;S;S;S;++;R", "R              R"]) == "@"

    def test_a_read_bit_leaves_the_accumulator_set(self) -> None:
        """``.`` puts the bit *into* the accumulator, sign and all.

        The read clears the low bit and adds the input one, and the only
        program that exercised it emitted straight away -- where the parity
        the ``;`` takes is the same whether the bit was added or subtracted
        (-1 and 1 are both odd).  The turn is not.  One ``+`` after the read
        leaves 2 against 0, and ``?`` turns a quarter for every count it
        holds, so 2 reverses the pointer and it walks back west to the
        origin and halts, while 0 holds course off the edge of the ring.
        Row 1 is never entered either way.  The first bit of ``A`` is 1.
        """
        assert run_and_capture([".+?", "R  "], inputs=["A"]) == ""

    def test_every_input_character_contributes_its_bits(self) -> None:
        """The bits of a second character are appended, not substituted.

        Input is read up front and flattened into a bit list, and every
        program here was given a single character -- where appending to the
        list and replacing it outright come to the same thing.  Two
        characters separate them: the program echoes both only if the first
        one's bits are still there when it gets to them.
        """
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["AB"]) == "AB"

    def test_a_bang_turns_when_the_accumulator_is_zero(self) -> None:
        """``!`` is the inverse of ``?``, and no program here used one.

        The truth machine covers ``?``, which turns on a *set* accumulator;
        nothing covered the corner that turns on a clear one.  With the
        accumulator left at zero a ``!`` steers exactly as an ``R`` does,
        so a ring built from them closes -- and stops closing the moment
        the condition is read the other way round.
        """
        assert run_and_capture(["  !", "! !"]) == ""
        # mixed with R corners, the ring still closes
        assert run_and_capture(["  !", "R R"]) == ""

    def test_unclosed_ring_rejected(self) -> None:
        """A pointer that walks off the ring is a malformed program."""
        with pytest.raises(ValueError, match=r"^Clockwise ring is not closed$"):
            run_and_capture(["+;S"])

    def test_leaving_the_grid_is_rejected_rather_than_turned(self) -> None:
        """The edge does not turn a pointer that would otherwise leave.

        The one-row program above cannot say which happens, because a turn
        at that edge leaves the grid as well.  Here a clockwise turn would
        land on row 1 and close the ring, and the pointer walks off anyway.
        """
        with pytest.raises(ValueError, match=r"^Clockwise ring is not closed$"):
            run_and_capture(["  ?", "R  "])


class TestMachineState:
    def test_a_fresh_machine_reports_a_boolean(self) -> None:
        """``halted`` starts as False itself, not merely as something falsey.

        Every other read of it is a truthiness test, which ``None`` passes
        just as well, so the flag could start un-set rather than unset and
        nothing would object -- while ``halted`` is annotated a bool.
        """
        from esolangs.interpreters.grid_based.clockwise import _Machine

        assert _Machine(["  R", "R R"], ScriptedIO()).halted is False

    def test_a_ring_with_no_read_never_touches_the_input(self) -> None:
        """The bits are read at construction, but only if a ``.`` is there.

        That guard is what lets the contracts below hand the machine a bare
        ``IO()``: a construction that read unconditionally would prompt for
        a line nothing supplies.
        """
        from esolangs.interpreters.grid_based.clockwise import _Machine

        io = ScriptedIO("A\n")
        _Machine(["+;S;S;S;S;S;+;R", "R             R"], io)
        assert io.position() == 0


class TestMove:
    """``move`` decides the turn, the step, and whether the ring goes on.

    Every other test drives it through a whole program, where a ring that
    stays closed hides which of its answers were right.  These call it at
    the positions a program cannot reach without already having failed.
    """

    def test_a_position_off_the_grid_is_a_malformed_ring(self) -> None:
        """Each side of both bounds is rejected before the cell is read.

        Reaching past the last row has to be refused rather than indexed:
        a non-strict bound there raises IndexError from inside instead of
        the ring's own error.
        """
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["  R", "R R"]
        for row, col in ((2, 0), (-1, 0), (0, 3), (0, -1)):
            with pytest.raises(ValueError, match=r"^Clockwise ring is not closed$"):
                move(row, col, 0, grid, 0)

    def test_the_pointer_reports_when_it_is_back_at_the_origin(self) -> None:
        """Returning to (0, 0) ends the run, except heading right.

        A program only ever reaches that moment once -- at the end, where
        stopping and having stopped look alike.  Called directly, all four
        headings say which of them keeps going.  *Which* of the flag's
        three terms answers is the next test's business: these four values
        are the first two, and come out the same with the third deleted.
        """
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["RR", "RR"]
        assert [move(0, 0, r, grid, 0)[4] for r in range(4)] == [1, -1, -1, 1]

    def test_the_origin_is_only_ever_entered_heading_left_or_up(self) -> None:
        """The heading-right exception guards a state no caller can build.

        A step onto (0, 0) heading right would have to start from (0, -1),
        which is off the grid and refused before the cell is read.  Both
        headings that *can* arrive halt, so the third term never decides a
        run -- it is a guard, and this is the shape of it.
        """
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["RR", "RR"]
        assert move(0, 1, 1, grid, 0)[:3] == (0, 0, 2)
        assert move(1, 0, 2, grid, 0)[:3] == (0, 0, 3)
        with pytest.raises(ValueError, match=r"^Clockwise ring is not closed$"):
            move(0, -1, 3, grid, 0)

    def test_a_question_turns_a_quarter_for_every_count_it_holds(self) -> None:
        """``?`` turns ``acc`` quarters, not one.

        Every ring in this file reaches a ``?`` holding 0 or 1, where the
        two readings agree; they part at 2, which is a half-turn that sends
        the pointer back the way it came.  ``R`` and ``!`` are the single
        quarter-turn they look like -- ``!`` *tests* the accumulator, so it
        can only be a bool, while ``?`` is the accumulator itself.
        """
        from esolangs.interpreters.grid_based.clockwise import move

        counts = (0, 1, 2, 3, 4, -1)
        assert [move(1, 1, 0, ["???"] * 3, acc)[2] for acc in counts] == [
            0,
            1,
            2,
            3,
            0,
            3,
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
        """``.`` clears the low bit and adds the input one, keeping the rest.

        Every other ``.`` in this file runs with the accumulator at 0 or 1,
        where merging the bit in and replacing the accumulator outright come
        to the same thing.  Two increments before the read separate them:
        the first bit of ``A`` is 1, so 2 becomes 3, not 1.
        """
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

    with pytest.raises(EOFError):
        run(".", ScriptedIO("\n"))


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.clockwise import _Machine

    return _Machine(code, IO())


class TestContract(EmptyProgramContract, CycleContract, StateViewContract):
    """The shared shapes.

    The halt condition is a return to the origin with a non-zero heading,
    so the looping ring's closed orbit is a finite-state cycle the detector
    can prove without waiting out a timeout.
    """

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
    """The named views read the slots they claim, not one another.

    The shared contract checks that each view *moves*; which slot it moves
    with is this file's business, because only this file knows which of its
    names could be confused for each other.  A value pinned at a step where
    they hold different things is what a rewiring would change.
    """

    def test_out_is_the_output_buffer_and_inp_the_input(self) -> None:
        """Two steps in, one parity bit is queued and no input has been read."""
        machine = _machine(["+;S;S;S;S;S;+;R", "R             R"])
        machine.step()
        machine.step()
        assert machine.out == ("1",)
        assert machine.inp == ()

    def test_ip_carries_the_heading_and_memory_the_accumulator(self) -> None:
        """``ip`` is three numbers, not two.

        Where the program is includes which way it faces: the same cell
        continues differently depending on it, so a heading-less ``ip``
        would report one position for two states.  ``memory`` is the
        accumulator boxed as this language's single addressable cell.
        """
        machine = _machine(["+;S;S;S;S;S;+;R", "R             R"])
        machine.step()
        machine.step()
        assert machine.ip == (0, 2, 0)
        assert machine.memory == [1]
