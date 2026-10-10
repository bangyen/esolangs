"""Unit tests for the Painfuck interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from esolangs.interpreters.tape_based.painfuck import _Machine as Painfuck
from esolangs.vm import (
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_cycle,
)
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.raises import assert_halts_with_hint

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
    """A source that answers every draw with one value."""

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


_OUTPUT = {
    # pp a (cell 2 nonzero, open), s b (0 -> close), u prints 0
    "loop": ("ppas b ue".replace(" ", ""), "\x00"),
    # t repeats the previous command 3 times
    "repeat_previous": ("ptpue", "\n"),
    "print_number": ("ppoe", "4"),
    # q copies the left neighbor into the current cell when ptr > 0
    "copy_from_left_neighbor": ("pprpplque", "\x04"),
    "decrement": ("sue", "\xff"),
    "half": ("pphue", "\x02"),
    # p at cell 0, r moves right, pp, then d resets and p adds again
    "pointer_reset": ("prppdpue", "\x04"),
    "zero": ("pzue", "\x00"),
    # A zero cell skips to the loop's own 'b', not to a nested one.
    # cell 0 is zero, so the outer 'a' skips forward; the inner 'a...b'
    # pair must be consumed as a unit, leaving 'u' to print cell 0.
    "skipping_a_loop_steps_over_a_nested_one": ("aabbue", "\x00"),
    # The grown cell and the start cell are distinct and both kept.
    # start 2, grow left and add 6; r lands one past the start, then
    # two l print the start cell and the grown one
    "left_of_zero_and_back_keeps_both_cells": ("plppprloloe", "26"),
    # The cell left of the leftmost exists and is zero, as ``w``'s is.
    "copy_from_left_at_the_leftmost_cell_copies_a_zero": ("ppqoe", "0"),
}


# (targets, stdin, coin, expected); the ``_OUTPUT`` entries run without input.
_CASES = [
    *[(targets, "", None, expected) for targets, expected in _OUTPUT.values()],
    ("pue", "", None, "\x02"),
    ("ppue", "", None, "\x04"),
    ("ssssssshoe", "", None, "-4"),  # half_rounds_a_negative_down
    ("ssshoe", "", None, "-2"),
    ("prpprpppoe", "", None, "6"),  # right_moves_two
    ("prpprppplloe", "", None, "4"),  # left_moves_one
    ("prpprppploe", "", None, "0"),  # grown_tape_is_zero
    ("prroe", "", None, "0"),
    ("jue", "A\n", None, "A"),  # read_byte
    ("jiue", "6\n65\n", None, "A"),  # read_number
    ("pcsu", "", None, "\xfb"),  # repeat_next
    ("pcue", "", None, "\x02\x02\x02\x02\x02\x02\x02"),
    ("tue", "", None, "\x00"),  # leading_t_repeats_nothing
    ("t", "", None, ""),
    ("pe", "", None, ""),  # halt
    ("p", "", None, ""),
    ("vsu", "", None, "\xff"),  # conditional_skip
    ("pvsu", "", None, "\x02"),
    ("pvuu", "", None, "\x02"),
    ("cju", "abcdefgh", None, "g"),  # repeated_read_reads_each_time
    ("jtu", "abcde", None, "d"),
    ("pyu", "", 1, ""),  # random_skip
    ("pyu", "", 0, "\x02"),
    ("cypoe", "", 0, "14"),  # repeated_skip_flips_per_repeat
    ("cypoe", "", 1, "0"),
    ("cpoe", "", 0, "14"),
    ("ypoe", "", 0, "2"),
    ("ypoe", "", 1, "0"),
    ("ppwue", "", None, "\x00"),  # copy_neighbor
    ("ppwque", "", None, "\x00"),
    ("ploe", "", None, "0"),  # left_of_cell_zero_is_fresh
    ("plllrrloe", "", None, "2"),
    ("pcllrrrroe", "", None, "2"),
    ("plldoe", "", None, "2"),  # reset_returns_to_start
    ("lpdoe", "", None, "0"),
    ("pkue", "", None, "\x04"),  # square
    ("ppkue", "", None, "\x10"),
    ("psckue", "", None, "\x01"),  # repeated_square_fixes_one
    ("ckue", "", None, "\x00"),
]


@pytest.mark.parametrize(("targets", "stdin", "coin", "expected"), _CASES)
def test_output(targets: str, stdin: str, coin: int | None, expected: str) -> None:
    assert run_program(targets, stdin, coin) == expected


def test_read_number_rejects_garbage() -> None:
    with pytest.raises(HaltError):
        run_program("ip", "12x\n")


def test_unmatched_loop_close_is_an_error() -> None:
    with pytest.raises(HaltError):
        run_program("b")


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        machine = Painfuck("pp", ScriptedIO())
        assert (machine.ind, list(machine.tape)) == (0, [0])
        machine.step()  # p adds 2
        assert list(machine.tape) == [2]
        machine.step()  # e halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_the_vm_view_reports_the_tape_and_the_loop_stack(self) -> None:
        """``ind``/``memory``/``stack`` are what the VM shows over painfuck's state."""
        machine = Painfuck(_encode("pabe"), ScriptedIO())
        assert (machine.ind, machine.memory, machine.stack) == (0, [0], [])
        machine.step()  # p adds 2, so the loop is entered rather than skipped
        assert machine.memory == [2]
        machine.step()  # a pushes the loop's return point
        assert (machine.ind, machine.stack) == (2, [1])
        machine.step()  # b jumps back to it, draining the stack
        assert (machine.ind, machine.stack) == (1, [])

    def test_an_eof_read_still_writes_back_what_the_step_spent(self) -> None:
        """EOF propagates, but the cursor the step already moved is kept."""
        for prog in ("i", "j"):
            machine = Painfuck(_encode(prog), ScriptedIO(""))  # nothing to read
            assert machine.ind == 0
            with pytest.raises(EOFError):
                machine.step()
            assert machine.ind == 1, prog  # advanced past the read, not parked

    def test_an_eof_keeps_the_repeated_reads_already_done(self) -> None:
        """Pins EOF mid-repeat: ``ci`` reads 5, then EOF; the 5 survives."""
        machine = Painfuck(_encode("ci"), ScriptedIO("5\n"))
        with pytest.raises(EOFError):  # one step: c binds to the i
            machine.step()
        assert (machine.tape, machine.ind, machine.rep) == ((5,), 2, 5)

    def test_a_fault_keeps_what_the_step_already_did(self) -> None:
        """A ``_Halted`` fault writes its effects and state back before raising."""
        machine = Painfuck(_encode("i"), ScriptedIO("hello\n"))
        with pytest.raises(HaltError):
            machine.step()
        assert machine.ind == 1  # the cursor the faulting step moved is kept

        loose = Painfuck(_encode("b"), ScriptedIO(""))
        with pytest.raises(HaltError, match="unmatched 'b'"):
            loose.step()
        assert loose.ind == 1

    def test_growing_the_tape_leaves_an_addressable_pointer_alone(self) -> None:
        """``_grow`` returns the tape untouched when the pointer already fits."""
        from esolangs.interpreters.tape_based.painfuck import _grow

        tape = (1, 2, 3)
        assert _grow(tape, 0) is tape  # in range, so the same object comes back
        assert _grow(tape, 2) is tape  # the last addressable cell
        assert _grow(tape, 4) == (1, 2, 3, 0, 0)  # past the end, so extended


