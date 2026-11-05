"""Answer a row by proving halting or a repeated machine state."""

from functools import partial

import esolangs
from esolangs._cycles import _halt_or_cycle_result
from esolangs.exceptions import InterpreterLimitError
from esolangs.runtime._proof import CycleDecision, checked_decision
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options
from esolangs.vm import make_vm


def _terminates(
    name: str,
    source: str,
    stdin: str,
    bound: float | None,
    halts: str,
    diverges: str,
    *,
    settings: DialectSettings | None = None,
) -> str:
    """Return this row's answer for a language that answers by terminating.

    Repeated snapshots prove divergence; a growing state needs the deadline.
    """
    verdict = _termination_decision(name, source, stdin, bound, settings=settings)
    return halts if verdict.halts else diverges


def _termination_decision(
    name: str,
    source: str,
    stdin: str,
    bound: float | None,
    *,
    settings: DialectSettings | None = None,
) -> CycleDecision:
    """Return explicit halt or cycle evidence; a deadline remains undecided."""
    dialect_options(name, settings)

    def _drive(*_args: object) -> CycleDecision:
        factory = make_vm if settings is None else partial(make_vm, settings=settings)
        machine = factory(name, source, stdin=stdin)
        return _halt_or_cycle_result(machine)

    verdict = esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    try:
        return checked_decision(verdict)
    except ValueError as error:
        raise InterpreterLimitError(
            "termination driver returned no decision evidence",
            hint="check the termination driver or report this interpreter error",
        ) from error
