"""Fuzz the interpreters that have no generators.

The generator-backed languages are fuzzed through their generators (see
test_fuzz_generators.py). These languages have no generator, so random
programs drawn from their instruction alphabets are the only broad way to
exercise them. The invariant is that a random program terminates -- halting
or rejecting -- and never spins forever.
"""

import importlib
import os
import random
import signal
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO

# interpreter module -> instruction alphabet. lightlang's "_" (sleep) is
# left out so the fuzz stays fast, and input is mocked below.
FUZZ = {
    "queue_based.bitdeque": "PUSHINJECTEJECTPOPINVERT",
    "other.keys": "-_\\/",
    "register_based.minsky_swap": "+~*",
    "tape_based.movesum": "move sum0123456789",
    "other.lamfunc": "p eq i cb lb fb vs vg F . x 0 1",
}

# ArrowQueue, back, Between, lightlang, and RAM0 are not fuzzed here: they
# have unconditional, goto, or directional loops, so a random program may
# legitimately never terminate and the "terminates" invariant does not apply
# to them.


class _TimeoutError(Exception):
    """Raised by the alarm handler when a random program does not terminate."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError("interpreter did not terminate on a random program")


@pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
@pytest.mark.parametrize("module", sorted(FUZZ))
def test_random_programs_terminate(module: str) -> None:
    random.seed(sum(map(ord, module)))
    alphabet = FUZZ[module]
    run = importlib.import_module("esolangs.interpreters." + module).run
    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    try:
        for _ in range(25):
            program = "".join(
                random.choice(alphabet) for _ in range(random.randint(1, 24))
            )
            signal.alarm(3)
            try:
                with patch("builtins.input", return_value="0"):
                    run(program, io=IO())
            except _TimeoutError:
                pytest.fail(f"{module} hung on a random program")
            except Exception:
                pass  # rejecting a random program is a valid termination
            finally:
                signal.alarm(0)
    finally:
        signal.signal(signal.SIGALRM, old_handler)
