"""Evaluate a supplied program on every Boolean input row.

``esolangs.run`` is reached through the package at call time (patchable).
"""

from functools import partial
from typing import cast

import esolangs
from esolangs._answers import (
    encode_inputs,
    read_answer,
)
from esolangs._describe import describe
from esolangs._execution import check_signal_timeout
from esolangs._program import Program
from esolangs._source import ProgramSource, check_scale_for
from esolangs._validate import check_timeout
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.helpers import MOST_INPUTS
from esolangs.vm import make_vm


class _Default:
    """The "argument was not given" marker for :func:`evaluate`.

    ``None`` already means *unbounded* in :func:`run`, and meaning "default"
    here too left no value that turned the alarm off from a thread.
    """

    def __repr__(self) -> str:
        """Render as ``<default>`` in a signature rather than as an address."""
        return "<default>"


_DEFAULT = _Default()

#: A termination-answering language proves a 1 by *not* halting, so
#: :func:`evaluate` pays this once for every such row.  Four languages
#: carry that convention, so the floor is real and small.
_TERMINATION_TIMEOUT = 5.0

#: The bound on an ordinary row.  Generous: it exists to stop a hang, not
#: to hold anything to a schedule.
_ROW_TIMEOUT = 30.0


def evaluate(
    language: str,
    program: ProgramSource,
    timeout: float | _Default | None = _DEFAULT,
    *,
    inputs: int,
    isolated: bool = False,
    scale: int | None = None,
) -> str:
    """Return the table a supplied program computes over ``inputs`` bits.

    Inputs range from 1 to 64, in MSB-first row order. Parameterized languages
    require a template, filled separately for each row. Paths load text or PNG
    source. No program is generated.
    The default bounds each row to 30 seconds (5 for termination answers).
    Repeated states prove divergence; a timeout raises rather than counting as 1.
    ``None`` disables the deadline; ``isolated=True`` needs a finite deadline.
    """
    # Checked here, not only inside ``run``: the termination path drives the
    # machine itself and never reaches ``run``, so a bound too small to
    # service was refused for the languages that halt and silently read as
    # "diverges" for the termination-answer ones -- the same argument
    # answering a different table depending on which kind of language it was.
    if not isinstance(timeout, _Default):
        check_timeout(timeout)
    facts = describe(language)
    name = str(facts["name"])
    check_scale_for(name, scale)
    if (
        isinstance(inputs, bool)
        or not isinstance(inputs, int)
        or not 1 <= inputs <= MOST_INPUTS
    ):
        raise ArgumentError(f"inputs must be an integer from 1 to {MOST_INPUTS}")
    program = esolangs._read_source(name, program)  # noqa: SLF001
    rows = 1 << inputs
    terminating = facts["answer_mode"] == "termination"
    bound: float | None
    if isinstance(timeout, _Default):
        bound = _TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT
    else:
        # ``None`` is unbounded, as in :func:`run`, and the thread escape
        # hatch (the guard is ``SIGALRM``).
        bound = timeout
    if isolated and bound is None:
        raise ArgumentError("isolated evaluation requires a finite timeout")
    if not isolated:
        # The termination path drives ``_run`` directly and so never reached
        # ``run``'s guard: off a main thread it leaked ``signal.signal``'s
        # bare ValueError.  ``timeout=None`` is the route out, as for
        # :func:`run`; the divergers are settled by a repeated state.
        check_signal_timeout(
            bound,
            "evaluate's timeout guard uses SIGALRM and needs a Unix main "
            "thread; off it, pass timeout=None -- a diverging row is "
            "settled by a repeated machine state rather than waited for",
        )
    if terminating:
        # Which of halting and diverging means 1, as data.  It is
        # ``("halts", "diverges")`` for all four, but reading the order
        # rather than assuming it is what keeps this branch language-free.
        encoding = list(facts["answer_encoding"])
        diverges_is = str(encoding.index("diverges"))
        halts_is = str(encoding.index("halts"))
    answers = []
    for row in range(rows):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        source: Program
        if facts["parameterized"]:
            source, stdin = esolangs.instantiate(name, cast("str", program), bits), ""
        else:
            source, stdin = program, encode_inputs(name, bits)
        try:
            if terminating:
                source = cast("str", source)
                if isolated:
                    from esolangs._isolated import termination_isolated

                    answer = termination_isolated(
                        name, source, stdin, cast("float", bound), halts_is, diverges_is
                    )
                else:
                    answer = _terminates(
                        name, source, stdin, bound, halts_is, diverges_is
                    )
                answers.append(answer)
            else:
                runner = esolangs.run
                if scale is not None:
                    runner = partial(runner, scale=scale)
                if isolated:
                    output = runner(
                        name, source, stdin, cast("float", bound), isolated=True
                    )
                else:
                    output = runner(name, source, stdin, bound)
                answers.append(read_answer(name, output))
        except EsolangError as exc:
            # The row and its bits as a note (the classes share no
            # constructor); a 1024-row failure otherwise names no row.
            exc.add_note(
                f"while evaluating row {row} of {rows} "
                f"(inputs {''.join(str(b) for b in bits)}), after "
                f"{len(answers)} row{'' if len(answers) == 1 else 's'} "
                f"answered {''.join(answers) or '(none)'}"
            )
            raise
    return "".join(answers)


def _terminates(
    name: str,
    source: str,
    stdin: str,
    bound: float | None,
    halts: str,
    diverges: str,
) -> str:
    """Return this row's answer for a language that answers by terminating.

    Repeated snapshots prove divergence; a growing state needs the deadline.
    """
    from esolangs.vm import run_until_halt_or_cycle

    # A box, because ``_run`` exists to apply the timeout and discards what
    # it drove -- which is right for ``run``, whose result is the io buffer.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        machine = make_vm(name, source, stdin)
        verdict.append(run_until_halt_or_cycle(machine))

    esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    return halts if verdict and verdict[0] else diverges