class TestRepeatCollapsing:
    """The closed forms `_advance` uses instead of looping `rep` times."""

    @staticmethod
    def _iterate(
        op: str, tape: tuple[int, ...], ptr: int, origin: int, rep: int
    ) -> tuple:
        """Apply ``op`` ``rep`` times, one step at a time."""
        from esolangs.interpreters.tape_based.painfuck import _half, _set

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
                if ptr:
                    ptr -= 1
                else:
                    tape, origin = (0, *tape), origin + 1
            elif op == "z":
                tape = _set(tape, ptr, 0)
            elif op == "w":
                tape = _set(tape, ptr, tape[ptr + 1] if ptr + 1 < len(tape) else 0)
            elif op == "q":
                tape = _set(tape, ptr, tape[ptr - 1] if ptr else 0)
            elif op == "d":
                ptr = origin
            elif op == "h":
                tape = _set(tape, ptr, _half(tape[ptr]))
            elif op == "k":
                tape = _set(tape, ptr, tape[ptr] * tape[ptr])
        return tape, ptr, origin

    @pytest.mark.parametrize("op", "psrlzwqdhk")
    @pytest.mark.parametrize("rep", [13])
    # ``[2]`` is the cell just above the squaring fast path's bound.  The
    # bound is ``-1 <= x <= 1``, and every other value here is either well
    # inside it or well outside: widening it by one admits exactly 2 and
    # nothing else (-2 still fails the *lower* bound, so ``[-2, 6]`` cannot
    # see it), which collapses 2 to 4 where repeating squares it to 16.
    @pytest.mark.parametrize("cells", [[2], [-2, 6]])
    def test_a_collapsed_op_equals_repeating_it(
        self, op: str, rep: int, cells: list[int]
    ) -> None:
        from esolangs.interpreters.tape_based.painfuck import _advance

        for ptr in range(len(cells)):
            tape = tuple(cells)
            if op == "k" and abs(tape[ptr]) > 1 and rep > 5:
                continue  # squaring explodes by design; nothing to collapse
            origin = len(cells) - 1  # ``d``'s target, off the pointer
            state = (tape, (), ptr, 0, rep, origin)
            (got_tape, _loop, got_ptr, _ind, _r, got_origin), _fx = _advance(
                state, op, 1, (), ()
            )
            got = (got_tape, got_ptr, got_origin)
            assert got == self._iterate(op, tape, ptr, origin, rep), (
                f"{op!r} at ptr={ptr} rep={rep}"
            )

    def test_a_repeated_loop_command_decides_once(self) -> None:
        """``a``/``b`` are jumps, so repeating one changes nothing."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        entered = None
        for rep in (1, 2, 7, 1000):
            state = ((5,), (), 0, 0, rep, 0)  # nonzero cell: the loop is entered
            (_tape, loop, _ptr, ind, _r, _o), _fx = _advance(state, "ab", 2, (), ())
            assert len(loop) == 1, f"rep={rep} pushed {len(loop)} entries"
            entered = (loop, ind) if entered is None else entered
            assert (loop, ind) == entered, f"rep={rep} differed from rep=1"

        popped = None
        for rep in (1, 2, 7, 1000):
            state = ((5,), (7, 8, 9), 0, 3, rep, 0)
            (_tape, loop, _ptr, ind, _r, _o), _fx = _advance(state, "aaab", 4, (), ())
            popped = (loop, ind) if popped is None else popped
            assert (loop, ind) == popped, f"b at rep={rep} differed from rep=1"

    @pytest.mark.parametrize(
        ("prog", "runs"),
        [
            ("cp", 7),
            # A t run after a c run repeats the *c*; each successive t adds
            # the next power of three, as in the author's ptto -> 26
            # (User talk:Lemonz, 8 May 2022).
            ("ctp", 7**4),
            ("ccttp", 49 ** (1 + 3 + 9)),
        ],
    )
    def test_a_c_run_absorbs_the_t_run_after_it(self, prog: str, runs: int) -> None:
        """A ``t`` run after a ``c`` run repeats *the ``c``*."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        state = ((0,), (), 0, 0, 1, 0)
        (tape, _loop, _ptr, _ind, _r, _o), _fx = _advance(
            state, prog, len(prog), (), ()
        )
        assert tape[0] == 2 * runs, f"{prog!r} ran p {tape[0] // 2}x, wanted {runs}"

    @pytest.mark.parametrize(
        ("prog", "runs"),
        # User talk:Lemonz, 8 May 2022: ptto prints 26 = 2 * (1 + 3 + 9).
        [("ptt", 1 + 3 + 9)],
    )
    def test_a_t_run_adds_successive_powers_of_three(
        self, prog: str, runs: int
    ) -> None:
        """Each ``t`` in a run repeats the previous repeat three times."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        tape: tuple[int, ...] = (0,)
        loop: tuple[int, ...] = ()
        ptr = ind = 0
        while ind < len(prog):
            state = (tape, loop, ptr, ind, 1, 0)
            (tape, loop, ptr, ind, _r, _o), _fx = _advance(
                state, prog, len(prog), (), ()
            )
        assert tape[0] == 2 * runs, f"{prog!r} ran p {tape[0] // 2}x, wanted {runs}"

    @pytest.mark.parametrize(
        ("prog", "trace"),
        [("ptt", [2, 8, 26]), ("pst", [2, 1, -2])],
    )
    def test_a_bare_t_still_repeats_the_previous_command(
        self, prog: str, trace: list[int]
    ) -> None:
        """The forward read is only for a ``t`` reached from a ``c`` run."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        tape: tuple[int, ...] = (0,)
        loop: tuple[int, ...] = ()
        ptr = ind = 0
        seen = []
        while ind < len(prog):
            state = (tape, loop, ptr, ind, 1, 0)
            (tape, loop, ptr, ind, _r, _o), _fx = _advance(
                state, prog, len(prog), (), ()
            )
            seen.append(tape[0])
        assert seen == trace

    def test_halving_rounds_down_not_toward_zero(self) -> None:
        """The one collapse a truncating shift would get wrong."""
        from esolangs.interpreters.tape_based.painfuck import _advance

        state = ((-7,), (), 0, 0, 2, 0)
        (tape, _loop, _ptr, _ind, _r, _o), _fx = _advance(state, "h", 1, (), ())
        assert tape == (-2,), "halving a negative must round down"


