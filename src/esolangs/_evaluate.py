"""Evaluate a supplied program on every Boolean input row.

``esolangs.run`` is reached through the package at call time (patchable).
"""

from collections.abc import Callable, Iterator
from functools import partial
from threading import Thread
from time import monotonic
from typing import cast

import esolangs
from esolangs._answers import (
    encode_inputs,
    read_answer,
)
from esolangs._execution import check_signal_timeout
from esolangs._program import Program
from esolangs._source import ProgramSource, check_scale_for
from esolangs._validate import _TIMEOUT_FLOOR, check_timeout, check_whole
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    InterpreterLimitError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.source_hints import with_hint
from esolangs.registry import LANGUAGES, resolve
from esolangs.settings import DialectSettings, dialect_options
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
_DEFAULT_MAX_ROWS = 1_048_576


def _remaining(deadline: float | None, bound: float | None) -> float | None:
    """Clamp a row bound to the remaining total deadline."""
    if deadline is None:
        return bound
    remaining = deadline - monotonic()
    if remaining < _TIMEOUT_FLOOR:
        raise ExecutionTimeoutError("evaluation exceeded its total deadline")
    return remaining if bound is None else min(bound, remaining)


def _prepare[T](call: Callable[[], T], deadline: float | None, *, isolated: bool) -> T:
    """Bound acquisition; an isolated caller's blocked stream may finish later."""
    if deadline is None:
        return call()
    values: list[T] = []
    errors: list[BaseException] = []

    def capture(*_args: object) -> None:
        try:
            values.append(call())
        except BaseException as exc:
            errors.append(exc)

    bound = _remaining(deadline, None)
    if isolated:
        reader = Thread(target=capture, daemon=True)
        reader.start()
        reader.join(bound)
        if reader.is_alive():
            raise ExecutionTimeoutError("evaluation timed out during preparation")
    else:
        esolangs._run(capture, "", ScriptedIO(""), bound)  # noqa: SLF001
    _remaining(deadline, None)
    if errors:
        raise errors[0]
    return values[0]


def _evaluation_rows(inputs: int, max_rows: int | None) -> int:
    """Validate an evaluation's input count and row budget before acquisition."""
    if max_rows is not None:
        check_whole(max_rows, "max_rows")
    if (
        isinstance(inputs, bool)
        or not isinstance(inputs, int)
        or not 1 <= inputs <= MOST_INPUTS
    ):
        raise with_hint(
            ArgumentError(f"inputs must be an integer from 1 to {MOST_INPUTS}"),
            (
                "choose the program input count; inputs=2 is "
                "valid for a two-input program"
            ),
        )
    rows = 1 << inputs
    if max_rows is not None and rows > max_rows:
        raise with_hint(
            InterpreterLimitError(
                f"evaluation needs {rows} rows, exceeding max_rows={max_rows}"
            ),
            "raise max_rows deliberately or use fewer inputs",
        )
    return rows


