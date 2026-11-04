"""Answer a row by proving halting or a repeated machine state."""

from functools import partial

import esolangs
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

    # A box, because ``_run`` exists to apply the timeout and discards what
    # it drove -- which is right for ``run``, whose result is the io buffer.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        factory = make_vm if settings is None else partial(make_vm, settings=settings)
        machine = factory(name, source, stdin=stdin)
        verdict.append(run_until_halt_or_cycle(machine))

    esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    return halts if verdict and verdict[0] else diverges
