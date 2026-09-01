"""Unit tests for the Suffolk interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.suffolk import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestSuffolk:
    def test_count_and_output(self) -> None:
        """66 increments of the counter then a print yields 'A'."""
        assert run_and_capture("!" * 66 + "<.") == "A"

    def test_other_value(self) -> None:
        assert run_and_capture("!" * 70 + "<.") == "E"

    def test_output_requires_accumulator(self) -> None:
        """A . with no accumulated value prints nothing.

        ``!`` clears the accumulator on its way out, so the ``.`` that
        follows has nothing to print; the ``<<!`` puts cell 0 back so the
        program ends rather than incrementing it forever.
        """
        assert run_and_capture("!.<<!") == ""

    def test_no_halt_without_instruction(self) -> None:
        """A program that writes nothing still ends, and prints nothing.

        ``!!!!`` alone grows cell 0 by one per pass forever, so it has no
        stop of its own; ``<<!`` puts the cell back, which makes the state
        repeat and ends the run.  That is the shape every program the
        generators emit has, spelled out at its smallest.
        """
        assert run_and_capture("!!!!<<!") == ""

    def test_move_right(self) -> None:
        """> moves the pointer to a new tape cell.

        Driven a step at a time rather than through ``run``: the trailing
        ``!`` leaves the accumulator loaded at the wrap, so the ``.`` fires
        again on the second pass and a whole-program run would print twice
        before its state repeated.  What is under test is where ``>`` puts
        the pointer, which one pass settles.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        program = "!!!!!!!!>!><<<<<<<<<.!"
        machine = _Machine(program, ScriptedIO())
        for _ in range(len(program)):
            machine.step()
        assert machine.io.getvalue() == "@"

    def test_input(self) -> None:
        """, reads input into the accumulator.

        One pass at the machine, for the same reason as above: a second
        ``,`` has no input left, and what is under test is the first read.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("B\n"))
        machine.step()
        machine.step()
        assert machine.io.getvalue() == "A"

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed.

        The message is matched whole, and with its casing: ``match="empty"``
        is a substring search, so the wording could drift to anything that
        still contains the word and no test would say so.
        """
        import pytest

        with pytest.raises(ValueError, match=r"^Suffolk program cannot be empty$"):
            run("", IO())

    def test_a_repeated_state_ends_the_run(self) -> None:
        """``run`` stops on a proof, not a count.

        This replaced a test pinning a ten-pass default.  The count was
        arbitrary -- the wiki's rerun is infinite, so any number would have
        done -- and it decided nothing: ``!<.`` printed ten bytes because
        ten was the number, not because the program was finished.  A program
        that returns to a state it has been in cannot do anything new, so
        the run ends there and the byte is printed once.
        """
        assert run_and_capture("!<.<<!") == "\x00"

    def test_a_program_that_never_repeats_raises(self) -> None:
        """The step cap is the backstop for what neither stop covers.

        A cell growing without bound never repeats a state, and a program
        that reads nothing never runs out of input, so ``!`` alone would run
        forever.  Reaching the cap raises rather than returning quietly: a
        program the run could not decide is not reported as finished.
        """
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError, match="exceeded"):
            run("!", IO(), steps=500)

    def test_the_step_cap_defaults_to_a_million(self) -> None:
        """The default is pinned, since every other call passes its own.

        Nothing generated comes near the cap, so its value is invisible in
        every other test and could drift to anything.  The message carries
        it, which is the cheapest place to read it back.
        """
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError, match=r"^execution exceeded the 1000000-"):
            run("!", IO())

    def test_pointer_walks_past_the_second_cell(self) -> None:
        """Consecutive > keep incrementing the pointer, they do not set it.

        ``test_move_right`` returns to the origin with ``<`` before the
        distance matters, so a pointer *pinned* at 1 behaved identically.
        Three ``>`` in a row have to reach cell 3.
        """
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(">>>!", IO())
        for expected in (0, 1, 2, 3):
            assert machine.ptr == expected
            machine.step()
        assert machine.tape == [0, 0, 0, 1]

    def test_cell_clamps_at_zero(self) -> None:
        """! floors the cell at 0 when the accumulator overshoots.

        ``!`` writes ``tape[ptr] + 1 - acc``, which goes negative once the
        accumulator exceeds the cell: three increments give ``acc`` 3, and
        ``!`` on a fresh cell computes ``0 + 1 - 3 = -2``.  Nothing else here
        drives the expression below zero, so the floor was never exercised.
        """
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!!<>!", IO())
        for _ in range(6):
            machine.step()
        assert machine.tape == [3, 0]

    def test_accumulator_is_subtracted_at_the_cell(self) -> None:
        """! subtracts the accumulator rather than adding it.

        With ``acc`` 2 on a cell holding 2 the result is ``2 + 1 - 2 = 1``;
        adding instead would give 5.  Every other ``!`` here runs with an
        empty accumulator, where the two agree.
        """
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!<!", IO())
        for _ in range(4):
            machine.step()
        assert machine.tape == [1]

    def test_empty_input_clears_the_accumulator(self) -> None:
        """, on an empty line leaves the accumulator at zero, not one."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("\n"))
        machine.step()
        assert machine.acc == 0


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!", IO())
        before = machine.snapshot()
        machine.step()  # ! sets the current cell from the accumulator
        assert machine.snapshot() != before
        assert machine.tape == [1]

    def test_halted_is_always_false(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(".", IO())
        assert machine.halted is False
        for _ in range(5):
            machine.step()
        assert machine.halted is False

    def test_step_wraps_at_code_end(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!.", IO())
        machine.step()  # !
        assert machine.ind == 1
        assert machine.tape == [1]
        machine.step()  # .
        assert machine.ind == 0  # wrapped past the last instruction

    def test_cycle_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # "." never changes state, so the snapshot repeats immediately
        assert run_until_halt_or_cycle(_Machine(".", IO())) is False
        assert run_until_halt_or_cycle(_Machine("<", IO())) is False

    def test_snapshot_includes_the_input_cursor(self) -> None:
        """Reading a byte changes the state, even when nothing else does.

        ``,`` adds the byte into the accumulator, so a program that reads
        the same value twice leaves the tape and accumulator looking
        untouched between the two reads -- identical on every field except
        how much input is left.  Without the cursor those compare equal, and
        the detector calls a program periodic when it is one read away from
        EOF.  Two boolean-generator programs did exactly that.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",", ScriptedIO("\x00\n\x00\n"))
        before = machine.snapshot()
        machine.step()  # consumes a line; acc stays 0 because the byte is NUL
        assert machine.acc == before[2]  # nothing else moved
        assert machine.snapshot() != before

    def test_a_program_that_reads_is_not_called_periodic(self) -> None:
        """A read one byte from EOF must not be reported as a hang.

        The cursor makes each read a fresh state, so the detector runs the
        program out to the ``EOFError`` instead of stopping at a repeat that
        only looked like one.
        """
        import pytest

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(",.", ScriptedIO("A\n"))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine)

    def test_snapshot_excludes_pass_count(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        # "." is a no-op when acc is 0, so the state after one whole pass
        # (len(code) steps) equals the initial state -- the pass count must
        # not be part of snapshot, or every state would be unique and the
        # cycle detector would never fire.
        machine = _Machine("..", IO())
        before = machine.snapshot()
        machine.step()
        machine.step()  # one whole pass
        assert machine.snapshot() == before
