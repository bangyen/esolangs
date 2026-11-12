"""Private Boolean evaluation harness for supplied programs.

This machinery certifies generators and exercises interpreters in tests.
It is deliberately not exported as public API.  ``esolangs.run`` is reached
through the package at call time (patchable).
"""

import signal
import threading
from collections.abc import Callable, Iterator
from functools import partial
from threading import Thread
from time import monotonic
from typing import Protocol, cast

import esolangs
import esolangs.operations.source as _source_operations
from esolangs.artifacts import Artifact, TemplateArtifact
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    InterpreterLimitError,
    TemplateError,
)
from esolangs.operations.boolean_io import (
    encode_inputs,
    read_answer,
)
from esolangs.registry import LANGUAGES, resolve
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._prepared import PreparedProgram, prepare_program
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource, check_scale_for
from esolangs.runtime._validate import check_timeout, check_whole
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from tests.support.execution import TIMEOUT_FLOOR, run_guard, termination_observed


class _Default:
    """The "argument was not given" marker for :func:`_evaluate`.

    ``None`` already means *unbounded* in :func:`run`, and meaning "default"
    here too left no value that turned the alarm off from a thread.
    """

    def __repr__(self) -> str:
        """Render as ``<default>`` in a signature rather than as an address."""
        return "<default>"


_DEFAULT = _Default()


def check_signal_timeout(timeout: float | None, message: str) -> None:
    """Refuse a signal deadline outside a Unix main thread."""
    # Only this harness still times rows with ``run_guard``; public ``run``
    # sends every timeout to a worker.
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        raise ArgumentError(message)


#: A termination-answering language proves a 1 by *not* halting, so
#:  :func:`_evaluate` pays this once for every such row.  Four languages
#: carry that convention, so the floor is real and small.
_TERMINATION_TIMEOUT = 5.0

#: The bound on an ordinary row.  Generous: it exists to stop a hang, not
#: to hold anything to a schedule.
_ROW_TIMEOUT = 30.0
_DEFAULT_MAX_ROWS = 1_048_576


#: The widest row this harness evaluates.
MOST_INPUTS = 64


def _remaining(deadline: float | None, bound: float | None) -> float | None:
    """Clamp a row bound to the remaining total deadline."""
    if deadline is None:
        return bound
    remaining = deadline - monotonic()
    if remaining < TIMEOUT_FLOOR:
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
        run_guard(capture, "", ScriptedIO(""), bound)
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


def _iter_evaluate(
    language: str,
    program: ProgramSource,
    timeout: float | _Default | None = _DEFAULT,
    *,
    inputs: int,
    isolated: bool = False,
    scale: int | None = None,
    max_rows: int | None = _DEFAULT_MAX_ROWS,
    max_output: int | None = None,
    max_memory: int | None = None,
    total_timeout: float | None = None,
    settings: DialectSettings | None = None,
) -> Iterator[str]:
    """Yield answer bits in MSB-first row order without retaining the table.

    Validation and source loading begin on first iteration. ``max_rows`` bounds
    the full table (None opts out); ``total_timeout`` includes loading and pauses
    between yields. Row timeouts default to 30 seconds, 5 for termination.
    A timeout never proves divergence. Paths load once; templates fill per row.
    ``max_output`` caps each isolated row in Unicode characters.
    ``max_memory`` caps Linux worker virtual address space in bytes.
    Retained dialect choices apply to filling and execution; explicit ``settings``
    overrides individual choices.
    """
    check_limits(max_output, max_memory, isolated=isolated)
    settings = effective_settings(language, program, settings)
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
    parameterized = LANGUAGES[name].parameterized
    check_scale_for(name, scale)
    rows = _evaluation_rows(inputs, max_rows)
    terminating = LANGUAGES[name].contract.answer_mode == "termination"
    if terminating and scale is not None:
        # Scale upscales raster output; a termination answer (halts vs
        # diverges) has no raster to upscale.  No current termination
        # language declares supports_scale, so check_scale_for already
        # rejects this -- this guards a future raster language that
        # answers by termination, where scale would otherwise be
        # silently dropped on the termination path below.
        raise ArgumentError("scale has no meaning for termination-mode evaluation")
    bound = _row_timeout(
        timeout, terminating=terminating, isolated=isolated, total=total_timeout
    )
    deadline = None if total_timeout is None else started + total_timeout
    program = _prepare(
        lambda: _source_operations.read_artifact(name, program),
        deadline,
        isolated=isolated,
    )
    settings = effective_settings(name, program, settings)
    if parameterized and not isinstance(program, TemplateArtifact):
        raise TemplateError(
            "evaluation needs a TemplateArtifact with explicit bindings"
        )
    answer_row = _row_answerer(
        name,
        terminating=terminating,
        isolated=isolated,
        settings=settings,
        scale=scale,
        max_output=max_output,
        max_memory=max_memory,
    )
    instantiator = esolangs.instantiate
    if settings is not None:
        instantiator = partial(instantiator, settings=settings)
    prepared: PreparedProgram | None = None
    for row in range(rows):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]

        def prepare_row(bits: list[int] = bits) -> tuple[Program | Artifact, str]:
            if parameterized:
                assert isinstance(program, TemplateArtifact)
                return instantiator(name, program, bits), ""
            # A language with no generator reads no stdin at all.
            return program, (
                encode_inputs(name, bits) if LANGUAGES[name].backend is not None else ""
            )

        try:
            source, stdin = _prepare(prepare_row, deadline, isolated=isolated)
            if prepared is None and not (isolated or parameterized):
                prepared = _prepare(
                    partial(
                        prepare_program,
                        name,
                        source,
                        settings=settings,
                        scale=scale,
                        bind_machine=True,
                    ),
                    deadline,
                    isolated=False,
                )
            answer = answer_row(source, stdin, _remaining(deadline, bound), prepared)
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


