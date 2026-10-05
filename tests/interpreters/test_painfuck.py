"""Unit tests for the Painfuck interpreter."""

import importlib

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

run = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run
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


class TestStepMachine:
    def test_growing_the_tape_leaves_an_addressable_pointer_alone(self) -> None:
        """``_grow`` returns the tape untouched when the pointer already fits.

        Every program here walks right one cell at a time, so the tape is
        always grown by exactly the cell being stepped onto and the
        already-addressable case never came up.  Called directly: the guard
        is what keeps a re-visit from re-extending the tape.
        """
        from esolangs.interpreters.tape_based.painfuck import _grow

        tape = (1, 2, 3)
        assert _grow(tape, 0) is tape
        assert _grow(tape, 2) is tape
        assert _grow(tape, 4) == (1, 2, 3, 0, 0)


class TestRepeatCollapsing:
    """Repeated loop commands make one jump decision."""

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
            state = ((5,), (), 0, 0, rep)
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
    looping_program = _encode("pab")