def iter_evaluate(
    language: str,
    program: ProgramSource,
    timeout: float | _Default | None = _DEFAULT,
    *,
    inputs: int,
    isolated: bool = False,
    scale: int | None = None,
    max_rows: int | None = _DEFAULT_MAX_ROWS,
    total_timeout: float | None = None,
    settings: DialectSettings | None = None,
) -> Iterator[str]:
    """Yield answer bits in MSB-first row order without retaining the table.

    Validation and source loading begin on first iteration. ``max_rows`` bounds
    the full table (None opts out); ``total_timeout`` includes loading and pauses
    between yields. Row timeouts default to 30 seconds, 5 for termination.
    A timeout never proves divergence. Paths load once; templates fill per row.
    ``settings`` applies to template filling and every execution path.
    """
    dialect_options(language, settings)
    started = monotonic()
    check_timeout(total_timeout)
    # Checked here, not only inside ``run``: the termination path drives the
    # machine itself and never reaches ``run``, so a bound too small to
    # service was refused for the languages that halt and silently read as
    # "diverges" for the termination-answer ones -- the same argument
    # answering a different table depending on which kind of language it was.
    if not isinstance(timeout, _Default):
        check_timeout(timeout)
    name = resolve(language)
    contract = LANGUAGES[name].contract
    check_scale_for(name, scale)
    rows = _evaluation_rows(inputs, max_rows)
    terminating = contract.answer_mode == "termination"
    bound: float | None
    if isinstance(timeout, _Default):
        bound = _TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT
    else:
        # ``None`` is unbounded, as in :func:`run`, and the thread escape
        # hatch (the guard is ``SIGALRM``).
        bound = timeout
    if isolated and bound is None and total_timeout is None:
        raise with_hint(
            ArgumentError("isolated evaluation requires a finite timeout"),
            ("set a positive finite timeout, for example timeout=5.0"),
        )
    if not isolated:
        # The termination path drives ``_run`` directly and so never reached
        # ``run``'s guard: off a main thread it leaked ``signal.signal``'s
        # bare ValueError.  ``timeout=None`` is the route out, as for
        # :func:`run`; the divergers are settled by a repeated state.
        check_signal_timeout(
            bound if total_timeout is None else total_timeout,
            "evaluate's timeout guard uses SIGALRM and needs a Unix main "
            "thread; off it, pass timeout=None -- a diverging row is "
            "settled by a repeated machine state rather than waited for",
        )
    deadline = None if total_timeout is None else started + total_timeout
    program = _prepare(
        lambda: esolangs._read_source(name, program),  # noqa: SLF001
        deadline,
        isolated=isolated,
    )
    if terminating:
        # Which of halting and diverging means 1, as data.  It is
        # ``("halts", "diverges")`` for all four, but reading the order
        # rather than assuming it is what keeps this branch language-free.
        encoding = list(contract.answer_values)
        diverges_is = str(encoding.index("diverges"))
        halts_is = str(encoding.index("halts"))
    instantiator = esolangs.instantiate
    if settings is not None:
        instantiator = partial(instantiator, settings=settings)
    for row in range(rows):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]

        def prepare_row(bits: list[int] = bits) -> tuple[Program, str]:
            if contract.parameterized:
                return instantiator(name, cast("str", program), bits), ""
            return program, encode_inputs(name, bits)

        try:
            source, stdin = _prepare(prepare_row, deadline, isolated=isolated)
            row_bound = _remaining(deadline, bound)
            if terminating:
                source = cast("str", source)
                if isolated:
                    from esolangs._isolated import termination_isolated

                    termination_runner = termination_isolated
                    if settings is not None:
                        termination_runner = partial(
                            termination_runner, settings=settings
                        )
                    answer = termination_runner(
                        name,
                        source,
                        stdin,
                        cast("float", row_bound),
                        halts_is,
                        diverges_is,
                    )
                else:
                    terminator = _terminates
                    if settings is not None:
                        terminator = partial(terminator, settings=settings)
                    answer = terminator(
                        name, source, stdin, row_bound, halts_is, diverges_is
                    )
            else:
                runner = esolangs.run
                if settings is not None:
                    runner = partial(runner, settings=settings)
                if scale is not None:
                    runner = partial(runner, scale=scale)
                if isolated:
                    output = runner(
                        name, source, stdin, cast("float", row_bound), isolated=True
                    )
                else:
                    output = runner(name, source, stdin, row_bound)
                answer = read_answer(name, output)
            if deadline is not None and monotonic() >= deadline:
                raise ExecutionTimeoutError("evaluation exceeded its total deadline")
        except EsolangError as exc:
            # The row and its bits as a note (the classes share no
            # constructor); a 1024-row failure otherwise names no row.
            exc.add_note(
                f"while evaluating row {row} of {rows} "
                f"(inputs {''.join(str(b) for b in bits)}), after "
                f"{row} row{'' if row == 1 else 's'} completed"
            )
            raise
        yield answer


def evaluate(
    language: str,
    program: ProgramSource,
    timeout: float | _Default | None = _DEFAULT,
    *,
    inputs: int,
    isolated: bool = False,
    scale: int | None = None,
    max_rows: int | None = _DEFAULT_MAX_ROWS,
    total_timeout: float | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Return the table computed over ``inputs`` bits, collecting iter_evaluate.

    Repeated states prove divergence; a timeout raises rather than counting as 1.
    Row timeouts default to 30 seconds (5 for termination). ``max_rows`` defaults
    to 1,048,576; None opts out. ``total_timeout`` optionally bounds the whole run.
    """
    answers = []
    try:
        for answer in iter_evaluate(
            language,
            program,
            timeout,
            inputs=inputs,
            isolated=isolated,
            scale=scale,
            max_rows=max_rows,
            total_timeout=total_timeout,
            settings=settings,
        ):
            answers.append(answer)
    except EsolangError as exc:
        exc.add_note(f"answered {''.join(answers) or '(none)'}")
        raise
    return "".join(answers)


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
    from esolangs.vm import run_until_halt_or_cycle

    dialect_options(name, settings)

    # A box, because ``_run`` exists to apply the timeout and discards what
    # it drove -- which is right for ``run``, whose result is the io buffer.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        factory = make_vm if settings is None else partial(make_vm, settings=settings)
        machine = factory(name, source, stdin)
        verdict.append(run_until_halt_or_cycle(machine))

    esolangs._run(_drive, source, ScriptedIO(""), bound)  # noqa: SLF001
    return halts if verdict and verdict[0] else diverges
