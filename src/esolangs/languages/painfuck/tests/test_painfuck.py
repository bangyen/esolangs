"""Unit tests for the Painfuck interpreter."""

import importlib
from itertools import product

import pytest

from esolangs import ExecutionLimits, ExecutionResult, InputExhaustedError, Language
from esolangs.debugger import Debugger, make_debugger
from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.languages.painfuck._transition import _advance as _advance_sparse
from esolangs.languages.painfuck._transition import _get, _put
from esolangs.languages.painfuck.interpreter import _Machine as Painfuck
from esolangs.languages.painfuck.interpreter import prepare_machine
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import FirstDraw
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
from tests.support.factories import reject_rng_options, rng_factory
from tests.support.raises import assert_halts_with_hint
from tests.support.vm_support import assert_random_steps_reproduce

_interpreter = importlib.import_module("esolangs.languages.painfuck.interpreter")
run = _interpreter.run


def _set(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _advance(state, prog, n, reads, coins):
    """``_advance`` over the dense ``(tape, loop, ptr, ind, rep, origin)``."""
    tape, loop, ptr, ind, rep, origin = state
    kept = [(i - origin, v) for i, v in enumerate(tape) if v]
    cells = (tuple(i for i, _ in kept), tuple(v for _, v in kept))
    span = (-origin, len(tape) - 1 - origin)
    sparse = (cells, loop, ptr - origin, ind, rep, span)
    (cells, loop, pos, ind, rep, span), effects = _advance_sparse(
        sparse, prog, n, reads, coins
    )
    dense = _interpreter._dense(cells, span)
    return (dense, loop, pos - span[0], ind, rep, -span[0]), effects


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
    ("ssssssshoe", "", None, "-4"),  # half_rounds_a_negative_down
    ("prpprpppoe", "", None, "6"),  # right_moves_two
    ("prpprppplloe", "", None, "4"),  # left_moves_one
    ("prpprppploe", "", None, "0"),  # grown_tape_is_zero
    ("jue", "A\n", None, "A"),  # read_byte
    ("jiue", "6\n65\n", None, "A"),  # read_number
    ("pcsu", "", None, "\xfb"),  # repeat_next
    ("pcue", "", None, "\x02\x02\x02\x02\x02\x02\x02"),
    ("tue", "", None, "\x00"),  # leading_t_repeats_nothing
    ("pe", "", None, ""),  # halt
    ("p", "", None, ""),
    ("vsu", "", None, "\xff"),  # conditional_skip
    ("pvsu", "", None, "\x02"),
    ("cju", "abcdefgh", None, "g"),  # repeated_read_reads_each_time
    ("jtu", "abcde", None, "d"),
    ("pyu", "", 1, ""),  # random_skip
    ("pyu", "", 0, "\x02"),
    ("cypoe", "", 0, "14"),  # repeated_skip_flips_per_repeat
    ("cypoe", "", 1, "0"),
    ("cpoe", "", 0, "14"),
    ("ppwue", "", None, "\x00"),  # copy_neighbor
    ("ppwque", "", None, "\x00"),
    ("ploe", "", None, "0"),  # left_of_cell_zero_is_fresh
    ("plllrrloe", "", None, "2"),
    ("pcllrrrroe", "", None, "2"),
    ("plldoe", "", None, "2"),  # reset_returns_to_start
    ("lpdoe", "", None, "0"),
    ("pkue", "", None, "\x04"),  # square
    ("psckue", "", None, "\x01"),  # repeated_square_fixes_one
]


@pytest.mark.parametrize(("targets", "stdin", "coin", "expected"), _CASES)
def test_output(targets: str, stdin: str, coin: int | None, expected: str) -> None:
    assert run_program(targets, stdin, coin) == expected


