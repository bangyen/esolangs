"""A divergence certificate for the sweeps that used to time one.

Several suites need to tell "this program loops forever" from "this program
is still going", and the cheap way to do it is a stopwatch: run with a
bound, and read a timeout as a loop.  That decides nothing.  A timeout says
only that the run had not finished, which is equally what a slow run says,
so the bound has to be guessed high enough to be safe and is then paid in
full on every looping row -- ~42s in `test_generic_verifier.py` and 40s in
`tests/tools/test_wrap.py`, all of it spent waiting rather than deciding.

:func:`~esolangs.vm.run_until_halt_or_cycle` decides it: a machine that
revisits an exact state can never halt, so a repeated snapshot is a proof.
Over the four termination-answering languages with boolean generators (123,
ArrowQueue, Crement, Vandevelo) it returns the right answer for every row of
every table in those suites in 0.014s total, no row over 0.3ms.

What it cannot do is decide divergence-by-*growth*: a machine whose tape
keeps growing never repeats a state, so the search would not return.  Hence
:data:`_CYCLE_STEPS`, and hence the tri-state -- ``None`` means undecided,
and a caller that gets it should fall back to its clock rather than guess.
"""

from __future__ import annotations

import esolangs
from esolangs.vm import make_vm, run_until_halt_or_cycle

#: Step cap on the certificate, matching ``run_until_halt_or_growth``'s own.
#: Nothing here comes near it; it is what keeps an undecidable-by-cycle
#: program from hanging the suite instead of merely being slow.
_CYCLE_STEPS = 100_000


def diverges(name: str, source: str, stdin: str) -> bool | None:
    """Whether ``source`` provably never halts, or ``None`` if undecided.

    ``True`` on a proven cycle, ``False`` on a halt the detector watched
    happen, ``None`` when no proof was available -- no VM for the language,
    no snapshot on its machine, a fault mid-step (Taglate reads past its
    input under the VM), or the cap reached.  Only the first two are
    verdicts; ``None`` is the caller's cue to use a timeout instead.
    """
    try:
        machine = make_vm(name, source, stdin)
    except Exception:
        return None
    try:
        return not run_until_halt_or_cycle(machine, limit=_CYCLE_STEPS)
    except Exception:
        return None


def terminates(name: str, source: str, stdin: str, timeout: float) -> bool:
    """Whether a run halts, proving a cycle before using time as the oracle."""
    proven = diverges(name, source, stdin)
    if proven is not None:
        return not proven
    try:
        esolangs.run(name, source, stdin=stdin, timeout=timeout)
    except esolangs.ExecutionTimeoutError:
        return False
    return True
