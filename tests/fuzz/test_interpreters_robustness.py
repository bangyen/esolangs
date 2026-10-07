"""Robustness properties shared by every interpreter."""

import importlib
import os
import signal
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from esolangs.interpreters.io import IO
from esolangs.vm import run_until_halt_or_cycle

INTERPRETER_DIR = Path(__file__).parents[2] / "src" / "esolangs" / "interpreters"

# Globbed rather than listed by category.  This sweep used to name its five
# categories in a tuple that omitted ``grid_based``, so eleven interpreters
# -- every grid language -- were silently exempt from a file whose docstring
# claims to cover "every interpreter".  It is the same hole
# the retired docstring script had, where a stale category tuple exempted
# twelve of sixty-three interpreters and three real violations sat behind
# it.  A walk that discovers the tree cannot acquire that hole again, which
# is why ``tests/test_interpreter_conventions.py`` already reads the tree
# this way.
MODULES = [
    f"esolangs.interpreters.{path.parent.name}.{path.stem}"
    for path in sorted(INTERPRETER_DIR.glob("*/*.py"))
    if not path.name.startswith("_")
]


#: Machines whose empty program is not ``_Machine("", io)``.  (Five older
#: entries here called constructors that no longer exist, so the sweep caught
#: their TypeError and passed without building a machine.)
_EMPTY: dict[str, Callable[[Any, IO], object]] = {
    "tape_based.brainif": lambda machine, io: machine([], io),
    "queue_based.taglate": lambda machine, io: machine([], io),
    "tape_based.back": lambda machine, io: machine([], io),
    "other.container": lambda machine, io: machine([], io),
    # An empty program is malformed in CV(N)(C), so the stand-in is the
    # shortest legal one: a single syllable that does nothing observable.
    "other.cvnc": lambda machine, io: machine("ci", io),
    "other.forbin": lambda machine, io: machine("main {}", io),
}


def _empty_machine(module: str, io: IO) -> object:
    """Build ``module``'s step-capable machine for the empty program."""
    machine = getattr(importlib.import_module(module), "_Machine")  # noqa: B009
    key = module.removeprefix("esolangs.interpreters.")
    return _EMPTY.get(key, lambda machine, io: machine("", io))(machine, io)


# The interpreter modules whose machine exposes step()/halted/snapshot() and
# can therefore be checked by state-cycle detection.
_STEP_MACHINES = {
    "esolangs.interpreters.tape_based.brainfuck",
    "esolangs.interpreters.tape_based.sbleq",
    "esolangs.interpreters.tape_based.dimensional",
    "esolangs.interpreters.tape_based.one_two_three",
    "esolangs.interpreters.stack_based.eval",
    "esolangs.interpreters.stack_based.modulous",
    "esolangs.interpreters.register_based.qoibl",
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
    "esolangs.interpreters.tape_based.factor",
    "esolangs.interpreters.tape_based.bit_tilde",
    "esolangs.interpreters.register_based.collatz_multiverse",
    "esolangs.interpreters.register_based.polynomial",
    "esolangs.interpreters.stack_based.grapheme",
    "esolangs.interpreters.register_based.ram0",
    "esolangs.interpreters.register_based.minsky_swap",
    "esolangs.interpreters.tape_based.home_row",
    "esolangs.interpreters.stack_based.unsquare",
    "esolangs.interpreters.tape_based.suffolk",
    "esolangs.interpreters.other.container",
    "esolangs.interpreters.stack_based.bf_pda",
    "esolangs.interpreters.stack_based.three_x",
    "esolangs.interpreters.register_based.sophie",
    "esolangs.interpreters.tape_based.jaune",
    "esolangs.interpreters.tape_based.slow_acv_mammalian",
    "esolangs.interpreters.other.cvnc",
    "esolangs.interpreters.other.fargo",
    "esolangs.interpreters.other.forbin",
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