def _row_timeout(
    timeout: float | _Default | None,
    *,
    terminating: bool,
    isolated: bool,
    total: float | None,
) -> float | None:
    """Return each row's own time bound; refuse one no guard can enforce."""
    bound: float | None
    if isinstance(timeout, _Default):
        bound = _TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT
    else:
        # ``None`` is unbounded, as in :func:`run`, and the thread escape
        # hatch (the guard is ``SIGALRM``).
        bound = timeout
    if isolated and bound is None and total is None:
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
            bound if total is None else total,
            "evaluation's timeout guard uses SIGALRM and needs a Unix main "
            "thread; off it, pass timeout=None -- a diverging row is "
            "settled by a repeated machine state rather than waited for",
        )
    return bound


class _RowAnswerer(Protocol):
    def __call__(
        self,
        source: Program | Artifact,
        stdin: str,
        bound: float | None,
        prepared: PreparedProgram | None = None,
        /,
    ) -> str: ...


def _row_answerer(
    name: str,
    *,
    terminating: bool,
    isolated: bool,
    settings: DialectSettings | None,
    scale: int | None,
    max_output: int | None,
    max_memory: int | None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
) -> _RowAnswerer:
    """Return the call that turns one row's source, stdin and bound into its bit."""
    if not terminating:
        from tests.support.execution import run_observed

        run = (
            esolangs.run
            if io_factory is ScriptedIO
            else partial(run_observed, io_factory=io_factory)
        )

        def output_answer(
            source: Program | Artifact,
            stdin: str,
            bound: float | None,
            prepared: PreparedProgram | None = None,
        ) -> str:
            if prepared is None:

                def call(*_args: object) -> ExecutionResult:
                    return run(
                        name,
                        source,
                        stdin=stdin,
                        timeout=bound if isolated else None,
                        isolated=isolated,
                        scale=scale,
                        max_output=max_output,
                        max_memory=max_memory,
                        settings=settings,
                    )

                result = (
                    call() if isolated else run_guard(call, "", ScriptedIO(""), bound)
                )
            else:
                result = run_observed(
                    name,
                    source,
                    stdin=stdin,
                    timeout=bound,
                    prepared=prepared,
                    io_factory=io_factory,
                    max_output=max_output,
                    max_memory=max_memory,
                )
            return read_answer(name, result.output)

        return output_answer
    # Derive each bit from its declared halt/diverge order.
    values = LANGUAGES[name].contract.answer_values
    diverges_is = str(values.index("diverges"))
    halts_is = str(values.index("halts"))

    def answer(
        source: Program | Artifact,
        stdin: str,
        bound: float | None,
        prepared: PreparedProgram | None = None,
    ) -> str:
        if isolated:
            from esolangs.runtime._isolated import termination_result_isolated

            proof = termination_result_isolated(
                name,
                _source_operations._check_program(name, source, stdin).source,
                stdin,
                cast("float", bound),
                settings=settings,
                max_output=max_output,
                max_memory=max_memory,
            )
        else:
            proof = termination_observed(
                name,
                source,
                stdin,
                bound,
                settings=settings,
                io_factory=io_factory,
                prepared=prepared,
            )
        return halts_is if proof.decision.halts else diverges_is

    return answer


def _evaluate(
    language: str,
    program: ProgramSource,
    timeout: float | _Default | None = _DEFAULT,
    *,
    inputs: int,
    isolated: bool = False,
    scale: int | None = None,
    max_rows: int | None = _DEFAULT_MAX_ROWS,
    max_output: int | None = None,
    max_memory: int | None = None,
    total_timeout: float | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Return the table computed over ``inputs`` bits, collecting ``_iter_evaluate``.

    Repeated states prove divergence; a timeout raises rather than counting as 1.
    Row timeouts default to 30 seconds (5 for termination). ``max_rows`` defaults
    to 1,048,576; None opts out. ``total_timeout`` optionally bounds the whole run.
    ``max_output`` caps each isolated row in Unicode characters.
    ``max_memory`` caps Linux worker virtual address space in bytes.
    """
    answers = []
    # Collected incrementally, not list(...): when a row raises, the
    # except below quotes the partial answers in the error's note.
    try:
        for answer in _iter_evaluate(
            language,
            program,
            timeout,
            inputs=inputs,
            isolated=isolated,
            scale=scale,
            max_rows=max_rows,
            max_output=max_output,
            max_memory=max_memory,
            total_timeout=total_timeout,
            settings=settings,
        ):
            answers.append(answer)  # noqa: PERF402
    except EsolangError as exc:
        exc.add_note(f"answered {''.join(answers) or '(none)'}")
        raise
    return "".join(answers)
