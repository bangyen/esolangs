r"""Unit tests for the Painfuck interpreter."""

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

# The source text is translated.
# before execution.
# exactly ``targets`` (the.
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
    r"""A source that answers every draw with one value."""

    def __init__(self, value: int) -> None:
        self._value = value

    def randbelow(self, upper: int) -> int:
        r"""Return the fixed value, checking the bound admits it."""
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
        assert run_program("sue") == "\xff"  # -1 as a byte.

    def test_zero(self) -> None:
        assert run_program("pzue") == "\x00"

    def test_square(self) -> None:
        assert run_program("pkue") == "\x04"  # 2*2.
        assert run_program("ppkue") == "\x10"  # 4*4.

    def test_half(self) -> None:
        assert run_program("pphue") == "\x02"  # 4 // 2 = 2.

    def test_half_truncates_a_negative_toward_zero(self) -> None:
        r"""Halving rounds toward zero, which only shows below it."""
        assert run_program("ssssssshoe") == "-3"
        assert run_program("ssshoe") == "-1"  # -3 -> -1, not -2.

    def test_the_pointer_moves_by_two_right_and_one_left(self) -> None:
        r"""``r`` and ``l`` move by their own distances, from where they are."""
        assert run_program("prpprpppoe") == "6"
        assert run_program("prpprppplloe") == "4"

    def test_growing_the_tape_fills_with_zeros(self) -> None:
        r"""``r`` past the end appends empty cells, not marked ones."""
        assert run_program("prpprppploe") == "0"
        assert run_program("prroe") == "0"

    def test_copy_neighbor(self) -> None:
        assert run_program("ppwue") == "\x00"  # copy 0 from the right.
        assert run_program("ppwque") == "\x00"  # copy back.

    def test_pointer_reset(self) -> None:
        # p at cell 0, r moves right,.
        assert run_program("prppdpue") == "\x04"

    def test_read_byte(self) -> None:
        assert run_program("jue", "A\n") == "A"

    def test_read_number(self) -> None:
        assert run_program("jiue", "6\n65\n") == "A"

    def test_read_number_rejects_garbage(self) -> None:
        with pytest.raises(HaltError):
            run_program("ip", "12x\n")

    def test_loop(self) -> None:
        # pp a (cell 2 nonzero, open),.
        assert run_program("ppas b ue".replace(" ", "")) == "\x00"

    def test_repeat_next(self) -> None:
        # c repeats the next command 7.
        assert run_program("pcsu") == "\xfb"
        # c repeating u prints 7 times.
        assert run_program("pcue") == "\x02\x02\x02\x02\x02\x02\x02"

    def test_repeat_previous(self) -> None:
        # t repeats the previous.
        assert run_program("ptpue") == "\n"

    def test_repeat_previous_with_nothing_before_it(self) -> None:
        r"""A leading ``t`` has no earlier command, so it repeats nothing."""
        assert run_program("tue") == "\x00"
        assert run_program("t") == ""

    def test_halt(self) -> None:
        assert run_program("pe") == ""
        assert run_program("p") == ""

    def test_print_number(self) -> None:
        assert run_program("ppoe") == "4"

    def test_copy_from_left_neighbor(self) -> None:
        # q copies the left neighbor.
        assert run_program("pprpplque") == "\x04"

    def test_conditional_skip(self) -> None:
        # v skips the next command when.
        assert run_program("pvpu") == "\x02"

    def test_random_skip(self) -> None:
        r"""``y`` skips the next command on a coin flip; pin both outcomes."""
        assert run_program("pyu", coin=1) == ""
        assert run_program("pyu", coin=0) == "\x02"

    def test_repeated_skip_decides_each_repeat_separately(self) -> None:
        r"""A repeated ``y`` flips once per repeat, not once for the run."""
        assert run_program("cypoe", coin=0) == "14"  # every repeat survives.
        assert run_program("cypoe", coin=1) == "0"  # every repeat dropped.
        assert run_program("cpoe", coin=0) == "14"  # a y-free run matches.
        # Unrepeated, every reading.
        assert run_program("ypoe", coin=0) == "2"
        assert run_program("ypoe", coin=1) == "0"

    def test_error(self) -> None:
        with pytest.raises(HaltError):
            run_program("b")  # loop close with an empty.


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine("pp", ScriptedIO())
        assert (machine.ind, list(machine.tape)) == (0, [0])
        machine.step()  # p adds 2.
        assert list(machine.tape) == [2]
        machine.step()  # e halts.
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 2

    def test_the_vm_view_reports_the_tape_and_the_loop_stack(self) -> None:
        r"""``ip``/``memory``/``stack`` are the shared names over painfuck's."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_encode("pabe"), ScriptedIO())
        assert (machine.ip, machine.memory, machine.stack) == (0, [0], [])
        machine.step()  # p adds 2, so the loop is.
        assert machine.memory == [2]
        machine.step()  # a pushes the loop's return.
        assert (machine.ip, machine.stack) == (2, [1])
        machine.step()  # b jumps back to it, draining.
        assert (machine.ip, machine.stack) == (1, [])

    def test_an_eof_read_still_writes_back_what_the_step_spent(self) -> None:
        r"""EOF propagates, but the cursor the step already moved is kept."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        for prog in ("i", "j"):
            machine = _Machine(_encode(prog), ScriptedIO(""))  # nothing to read.
            assert machine.ind == 0
            with pytest.raises(EOFError):
                machine.step()
            assert machine.ind == 1, prog  # advanced past the read, not.

    def test_a_fault_keeps_what_the_step_already_did(self) -> None:
        r"""A ``_Halted`` fault writes its effects and state back before."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_encode("i"), ScriptedIO("hello\n"))
        with pytest.raises(HaltError):
            machine.step()
        assert machine.ind == 1  # the cursor the faulting step.

        loose = _Machine(_encode("b"), ScriptedIO(""))
        with pytest.raises(HaltError, match="unmatched 'b'"):
            loose.step()
        assert loose.ind == 1

    def test_growing_the_tape_leaves_an_addressable_pointer_alone(self) -> None:
        r"""``_grow`` returns the tape untouched when the pointer already fits."""
        from esolangs.interpreters.tape_based.painfuck import _grow

        tape = (1, 2, 3)
        assert _grow(tape, 0) is tape  # in range, so the same object.
        assert _grow(tape, 2) is tape  # the last addressable cell.
        assert _grow(tape, 4) == (1, 2, 3, 0, 0)  # past the end, so extended.

    def test_skipping_a_loop_steps_over_a_nested_one(self) -> None:
        r"""A zero cell skips to the loop's own 'b', not to a nested one."""
        # cell 0 is zero, so the outer.
        # pair must be consumed as a.
        assert run_program("aabbue") == "\x00"


