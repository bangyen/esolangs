"""A divergence certificate for the sweeps that used to time one."""

from __future__ import annotations

import esolangs
from esolangs.vm import make_vm, run_until_halt_or_cycle

#: Step cap on the certificate, matching ``run_until_halt_or_growth``'s own.
#: Nothing here comes near it; it is what keeps an undecidable-by-cycle
#: program from hanging the suite instead of merely being slow.
_CYCLE_STEPS = 100_000


def diverges(name: str, source: str, stdin: str) -> bool | None:
    """Whether ``source`` provably never halts, or ``None`` if undecided."""
    try:
        machine = make_vm(name, source, stdin=stdin)
    except Exception:
        return None
    try:
        return not run_until_halt_or_cycle(machine, limit=_CYCLE_STEPS)
    except Exception:
        return None


def terminates(name: str, source: str, stdin: str, timeout: float) -> bool:
    """Whether a run halts; an undecided timeout propagates."""
    proven = diverges(name, source, stdin)
    if proven is not None:
        return not proven
    esolangs.run(name, source, stdin=stdin, timeout=timeout)
    return True
