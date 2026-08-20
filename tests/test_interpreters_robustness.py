"""Robustness properties shared by every interpreter.

The one invariant that holds across all the languages is that an
interpreter terminates on the empty program: it either halts (possibly
with no output) or rejects the input, but it never spins forever.

Where the interpreter exposes a step-capable machine, termination is
decided deterministically by state-cycle detection
(:func:`esolangs.vm.run_until_halt_or_cycle`): a deterministic machine
that revisits an exact internal state has looped forever, so the check
needs no wall-clock bound and is not POSIX-only.  Languages without a
step-capable machine (and Grapheme, whose machine has no ``snapshot()``
yet) keep the SIGALRM backstop, which stays for the unbounded-growth
hang class that cycle detection cannot catch.
"""

import importlib
import os
import signal
from pathlib import Path

import pytest

from esolangs.interpreters.io import IO
from esolangs.vm import run_until_halt_or_cycle

INTERPRETER_DIR = Path(__file__).parents[1] / "src" / "esolangs" / "interpreters"

MODULES = []
for category in ("tape_based", "stack_based", "register_based", "queue_based", "other"):
    for path in sorted((INTERPRETER_DIR / category).glob("*.py")):
        if path.name.startswith("_"):
            continue
        MODULES.append(f"esolangs.interpreters.{category}.{path.stem}")


def _empty_machine(module: str, io: IO) -> object:
    """Build ``module``'s step-capable machine for the empty program.

    The constructions mirror the VM adapters in :mod:`esolangs.vm`.
    """
    if module == "esolangs.interpreters.tape_based.brainfuck":
        from esolangs.interpreters.tape_based.brainfuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.sbleq":
        from esolangs.interpreters.tape_based.sbleq import _Machine

        return _Machine(io=io, mem=[])
    if module == "esolangs.interpreters.tape_based.dimensional":
        from esolangs.interpreters.tape_based.dimensional import _Runner

        return _Runner("", io)
    if module == "esolangs.interpreters.tape_based.one_two_three":
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.stack_based.eval":
        from esolangs.interpreters.stack_based.eval import State

        return State(io=io, sym="")
    if module == "esolangs.interpreters.stack_based.modulous":
        from esolangs.interpreters.stack_based.modulous import State

        state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=io)
        state.tokens = []
        return state
    if module == "esolangs.interpreters.stack_based.the_temporary_stack":
        from esolangs.interpreters.stack_based.the_temporary_stack import State

        state = State(io=io)
        state.code = []
        return state
    if module == "esolangs.interpreters.register_based.qoibl":
        from esolangs.interpreters.register_based.qoibl import State

        state = State(io=io)
        state.code = []
        return state
    if module == "esolangs.interpreters.register_based.point_break":
        from esolangs.interpreters.register_based.point_break import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.stack_based.forth":
        from esolangs.interpreters.stack_based.forth import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.register_based.addsubjump":
        from esolangs.interpreters.register_based.addsubjump import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.queue_based.bitdeque":
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.minifuck":
        from esolangs.interpreters.tape_based.minifuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.brainif":
        from esolangs.interpreters.tape_based.brainif import _Machine

        return _Machine([], io)
    if module == "esolangs.interpreters.queue_based.taglate":
        from esolangs.interpreters.queue_based.taglate import _Machine

        return _Machine([], io)
    if module == "esolangs.interpreters.tape_based.rotfuck":
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.circlefuck":
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.stack_based.bfstack":
        from esolangs.interpreters.stack_based.bfstack import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.register_based.decleq":
        from esolangs.interpreters.register_based.decleq import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.six_five":
        from esolangs.interpreters.tape_based.six_five import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.back":
        from esolangs.interpreters.tape_based.back import _Machine

        return _Machine([], io)
    if module == "esolangs.interpreters.register_based.bio":
        from esolangs.interpreters.register_based.bio import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.nocomment":
        from esolangs.interpreters.tape_based.nocomment import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.three_d_brainfuck":
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.factor":
        from esolangs.interpreters.tape_based.factor import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.basicfuck":
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.tape_based.bit_tilde":
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.register_based.collatz_multiverse":
        from esolangs.interpreters.register_based.collatz_multiverse import _Machine

        return _Machine("", io)
    if module == "esolangs.interpreters.register_based.polynomial":
        from esolangs.interpreters.register_based.polynomial import _Machine

        return _Machine("", io)
    raise KeyError(module)


# The interpreter modules whose machine exposes step()/halted/snapshot() and
# can therefore be checked by state-cycle detection.
_STEP_MACHINES = {
    "esolangs.interpreters.tape_based.brainfuck",
    "esolangs.interpreters.tape_based.sbleq",
    "esolangs.interpreters.tape_based.dimensional",
    "esolangs.interpreters.tape_based.one_two_three",
    "esolangs.interpreters.stack_based.eval",
    "esolangs.interpreters.stack_based.modulous",
    "esolangs.interpreters.stack_based.the_temporary_stack",
    "esolangs.interpreters.register_based.qoibl",
    "esolangs.interpreters.register_based.point_break",
    "esolangs.interpreters.stack_based.forth",
    "esolangs.interpreters.register_based.addsubjump",
    "esolangs.interpreters.queue_based.bitdeque",
    "esolangs.interpreters.tape_based.minifuck",
    "esolangs.interpreters.tape_based.brainif",
    "esolangs.interpreters.queue_based.taglate",
    "esolangs.interpreters.tape_based.rotfuck",
    "esolangs.interpreters.tape_based.circlefuck",
    "esolangs.interpreters.stack_based.bfstack",
    "esolangs.interpreters.register_based.decleq",
    "esolangs.interpreters.tape_based.six_five",
    "esolangs.interpreters.tape_based.back",
    "esolangs.interpreters.register_based.bio",
    "esolangs.interpreters.tape_based.nocomment",
    "esolangs.interpreters.tape_based.three_d_brainfuck",
    "esolangs.interpreters.tape_based.factor",
    "esolangs.interpreters.tape_based.basicfuck",
    "esolangs.interpreters.tape_based.bit_tilde",
    "esolangs.interpreters.register_based.collatz_multiverse",
    "esolangs.interpreters.register_based.polynomial",
}


class _TimeoutError(Exception):
    """Raised by the alarm handler when an interpreter does not terminate."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError("interpreter did not terminate on the empty program")


@pytest.mark.parametrize("module", MODULES)
def test_empty_program_terminates(module: str) -> None:
    if module in _STEP_MACHINES:
        _assert_step_machine_halts(module)
        return
    if os.name != "posix":
        pytest.skip("signal.alarm is POSIX-only")
    _assert_wall_clock_terminates(module)


def _assert_step_machine_halts(module: str) -> None:
    """Prove the empty program terminates via state-cycle detection."""
    try:
        machine = _empty_machine(module, IO())
        halted = run_until_halt_or_cycle(machine)
    except Exception:
        return  # rejecting the empty program is a valid termination
    assert halted is True, f"{module} loops on the empty program"


def _assert_wall_clock_terminates(module: str) -> None:
    """Bound the whole-program run with a wall-clock alarm (backstop)."""
    run = importlib.import_module(module).run
    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(3)
    try:
        run("", io=IO())
    except _TimeoutError:
        pytest.fail(f"{module} hangs on the empty program")
    except Exception:
        pass  # rejecting the empty program is a valid termination
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
