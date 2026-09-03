"""Unit tests for the Painfuck interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

run = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run

# The source text is translated through a position-dependent shift per cycle
# before execution.  _encode builds a source program whose translation is
# exactly ``targets`` (the inverse of the module's _translate), so the tests
# can express commands directly.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _encode(targets: str) -> str:
    out: list[str] = []
    k = 0
    for tc in targets:
        for cycle in _CYCLES:
            if tc in cycle:
                out.append(cycle[(cycle.index(tc) - k) % len(cycle)])
                k += 1
                break
    return "".join(out)


class _Coin:
    """A source that answers every draw with one value.

    ``y`` flips a coin to decide whether to skip, and pinning it used to
    mean patching ``secrets.randbelow`` for the whole process.  ``run``
    now forwards a source, so the pin is an argument to the run under
    test rather than a global.
    """

    def __init__(self, value: int) -> None:
        self._value = value

    def randbelow(self, upper: int) -> int:
        """Return the fixed value, checking the bound admits it."""
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        return self._value % upper


def run_program(targets: str, stdin: str = "", coin: int | None = None) -> str:
    io = ScriptedIO(stdin)
    run(_encode(targets), io, rng=None if coin is None else _Coin(coin))
    return io.getvalue()


class TestPainfuck:
    def test_increment_and_print(self) -> None:
        assert run_program("pue") == "\x02"
        assert run_program("ppue") == "\x04"

    def test_decrement(self) -> None:
        assert run_program("sue") == "\xff"  # -1 as a byte

    def test_zero(self) -> None:
        assert run_program("pzue") == "\x00"

    def test_square(self) -> None:
        assert run_program("pkue") == "\x04"  # 2*2
        assert run_program("ppkue") == "\x10"  # 4*4

    def test_half(self) -> None:
        assert run_program("pphue") == "\x02"  # 4 // 2 = 2

    def test_half_truncates_a_negative_toward_zero(self) -> None:
        """Halving rounds toward zero, which only shows below it.

        Python's ``//`` rounds *down*, so a negative cell needs the sign
        handled separately -- and the positive case cannot tell that
        handling from its absence.  Seven subtractions give -7, whose half
        is -3: flooring would give -4, and dropping the sign 3.  An odd
        value is essential, since an even one halves the same either way.
        """
        assert run_program("ssssssshoe") == "-3"
        assert run_program("ssshoe") == "-1"  # -3 -> -1, not -2

    def test_the_pointer_moves_by_two_right_and_one_left(self) -> None:
        """``r`` and ``l`` move by their own distances, from where they are.

        Marking a single cell cannot show either distance -- the write and
        the read land together wherever the pointer went.  This marks three
        cells with different values (2 at cell 0, 4 at cell 2, 6 at cell 4)
        so each position prints something only that position holds: two
        ``r`` moves reach the 6, and two ``l`` moves back from there reach
        the 4 rather than the 6 or the 2.
        """
        assert run_program("prpprpppoe") == "6"
        assert run_program("prpprppplloe") == "4"

    def test_growing_the_tape_fills_with_zeros(self) -> None:
        """``r`` past the end appends empty cells, not marked ones.

        The cells the pointer skips are created by the growth, so their
        value is the growth's -- and every test read the cell it had just
        written.  Cell 3 is only ever created, never written.
        """
        assert run_program("prpprppploe") == "0"
        assert run_program("prroe") == "0"

    def test_copy_neighbor(self) -> None:
        assert run_program("ppwue") == "\x00"  # copy 0 from the right neighbor
        assert run_program("ppwque") == "\x00"  # copy back

    def test_pointer_reset(self) -> None:
        # p at cell 0, r moves right, pp, then d resets and p adds again
        assert run_program("prppdpue") == "\x04"

    def test_read_byte(self) -> None:
        assert run_program("jue", "A\n") == "A"

    def test_read_number(self) -> None:
        assert run_program("jiue", "6\n65\n") == "A"

    def test_read_number_rejects_garbage(self) -> None:
        with pytest.raises(HaltError):
            run_program("ip", "12x\n")

    def test_loop(self) -> None:
        # pp a (cell 2 nonzero, open), s b (0 -> close), u prints 0
        assert run_program("ppas b ue".replace(" ", "")) == "\x00"

    def test_repeat_next(self) -> None:
        # c repeats the next command 7 times; s subtracts 1 each -> -5
        assert run_program("pcsu") == "\xfb"
        # c repeating u prints 7 times
        assert run_program("pcue") == "\x02\x02\x02\x02\x02\x02\x02"

    def test_repeat_previous(self) -> None:
        # t repeats the previous command 3 times
        assert run_program("ptpue") == "\n"

    def test_repeat_previous_with_nothing_before_it(self) -> None:
        """A leading ``t`` has no earlier command, so it repeats nothing.

        The backward scan walks off the start of the program rather than
        finding a command, and execution carries on: the ``u`` still prints
        the untouched cell.  A ``t`` preceded only by more ``t``s is the
        same case, since the scan skips those looking for a real command.
        """
        assert run_program("tue") == "\x00"
        assert run_program("t") == ""

    def test_halt(self) -> None:
        assert run_program("pe") == ""
        assert run_program("p") == ""

    def test_print_number(self) -> None:
        assert run_program("ppoe") == "4"

    def test_copy_from_left_neighbor(self) -> None:
        # q copies the left neighbor into the current cell when ptr > 0
        assert run_program("pprpplque") == "\x04"

    def test_conditional_skip(self) -> None:
        # v skips the next command when the cell is nonzero
        assert run_program("pvpu") == "\x02"

    def test_random_skip(self) -> None:
        """``y`` skips the next command on a coin flip; pin both outcomes.

        The source is handed to ``run`` rather than patched into
        ``secrets``: the coin belongs to this run, and a global patch would
        also silence any other draw the process made.
        """
        assert run_program("pyu", coin=1) == ""
        assert run_program("pyu", coin=0) == "\x02"

    def test_error(self) -> None:
        with pytest.raises(HaltError):
            run_program("b")  # loop close with an empty stack


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine("pp", ScriptedIO())
        assert (machine.ind, list(machine.tape)) == (0, [0])
        machine.step()  # p adds 2
        assert list(machine.tape) == [2]
        machine.step()  # e halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_the_vm_view_reports_the_tape_and_the_loop_stack(self) -> None:
        """``ip``/``memory``/``stack`` are the shared names over painfuck's state.

        ``stack`` is the loop stack here, which is the one that actually
        carries something -- so an open loop is stepped into to see it fill
        and the matching close to see it drain.  The source is encoded
        first, like every other program in this file: the interpreter reads
        the Caesar-shifted text, not these letters.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_encode("pabe"), ScriptedIO())
        assert (machine.ip, machine.memory, machine.stack) == (0, [0], [])
        machine.step()  # p adds 2, so the loop is entered rather than skipped
        assert machine.memory == [2]
        machine.step()  # a pushes the loop's return point
        assert (machine.ip, machine.stack) == (2, [1])
        machine.step()  # b jumps back to it, draining the stack
        assert (machine.ip, machine.stack) == (1, [])

    def test_an_eof_read_still_writes_back_what_the_step_spent(self) -> None:
        """EOF propagates, but the cursor the step already moved is kept.

        The core re-runs the whole step once the shell has a value, so the
        shell holds the state from *before* it.  On EOF there is no value
        and nothing to re-run -- yet the original interpreter had already
        advanced past the read command and spent one repeat before it
        raised, so the shell writes that much back by hand.  Without it a
        caller that catches the EOFError sees a machine still parked on the
        read, and a resumed run would execute it twice.

        Both spellings raise: ``i`` reads a number and ``j`` a byte, and
        each is retried through the same port.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        for prog in ("i", "j"):
            machine = _Machine(_encode(prog), ScriptedIO(""))  # nothing to read
            assert machine.ind == 0
            with pytest.raises(EOFError):
                machine.step()
            assert machine.ind == 1, prog  # advanced past the read, not parked

    def test_a_fault_keeps_what_the_step_already_did(self) -> None:
        """A ``_Halted`` fault writes its effects and state back before raising.

        Same reason as the EOF path above, for the other way a step can end
        early: the core raises out of the middle of a step, carrying the
        state and any effects it had accumulated, and the shell replays
        them so the machine is left where the original interpreter left it
        rather than back at the start of the step.

        Both raise sites are covered -- ``i`` handed something that is not a
        number, and a ``b`` with nothing on the loop stack, which is the one
        that carries a message.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_encode("i"), ScriptedIO("hello\n"))
        with pytest.raises(HaltError):
            machine.step()
        assert machine.ind == 1  # the cursor the faulting step moved is kept

        loose = _Machine(_encode("b"), ScriptedIO(""))
        with pytest.raises(HaltError, match="unmatched 'b'"):
            loose.step()
        assert loose.ind == 1

    def test_growing_the_tape_leaves_an_addressable_pointer_alone(self) -> None:
        """``_grow`` returns the tape untouched when the pointer already fits.

        Every program here walks right one cell at a time, so the tape is
        always grown by exactly the cell being stepped onto and the
        already-addressable case never came up.  Called directly: the guard
        is what keeps a re-visit from re-extending the tape.
        """
        from esolangs.interpreters.tape_based.painfuck import _grow

        tape = (1, 2, 3)
        assert _grow(tape, 0) is tape  # in range, so the same object comes back
        assert _grow(tape, 2) is tape  # the last addressable cell
        assert _grow(tape, 4) == (1, 2, 3, 0, 0)  # past the end, so extended

    def test_skipping_a_loop_steps_over_a_nested_one(self) -> None:
        """A zero cell skips to the loop's own 'b', not to a nested one."""
        # cell 0 is zero, so the outer 'a' skips forward; the inner 'a...b'
        # pair must be consumed as a unit, leaving 'u' to print cell 0.
        assert run_program("aabbue") == "\x00"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.painfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "pp"
    halting_program = "pp"
