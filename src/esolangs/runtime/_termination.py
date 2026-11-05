"""Observe IO while proving halting or a repeated machine state."""

from functools import partial

import esolangs
from esolangs._cycles import _halt_or_cycle_result
from esolangs.exceptions import EsolangError, InterpreterLimitError
from esolangs.runtime._program import Program
from esolangs.runtime._proof import (
    TerminationResult,
    checked_termination,
)
from esolangs.runtime._result import ExecutionResult
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options
from esolangs.vm import _capture_observation, make_vm


def _termination_result(
    name: str,
    source: Program,
    stdin: str,
    bound: float | None,
    *,
    settings: DialectSettings | None = None,
) -> TerminationResult:
    """Retain live IO and proof evidence without taking a post-halt dump step."""
    dialect_options(name, settings)

    def _drive(*_args: object) -> TerminationResult:
        factory = make_vm if settings is None else partial(make_vm, settings=settings)
        machine = factory(name, source, stdin=stdin)
        try:
            decision = _halt_or_cycle_result(machine)
            return TerminationResult(_capture_observation(machine), decision)
        except EsolangError as error:
            error.partial_output = machine.output
            raise

    verdict = esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    try:
        return checked_termination(verdict)
    except ValueError as error:
        failure = InterpreterLimitError(
            "termination driver returned no decision evidence",
            hint="check the termination driver or report this interpreter error",
        )
        if isinstance(verdict, TerminationResult) and isinstance(
            verdict.observation, ExecutionResult
        ):
            failure.partial_output = verdict.observation.output
        raise failure from error
