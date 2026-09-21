"""The round trip: :func:`evaluate` and :func:`verify`.

``esolangs.run`` is reached through the package at call time (patchable).
"""

import esolangs
from esolangs._answers import (
    _validate_shape_for_evaluate,
    encode_inputs,
    read_answer,
)
from esolangs._describe import describe
from esolangs._validate import check_timeout
from esolangs.exceptions import (
    EsolangError,
    ExecutionTimeoutError,
    InputExhaustedError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Raster
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
    truth_table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
) -> str:
    """Return the truth table a generated ``language`` program *actually* computes.

    Generates, runs every row, returns the answers as a binary string;
    :func:`verify` is this with the comparison done.  ``timeout`` bounds each
    row: omit for the defaults, ``None`` for unbounded (callable off the main
    thread).  The four termination-answer languages do not pay it: those rows are
    settled by a repeated machine state, so the bound is only a backstop
    for growth.
    ``width`` is passed through.  A failure carries the row as a note and
    ``partial_output``.
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
    inputs = _validate_shape_for_evaluate(truth_table)
    terminating = facts["answer_mode"] == "termination"
    bound: float | None
    if isinstance(timeout, _Default):
        bound = _TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT
    else:
        # ``None`` is unbounded, as in :func:`run`, and the thread escape
        # hatch (the guard is ``SIGALRM``).  Safe: every program here is
        # generated, and the divergers are settled by a repeated state.
        bound = timeout
    # The width goes to whichever call builds the runnable text: for a
    # template that is ``instantiate`` below, which keeps every input's
    # run whole where a break inside one would destroy it.
    program = esolangs.generate(
        name, truth_table, None if facts["parameterized"] else width
    )
    if terminating:
        # Which of halting and diverging means 1, as data.  It is
        # ``("halts", "diverges")`` for all four, but reading the order
        # rather than assuming it is what keeps this branch language-free.
        encoding = list(facts["answer_encoding"])
        diverges_is = str(encoding.index("diverges"))
        halts_is = str(encoding.index("halts"))
    answers = []
    for row in range(len(truth_table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        source: str | Raster
        if facts["parameterized"]:
            if isinstance(program, Raster):  # pragma: no cover - impossible metadata
                raise TypeError("a raster generator cannot be parameterized")
            source, stdin = esolangs.instantiate(name, program, bits, width), ""
        else:
            source, stdin = program, encode_inputs(name, bits, truth_table)
        try:
            if terminating:
                if not isinstance(source, str):  # raster languages answer by output
                    raise TypeError("a raster language cannot answer by termination")
                answers.append(
                    _terminates(name, source, stdin, bound, halts_is, diverges_is)
                )
            else:
                output = esolangs.run(name, source, stdin, bound)
                answers.append(read_answer(name, output))
        except EsolangError as exc:
            # The row and its bits as a note (the classes share no
            # constructor); a 1024-row failure otherwise names no row.
            exc.add_note(
                f"while evaluating row {row} of {len(truth_table)} "
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

    A repeated snapshot proves the loop in milliseconds (these programs
    revisit a state within a hundred steps) where waiting cost five seconds
    per 1-row.  The clock stays for growth, which never repeats.  A step
    budget was rightly refused earlier; a repeated state is a fact, not a guess.
    """
    from esolangs.vm import run_until_halt_or_cycle

    machine = make_vm(name, source, stdin)
    # A box, because ``_run`` exists to apply the timeout and discards what
    # it drove -- which is right for ``run``, whose result is the io buffer.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        verdict.append(run_until_halt_or_cycle(machine))

    try:
        esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    except ExecutionTimeoutError:  # pragma: no cover - see below
        # No cycle inside the bound: unbounded growth or slow.  Unreached
        # by the suite (every program repeats within ~100 steps); kept
        # because the detector proves only cycles.
        return diverges
    except InputExhaustedError:  # pragma: no cover - see below
        # Reading past the end is a halt.  Unreachable via :func:`evaluate`
        # (it never underfeeds); kept for a caller passing its own stdin.
        return halts
    return halts if verdict and verdict[0] else diverges


def verify(
    language: str,
    truth_table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
) -> bool:
    """Whether a generated ``language`` program really computes ``truth_table``.

    Use :func:`evaluate` to see which rows disagree.
    """
    return evaluate(language, truth_table, timeout, width) == truth_table