def test_read_number_rejects_garbage() -> None:
    with pytest.raises(HaltError):
        run_program("ip", "12x\n")

    api = Language("Painfuck")
    limits = ExecutionLimits(max_steps=5)
    for commands, stdin, position, reads in (
        ("poioe", "oops 7", 4, 1),
        ("poboe", "", 0, 0),
        ("poi", "oops 7", 4, 1),
    ):
        plan = api.prepare(_encode(commands))
        expected = ExecutionResult("2", position, reads, 0, steps=2)
        for isolated in (False, True):
            outcome = plan.execute(stdin=stdin, limits=limits, isolated=isolated)
            assert type(outcome.error) is HaltError
            assert outcome.observation == expected
        machine = plan.make_debugger(stdin=stdin)
        with pytest.raises(HaltError) as before:
            machine.run(limits=limits)
        assert before.value.observation == expected
        saved = machine.snapshot()
        for invoke in (
            machine.step,
            lambda live=machine: live.run(limits=limits),
            lambda live=machine: run_until_halt_or_cycle(live, limit=5),
            lambda live=machine: run_until_halt_or_all_branches_cycle(live, limit=5),
        ):
            with pytest.raises(HaltError) as after:
                invoke()
            assert after.value is not before.value
            assert after.value.args == before.value.args
            assert str(after.value) == str(before.value)
            assert before.value.observation == machine.observation == expected
            assert machine.ip == 3
            assert machine.snapshot() == saved

    valid = api.run(_encode("poioe"), stdin="7", limits=limits)
    assert (valid.output, valid.input_reads, valid.steps) == ("27", 1, 5)


def _check_repeated_port_retry(target, stdin, *, refusal, monkeypatch) -> None:
    from esolangs.languages.painfuck import interpreter

    api = Language("Painfuck")
    source = _encode(target)
    numeric = target == "cio"
    operand = "input_token" if numeric else "input_char"
    read = getattr(ScriptedIO, operand)
    draws = []
    reads = []
    failed = False

    def draw_zero(_rng, upper):
        draws.append(upper)
        if failed and refusal == "draw" and len(draws) == 2:
            raise HaltError("temporary port refusal")
        return 0

    def read_operand(io, *args):
        reads.append(io.position())
        if failed and refusal == "read" and len(reads) == 2:
            raise HaltError("temporary port refusal")
        return read(io, *args)

    limits = ExecutionLimits(max_steps=4)
    with monkeypatch.context() as port:
        port.setattr(interpreter, "draw", draw_zero)
        port.setattr(ScriptedIO, operand, read_operand)
        expected = api.run(source, stdin=stdin, limits=limits, seed=0)
        assert (expected.output, expected.input_reads, expected.steps) == (
            "7" if numeric else "g",
            7,
            2,
        )
        total_draws = 7 if target == "cyju" else 0
        assert len(reads) == 7
        assert len(draws) == total_draws
        draws.clear()
        reads.clear()
        failed = True

        debugger = api.make_debugger(source, stdin=stdin, seed=0)
        with pytest.raises(HaltError, match="temporary port refusal") as caught:
            debugger.run(limits=limits)
        assert debugger.ip == 0
        read_count = int(refusal == "read")
        partial = ExecutionResult("", read_count, read_count, 0, steps=0)
        assert caught.value.observation == debugger.observation == partial
        accepted_draws = 1 if refusal == "draw" else total_draws
        read_values = (("1" if numeric else ord("a")),) if read_count else ()
        boundary = WorkspaceVariant(
            "pending_ports", (0, read_values, (0,) * accepted_draws)
        )
        saved = debugger.snapshot()
        assert saved[-1] == boundary
        workspace = debugger.vm._machine.workspace_snapshot()
        assert (
            workspace.parts[workspace.model.components.index("instruction")] == boundary
        )
        if refusal == "read":
            with pytest.raises(TimeoutError, match="needs input"):
                run_until_halt_or_all_branches_cycle(debugger, limit=8)
            assert debugger.snapshot() == saved

        assert debugger.run(limits=limits) == "halted"
        assert debugger.observation == expected
        assert caught.value.observation == partial
        assert len(reads) == 7 + int(refusal == "read")
        assert len(draws) == total_draws + int(refusal == "draw")
        assert debugger.snapshot()[9] == total_draws


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

    def test_an_eof_keeps_the_repeated_reads_already_done(self, monkeypatch) -> None:
        """Pins EOF mid-repeat: ``ci`` reads 5, then EOF; the 5 survives."""
        machine = Painfuck(_encode("ci"), ScriptedIO("5\n"))
        with pytest.raises(EOFError):  # one step: c binds to the i
            machine.step()
        assert (machine.tape, machine.ind, machine.rep) == ((5,), 2, 5)

        for target, data, refusal in (
            ("cju", "abcdefghijklmn", "read"),
            ("cio", "1 2 3 4 5 6 7 8 9", "read"),
            ("cyju", "abcdefghijklmn", "read"),
            ("cyju", "abcdefghijklmn", "draw"),
        ):
            _check_repeated_port_retry(
                target, data, refusal=refusal, monkeypatch=monkeypatch
            )

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

    def test_a_far_move_stores_no_cells(self) -> None:
        """``ctt`` moves 7**13 cells in one step; the tape stays sparse.

        A dense tuple built every cell, and a trace-corpus program was killed
        at 8 GB (2026-11-17).  Zero cells are never stored.
        """
        for move, pos in (("l", -(7**13)), ("r", 2 * 7**13)):
            machine = Painfuck(_encode(f"pctt{move}pe"), ScriptedIO())
            for _ in range(3):
                machine.step()
            assert machine.cells == (tuple(sorted((0, pos))), (2, 2)), move
        assert run_program("pocttlzoe") == "20"
        assert _put(_put(((), ()), 3, 5), 3, 0) == ((), ())

    def test_debugger_inspects_far_cells_without_building_the_tape(self) -> None:
        debugger = Debugger(make_debugger("Painfuck", _encode("pccttle")))
        distant = 49**13
        first = debugger.watch_cell(0)
        origin = debugger.watch_cell(distant)
        outside = debugger.watch_cell(distant + 1)
        debugger.break_on_cell(distant, 2)
        assert debugger.run(limits=ExecutionLimits(max_steps=4)) == "breakpoint"
        assert first == [2, 0]
        assert origin == [None, 2]
        assert outside == [None, None]
        with pytest.raises(InterpreterLimitError, match="dense view limit"):
            _ = debugger.memory
        assert debugger.run(limits=ExecutionLimits(max_steps=4)) == "halted"


