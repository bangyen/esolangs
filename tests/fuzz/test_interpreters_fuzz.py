"""Fuzz every interpreter, plus deeper alphabet fuzzing where it is safe.

Every registered interpreter runs a seeded set of mutations of its sample
program and a hostile short source under a VM step cap.  The small ``FUZZ``
table adds unrestricted alphabet fuzzing for languages whose random programs
must terminate -- halting or rejecting -- rather than legitimately looping.
"""

import importlib
import os
import random
import signal
from unittest.mock import patch

import pytest

from esolangs.exceptions import EsolangError
from esolangs.interpreters.io import IO
from esolangs.registry import RUNNERS
from esolangs.vm import make_vm
from tests.samples import SAMPLES

# interpreter module -> instruction alphabet; input is mocked below.
FUZZ = {
    "queue_based.bitdeque": "PUSHINJECTEJECTPOPINVERT",
    "register_based.minsky_swap": "+~*",
    "other.lamfunc": "p eq i cb lb fb vs vg F . x 0 1",
}

# ArrowQueue, back, Between, Jaune, Point Break, and RAM0 are
# not fuzzed here: they have unconditional, goto, or directional loops
# (Jaune's ?/! jumps, Point Break's POINT/END), so a random program may
# legitimately never terminate and the "terminates" invariant does not
# apply to them.


def _mutated_sources(language: str) -> list[tuple[str, str]]:
    """Return short hostile variants of ``language``'s known-good program.

    Every interpreter gets this fuzzer, including languages with generators:
    generated programs cover the intended language, while these edits exercise
    parser and runtime boundaries that generation cannot produce.  The VM
    supplies a fixed step cap, so a legal random loop is not mistaken for a
    hung test.
    """
    program, stdin = SAMPLES[language]
    rng = random.Random(sum(map(ord, language)))
    variants = [(program, stdin)]
    for _ in range(4):
        if rng.randrange(2):
            at = rng.randrange(len(program) + 1)
            ch = rng.choice("!?+-*/[]{}()<>;:,. 01az\n")
            variants.append((program[:at] + ch + program[at:], stdin))
        else:
            at = rng.randrange(len(program))
            variants.append((program[:at] + program[at + 1 :], stdin))
    variants.append(
        (
            "".join(rng.choice("!?+-*/[]{}()<>;:,. 01az\n") for _ in range(12)),
            "",
        )
    )
    return variants


@pytest.mark.parametrize("language", sorted(RUNNERS))
def test_every_interpreter_fuzzes_mutated_sources(language: str) -> None:
    """Fuzz every registered interpreter through bounded VM execution."""
    for program, stdin in _mutated_sources(language):
        try:
            vm = make_vm(language, program, stdin)
            for _ in range(100):
                if vm.halted:
                    break
                vm.step()
        except (EsolangError, ValueError, EOFError, SystemExit):
            pass  # rejection and exhausted input are documented outcomes


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