class TestRepeatCollapsing:
    r"""The closed forms `_advance` uses instead of looping `rep` times."""

    @staticmethod
    def _iterate(op: str, tape: tuple[int, ...], ptr: int, rep: int) -> tuple:
        r"""Apply ``op`` ``rep`` times, one step at a time."""
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
    # ``[2]`` is the cell just.
    # bound is ``-1 <= x <= 1``,.
    # inside it or well outside:.
    # nothing else (-2 still fails.
    # see it), which collapses 2 to.
    @pytest.mark.parametrize("cells", [[0], [5], [-7], [1], [-1], [2], [3, 9], [-2, 6]])
    def test_a_collapsed_op_equals_repeating_it(
        self, op: str, rep: int, cells: list[int]
    ) -> None:
        from esolangs.interpreters.tape_based.painfuck import _advance

        for ptr in range(len(cells)):
            tape = tuple(cells)
            if op == "k" and abs(tape[ptr]) > 1 and rep > 5:
                continue  # squaring explodes by design;.
            state = (tape, (), ptr, 0, rep)
            (got_tape, _loop, got_ptr, _ind, _r), _fx = _advance(state, op, 1, (), ())
            assert (got_tape, got_ptr) == self._iterate(op, tape, ptr, rep), (
                f"{op!r} at ptr={ptr} rep={rep}"
            )

    def test_a_repeated_loop_command_decides_once(self) -> None:
        r"""``a``/``b`` are jumps, so repeating one changes nothing."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        entered = None
        for rep in (1, 2, 7, 1000):
            state = ((5,), (), 0, 0, rep)  # nonzero cell: the loop is.
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
            ("cccp", 343),
            # A t run after a c run repeats.
            # once, so it adds 3**len more.
            ("ctp", 7**4),
            ("cctp", 49**4),
            ("ctttp", 7 ** (1 + 27)),
            ("ccttp", 49 ** (1 + 9)),
        ],
    )
    def test_a_c_run_absorbs_the_t_run_after_it(self, prog: str, runs: int) -> None:
        r"""A ``t`` run after a ``c`` run repeats *the ``c``*."""
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
        r"""``t...`` is one count of ``3 ** len``, as ``c...`` is of ``7 **``."""
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
        r"""The forward read is only for a ``t`` reached from a ``c`` run."""
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
        r"""The one collapse a plain ``//`` would get wrong."""
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
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "pp"
    halting_program = "pp"