class TestRepeatCollapsing:
    """The closed forms `_advance` uses instead of looping `rep` times."""

    @staticmethod
    def _iterate(
        op: str, tape: tuple[int, ...], ptr: int, origin: int, rep: int
    ) -> tuple:
        """Apply ``op`` ``rep`` times, one step at a time."""
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
                tape = _set(tape, ptr, tape[ptr] // 2)
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
def test_hints_for_bad_programs_and_input() -> None:
    assert_halts_with_hint("Painfuck", "i", HaltError.DEFAULT, "decimal integer", "x")


def test_painfuck_all_coin_outcomes_can_be_proved_to_loop() -> None:
    """Either ``y`` outcome reaches a loop close and returns to ``a``."""
    code = _encode("paybb")
    machine = Painfuck(code, ScriptedIO())
    assert run_until_halt_or_all_branches_cycle(machine) is False
    # Every outcome loops, so the hang is proved whatever this run draws.
    for coin in (0, 1):
        draws = FirstDraw(coin, rest=coin)
        assert (
            run_until_halt_or_cycle(Painfuck(code, ScriptedIO(), draws), limit=64)
            is False
        )


def test_painfuck_one_halting_coin_refutes_an_all_branches_hang() -> None:
    code = _encode("payb")
    machine = Painfuck(code, ScriptedIO())
    assert run_until_halt_or_all_branches_cycle(machine) is True
    halting = Painfuck(code, ScriptedIO(), FirstDraw(1))
    assert run_until_halt(halting, limit=1000) is True
    looping = Painfuck(code, ScriptedIO(), FirstDraw(0, rest=0))
    with pytest.raises(TypeError, match="random machines"):
        run_until_halt_or_cycle(looping, limit=64)


def test_branch_search_keeps_clean_and_faulting_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    machine = Painfuck(_encode("b"), ScriptedIO())
    start = machine.branching_snapshot()
    assert machine.branching_halted(start) is False

    with pytest.raises(HaltError, match="unmatched 'b'"):
        machine.branching_successors(start, 100)
    for proof in (run_until_halt_or_cycle, run_until_halt_or_all_branches_cycle):
        vm = Language("Painfuck").make_vm(_encode("b"))
        with pytest.raises(HaltError, match="unmatched 'b'"):
            proof(vm, limit=2)
        assert proof(Language("Painfuck").make_vm(_encode("e")), limit=2) is True

    api = Language("Painfuck")
    for program, error in (("yj", InputExhaustedError), ("yb", HaltError)):
        source = _encode(program)
        limits = ExecutionLimits(max_steps=1)
        assert api.run(source, seed=0, limits=limits).steps == 1
        with pytest.raises(error):
            api.run(source, seed=4, limits=limits)
        machine = api.make_vm(source, seed=4)
        saved = machine.snapshot()
        with pytest.raises(TimeoutError, match="coin outcomes"):
            run_until_halt_or_all_branches_cycle(machine, limit=1)
        assert run_until_halt_or_all_branches_cycle(machine, limit=2) is True
        assert machine.snapshot() == saved

    write = ScriptedIO._write
    for target, answer, accepted, raw_first, draws, steps in (
        ("pyu", "\x02", 0, "\x02", 1, 2),
        ("pyu", "\x02", 1, "\x02", 1, 2),
        ("cpyo", "14", 1, 14, 1, 2),
        ("cyo", "0000", 2, "0000", 7, 1),
    ):
        source = _encode(target)
        limits = ExecutionLimits(max_steps=steps)
        expected = api.run(source, seed=4, limits=limits)
        assert (expected.output, expected.steps) == (answer, steps)
        attempts = []
        faults = 2 if accepted < len(answer) else 1

        def refuse(io, value, _attempts=attempts, _accepted=accepted, _faults=faults):
            _attempts.append(value)
            if len(_attempts) <= _faults:
                if len(_attempts) == 1:
                    write(io, str(value)[:_accepted])
                raise HaltError("temporary writer refusal")
            write(io, value)

        with monkeypatch.context() as port:
            port.setattr(ScriptedIO, "_write", refuse)
            debugger = api.make_debugger(source, seed=4)
            partial = ExecutionResult(answer[:accepted], 0, 0, 0, steps=steps - 1)
            saved = None
            for _ in range(faults):
                with pytest.raises(
                    HaltError, match="temporary writer refusal"
                ) as caught:
                    debugger.run(limits=limits)
                assert caught.value.observation == debugger.observation == partial
                snapshot = debugger.snapshot()
                assert snapshot[9] == draws
                assert snapshot[-1][-1] == accepted
                assert saved is None or saved == snapshot
                saved = snapshot
                assert run_until_halt_or_cycle(debugger, limit=2) is True
                assert debugger.snapshot() == saved

            assert debugger.run(limits=ExecutionLimits(max_steps=1)) == "halted"
            assert debugger.observation == expected
            assert debugger.snapshot()[9] == draws
            assert attempts == [
                raw_first,
                *([answer[accepted:]] * 2 if faults == 2 else []),
            ]


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


def test_stepping_through_the_random_instruction_is_reproducible(monkeypatch) -> None:
    """Its random instruction steps the same way twice under one seed."""
    assert_random_steps_reproduce("Painfuck", "y")

    rng, before, options, factory = rng_factory(prepare_machine, _encode("yp"))
    options.clear()
    first, second = factory(ScriptedIO()), factory(ScriptedIO())
    assert first is not second
    assert first._rng is second._rng is rng
    assert rng._random.getstate() == before
    initial = second.snapshot()
    first.step()
    assert rng._random.getstate() != before
    assert second.snapshot() == initial
    assert second.memory == [0]
    assert second.ptr == second.ind == 0
    assert second.snapshot() == initial
    reject_rng_options(prepare_machine, [], "text source", "")

    from esolangs.languages.painfuck import interpreter
    from tests.support.prepared_support import check_random_plan_reuse

    check_random_plan_reuse(
        "Painfuck", _encode("cypoe"), interpreter, "_translate", monkeypatch
    )


def test_branching_limit_admits_exactly_its_outcomes() -> None:
    # One coin forks into two outcomes: a limit of 2 holds them, 1 does not.
    machine = Painfuck(_encode("yp"), ScriptedIO())
    start = machine.branching_snapshot()
    assert machine.branching_successors(start, 0) is None
    assert len(machine.branching_successors(start, 2) or ()) == 2
    with pytest.raises(TimeoutError, match="coin outcomes"):
        machine.branching_successors(start, 1)

    plain = Painfuck("p", ScriptedIO())
    state = plain.branching_snapshot()
    assert plain.branching_successors(state, 0) is None
    outcomes = plain.branching_successors(state, 1)
    assert outcomes is not None
    assert len(outcomes) == 1
    plain.step()
    assert outcomes == (plain.branching_snapshot(),)

    class RefuseCoin:
        draws = 0

        def randbelow(self, upper):
            assert upper == 2
            self.draws += 1
            if self.draws == 2:
                raise HaltError("temporary coin refusal")
            return int(self.draws == 1)

    coins = RefuseCoin()
    machine = Painfuck(_encode("cyp"), ScriptedIO(), coins)
    initial = machine.branching_snapshot()
    with pytest.raises(TimeoutError, match="coin outcomes"):
        machine.branching_successors(initial, 64)
    with pytest.raises(HaltError, match="temporary coin refusal"):
        machine.step()
    pending = machine.branching_snapshot()
    assert not machine.branching_halted(pending)
    assert pending != initial
    outcomes = machine.branching_successors(pending, 64)
    assert outcomes is not None
    assert {_get(state[0], 0) for state in outcomes} == set(range(0, 13, 2))
    assert machine.branching_snapshot() == pending
    assert coins.draws == 2  # Analysis used only the remembered first draw.
    machine.step()
    assert machine.halted
    assert machine.memory == [12]
    assert coins.draws == 8


def test_w_copies_the_right_neighbour_from_a_middle_cell() -> None:
    # Cells 2 and 4 hold 4 and 6; from cell 3, w takes 6, not the left 4.
    assert run_program("rpprppplwo") == "6"

    # Start with the input at the origin, copy it from the left at cell 1,
    # then square and halve before emitting both representations.
    for value, subtract, coin in product((-19, 0, 5, 257), range(4), (0, 1)):
        commands = "irlq" + "s" * subtract + "khypoue"
        squared = (value - subtract) ** 2 // 2
        result = squared + (0 if coin else 2)
        assert run_program(commands, f"{value}\n", coin) == str(result) + chr(
            result % 256
        )

    for value in (-257, -256, -1, 255, 256, 257):
        assert run_program("ioue", f"{value}\n") == str(value) + chr(value % 256)


@pytest.mark.parametrize("coin", [0, 1])
@pytest.mark.parametrize(
    ("commands", "owed"), [("y", 1), ("py", 1), ("cy", 7), ("ccy", 49), ("yy", 2)]
)
def test_trailing_y_consumes_only_its_owed_coins(
    commands: str, owed: int, coin: int
) -> None:
    class BoundedCoin(_Coin):
        draws = 0

        def randbelow(self, upper: int) -> int:
            self.draws += 1
            assert self.draws <= owed, "trailing y requested another coin"
            return super().randbelow(upper)

    source = BoundedCoin(coin)
    machine = Painfuck(_encode(commands), ScriptedIO(), source)
    assert run_until_halt(machine, limit=2) is True
    assert source.draws == (1 if commands == "yy" and coin else owed)
    final = machine.snapshot()
    machine.step()
    assert machine.snapshot() == final
    assert machine.io.getvalue() == ""
    assert run_program("pv") == ""


@pytest.mark.parametrize("value", [0, 1, -1])
def test_loop_end_tests_the_cell_before_jumping(value: int) -> None:
    state = ((value,), (0,), 0, 2, 1, 0)
    (tape, loops, _pointer, cursor, _repeat, _origin), _effects = _advance(
        state, "azb", 3, (), ()
    )
    assert cursor == (3 if value == 0 else 0)
    assert loops == ()
    assert tape == (value,)


def test_wide_decimal_reads_and_repeated_prints_ignore_the_host_digit_cap():
    from tests.support.execution import assert_digit_cap_independent

    digits = "9" * 641
    assert_digit_cap_independent("Painfuck", _encode("ioe"), digits, digits)
    value = "1" + "0" * 639 + "1"
    assert_digit_cap_independent("Painfuck", _encode("ipcoe"), digits[:-1], value * 7)