def _machine(code: object) -> object:
    return Painfuck(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "pp"
    halting_program = "pp"
    looping_program = _encode("pab")


@pytest.mark.medium
def test_hints_for_bad_programs_and_input():
    assert_halts_with_hint("Painfuck", "i", HaltError.DEFAULT, "decimal integer", "x")


def test_painfuck_all_coin_outcomes_can_be_proved_to_loop() -> None:
    """Either ``y`` outcome reaches a loop close and returns to ``a``."""
    code = _encode("paybb")
    machine = Painfuck(code, ScriptedIO())
    assert run_until_halt_or_all_branches_cycle(machine) is False
    # A later draw could escape; snapshot proofs refuse random machines.
    for coin in (0, 1):
        draws = FirstDraw(coin, rest=coin)
        with pytest.raises(TypeError, match="random machines"):
            run_until_halt_or_cycle(Painfuck(code, ScriptedIO(), draws), limit=64)


def test_painfuck_one_halting_coin_refutes_an_all_branches_hang() -> None:
    code = _encode("payb")
    machine = Painfuck(code, ScriptedIO())
    assert run_until_halt_or_all_branches_cycle(machine) is True
    halting = Painfuck(code, ScriptedIO(), FirstDraw(1))
    assert run_until_halt(halting, limit=1000) is True
    looping = Painfuck(code, ScriptedIO(), FirstDraw(0, rest=0))
    with pytest.raises(TypeError, match="random machines"):
        run_until_halt_or_cycle(looping, limit=64)


def test_painfuck_a_malformed_loop_is_a_terminal_branch() -> None:
    """An unmatched ``b`` ends its branch instead of escaping the search."""
    machine = Painfuck(_encode("b"), ScriptedIO())
    start = machine.branching_snapshot()
    assert machine.branching_halted(start) is False

    (ended,) = machine.branching_successors(start, 100) or ()
    assert machine.branching_halted(ended) is True
    assert ended[3] == machine.n  # cursor parked past the program


def test_painfuck_later_coin_can_escape_repeated_visible_state() -> None:
    """Pins the draw count in the snapshot: tape/cursor repeat, yet the
    fifth coin halts ``payb``, so a single path must not report a cycle."""

    class DelayedEscape:
        def __init__(self) -> None:
            self.draws = 0

        def randbelow(self, upper: int) -> int:
            assert upper == 2
            self.draws += 1
            return int(self.draws == 5)

    coins = DelayedEscape()
    machine = Painfuck(_encode("payb"), ScriptedIO(), coins)
    assert run_until_halt(machine, limit=64) is True
    assert coins.draws == 5


def test_branching_search_leaves_input_and_wide_coin_paths_undecided() -> None:
    # The direct target 'j' reads; sibling paths must not share a cursor.
    with pytest.raises(TimeoutError, match="needs input"):
        run_until_halt_or_all_branches_cycle(Painfuck(_encode("j"), ScriptedIO("A\n")))
    # c repeats y 49 times: the frontier is limited at the transition,
    # before its 2**49 outcomes are materialized.
    with pytest.raises(TimeoutError, match="coin outcomes"):
        run_until_halt_or_all_branches_cycle(
            Painfuck(_encode("ccy"), ScriptedIO()), limit=4
        )
