"""Answer a row by proving halting or a repeated machine state."""

from functools import partial

import esolangs
from esolangs.exceptions import InterpreterLimitError
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options
from esolangs.vm import make_vm, run_until_halt_or_cycle


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
    dialect_options(name, settings)

    def _drive(*_args: object) -> bool:
        factory = make_vm if settings is None else partial(make_vm, settings=settings)
        machine = factory(name, source, stdin=stdin)
        return run_until_halt_or_cycle(machine)

    verdict = esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    if verdict is True:
        return halts
    if verdict is False:
        return diverges
    raise InterpreterLimitError(
        "termination driver returned no boolean verdict",
        hint="check the termination driver or report this interpreter error",
    )
