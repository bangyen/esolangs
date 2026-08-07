"""Robustness properties shared by every interpreter.

The one invariant that holds across all the languages is that an
interpreter terminates on the empty program: it either halts (possibly
with no output) or rejects the input, but it never spins forever.
"""

import importlib
import os
import signal
from pathlib import Path

import pytest

INTERPRETER_DIR = Path(__file__).parents[1] / "src" / "esolangs" / "interpreters"

MODULES = []
for category in ("tape_based", "stack_based", "register_based", "other"):
    for path in sorted((INTERPRETER_DIR / category).glob("*.py")):
        if path.name.startswith("_"):
            continue
        MODULES.append(f"esolangs.interpreters.{category}.{path.stem}")


class _Timeout(Exception):
    """Raised by the alarm handler when an interpreter does not terminate."""


def _on_alarm(signum: int, frame: object) -> None:
    raise _Timeout("interpreter did not terminate on the empty program")


@pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
@pytest.mark.parametrize("module", MODULES)
def test_empty_program_terminates(module: str) -> None:
    run = importlib.import_module(module).run
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(3)
    try:
        run("")
    except _Timeout:
        pytest.fail(f"{module} hangs on the empty program")
    except Exception:
        pass  # rejecting the empty program is a valid termination
    finally:
        signal.alarm(0)
