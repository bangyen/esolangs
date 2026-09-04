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


class TestRepeatCollapsing:
    """The closed forms `_advance` uses instead of looping `rep` times.

    ``c`` multiplies the repeat count by 7 and ``t`` by 3, so a step can ask
    for millions of iterations of one command; the affine ones are computed
    directly instead.  Each has to agree with the loop it replaces, which is
    what these assert -- against explicit iteration rather than against a
    second interpreter, since ``y`` makes a two-machine differential
    nondeterministic and unable to prove anything.
    """

    @staticmethod
    def _iterate(op: str, tape: tuple[int, ...], ptr: int, rep: int) -> tuple:
        """Apply ``op`` ``rep`` times, one step at a time."""
        from esolangs.interpreters.tape_based.painfuck import _set, _trunc2

        for _ in range(rep):
            if op == "p":
                tape = _set(tape, ptr, tape[ptr] + 2)
            elif op == "s":
                tape = _set(tape, ptr, tape[ptr] - 1)
            elif op == "r":
                ptr += 2
                if ptr >= len(tape):
                    tape = (*tape, *([0] * (ptr + 1 - len(tape))))
            elif op == "l":
                ptr = ptr - 1 if ptr else ptr
            elif op == "z":
                tape = _set(tape, ptr, 0)
            elif op == "w":
                tape = _set(tape, ptr, tape[ptr + 1] if ptr + 1 < len(tape) else 0)
            elif op == "q":
                tape = _set(tape, ptr, tape[ptr - 1]) if ptr else tape
            elif op == "d":
                ptr = 0
            elif op == "h":
                tape = _set(tape, ptr, _trunc2(tape[ptr]))
            elif op == "k":
                tape = _set(tape, ptr, tape[ptr] * tape[ptr])
        return tape, ptr

    @pytest.mark.parametrize("op", "psrlzwqdhk")
    @pytest.mark.parametrize("rep", [1, 2, 3, 5, 13, 40])
    @pytest.mark.parametrize("cells", [[0], [5], [-7], [1], [-1], [3, 9], [-2, 6]])
    def test_a_collapsed_op_equals_repeating_it(
        self, op: str, rep: int, cells: list[int]
    ) -> None:
        from esolangs.interpreters.tape_based.painfuck import _advance

        for ptr in range(len(cells)):
            tape = tuple(cells)
            if op == "k" and abs(tape[ptr]) > 1 and rep > 5:
                continue  # squaring explodes by design; nothing to collapse
            state = (tape, (), ptr, 0, rep)
            (got_tape, _loop, got_ptr, _ind, _r), _fx = _advance(state, op, 1, (), ())
            assert (got_tape, got_ptr) == self._iterate(op, tape, ptr, rep), (
                f"{op!r} at ptr={ptr} rep={rep}"
            )

    def test_a_repeated_loop_command_decides_once(self) -> None:
        """``a``/``b`` are jumps, so repeating one changes nothing.

        The wiki defines them as "go to the matching b if the value is zero"
        and "go back to the matching a if it is not" -- decisions, not
        accumulations, and nothing between two iterations of a repeat
        changes the cell they read.  The loop stack is how this interpreter
        finds the matching bracket, not part of the language, so a repeated
        ``a`` must not push once per iteration and leave a loop that needs
        as many ``b``s to close.
        """
        from esolangs.interpreters.tape_based.painfuck import _advance

        entered = None
        for rep in (1, 2, 7, 1000):
            state = ((5,), (), 0, 0, rep)  # nonzero cell: the loop is entered
            (_tape, loop, _ptr, ind, _r), _fx = _advance(state, "ab", 2, (), ())
            assert len(loop) == 1, f"rep={rep} pushed {len(loop)} entries"
            entered = (loop, ind) if entered is None else entered
            assert (loop, ind) == entered, f"rep={rep} differed from rep=1"

        popped = None
        for rep in (1, 2, 7, 1000):
            state = ((5,), (7, 8, 9), 0, 3, rep)
            (_tape, loop, _ptr, ind, _r), _fx = _advance(state, "aaab", 4, (), ())
            popped = (loop, ind) if popped is None else popped
            assert (loop, ind) == popped, f"b at rep={rep} differed from rep=1"

    @pytest.mark.parametrize(
        ("prog", "runs"),
        [
            ("cp", 7),
            ("ccp", 49),
            ("ctp", 21),
            ("cctp", 147),
            ("ctttp", 189),
            ("ccttp", 441),
        ],
    )
    def test_a_c_run_absorbs_the_t_run_after_it(self, prog: str, runs: int) -> None:
        """``c...t...`` is one count, ``7**c * 3**t``, on the command after.

        ``t`` normally repeats the *preceding* command by walking backward,
        but the command preceding a ``t`` that follows a ``c`` run is that
        ``c`` -- which would be executed a second time, multiplying its
        seven in twice.  Reading the ``t`` run forward as part of the same
        count is what makes ``ct`` mean 21 rather than 7 or 147.
        """
        from esolangs.interpreters.tape_based.painfuck import _advance

        state = ((0,), (), 0, 0, 1)
        (tape, _loop, _ptr, _ind, _r), _fx = _advance(state, prog, len(prog), (), ())
        assert tape[0] == 2 * runs, f"{prog!r} ran p {tape[0] // 2}x, wanted {runs}"

    @pytest.mark.parametrize(
        ("prog", "runs"),
        [("pt", 1 + 3), ("ptt", 1 + 9), ("pttt", 1 + 27)],
    )
    def test_a_t_run_repeats_three_to_its_length_times(
        self, prog: str, runs: int
    ) -> None:
        """``t...`` is one count of ``3 ** len``, as ``c...`` is of ``7 **``.

        The cursor has to clear the whole run: leaving it inside made each
        later ``t`` a step of its own that walked back over the ones before
        it, so ``ptt`` ran its ``p`` three *then* nine times -- the
        geometric sum 1+3+9 rather than 1+9.  The text generator solved for
        that sum, and so only produced correct programs against it.
        """
        from esolangs.interpreters.tape_based.painfuck import _advance

        tape: tuple[int, ...] = (0,)
        loop: tuple[int, ...] = ()
        ptr = ind = 0
        while ind < len(prog):
            state = (tape, loop, ptr, ind, 1)
            (tape, loop, ptr, ind, _r), _fx = _advance(state, prog, len(prog), (), ())
        assert tape[0] == 2 * runs, f"{prog!r} ran p {tape[0] // 2}x, wanted {runs}"

    @pytest.mark.parametrize(
        ("prog", "trace"),
        [("pt", [2, 8]), ("ptt", [2, 20]), ("pst", [2, 1, -2])],
    )
    def test_a_bare_t_still_repeats_the_previous_command(
        self, prog: str, trace: list[int]
    ) -> None:
        """The forward read is only for a ``t`` reached from a ``c`` run.

        A ``t`` with an ordinary command behind it keeps walking backward,
        which is the operator's whole meaning; ``pt`` is ``p`` then three
        more ``p``.
        """
        from esolangs.interpreters.tape_based.painfuck import _advance

        tape: tuple[int, ...] = (0,)
        loop: tuple[int, ...] = ()
        ptr = ind = 0
        seen = []
        while ind < len(prog):
            state = (tape, loop, ptr, ind, 1)
            (tape, loop, ptr, ind, _r), _fx = _advance(state, prog, len(prog), (), ())
            seen.append(tape[0])
        assert seen == trace

    def test_halving_truncates_toward_zero_not_down(self) -> None:
        """The one collapse a plain ``//`` would get wrong.

        ``_trunc2`` truncates toward zero, so ``-7`` halved twice is ``-1``;
        flooring would give ``-2``.  The shift has to match the loop for
        every negative that does not divide exactly.
        """
        from esolangs.interpreters.tape_based.painfuck import _advance

        state = ((-7,), (), 0, 0, 2)
        (tape, _loop, _ptr, _ind, _r), _fx = _advance(state, "h", 1, (), ())
        assert tape == (-1,), "halving a negative must truncate toward zero"
        assert -7 // 4 == -2, "the flooring answer this must not produce"


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
