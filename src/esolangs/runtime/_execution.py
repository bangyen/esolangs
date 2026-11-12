"""Shared interpreter call preparation and public exception translation."""

from __future__ import annotations

import importlib
import re
import shlex
import signal
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any, cast

from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    InterpreterLimitError,
    ProgramError,
)
from esolangs.outcomes import ExecutionOutcome, _capture_outcome
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import Seeded
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import dialect_options


def run_under_alarm[T](
    run_fn: Callable[..., T],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float,
) -> T:
    """Return the call's result under a ``SIGALRM`` guard (main thread only)."""
    # The handler fires between any two bytecodes, including the cleanup's;
    # raising into its own teardown left the timer armed and the default
    # SIGALRM disposition killed one run in three.  Clearing this is one store.
    armed = True
    old = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    pending, interval = signal.getitimer(signal.ITIMER_REAL)
    caller_deadline = started + pending if pending else None
    deadline = started + timeout

    def _timeout_handler(_signum: int, _frame: object) -> None:
        nonlocal caller_deadline
        # coverage cannot trace a raise inside a signal handler
        if not armed:  # pragma: no cover - a late alarm, not an overrun
            return
        now = time.monotonic()
        if caller_deadline is not None and now >= caller_deadline:
            caller_deadline = (
                caller_deadline
                + (int((now - caller_deadline) // interval) + 1) * interval
                if interval
                else None
            )
            if callable(old):
                old(_signum, cast("Any", _frame))
            elif old == signal.SIG_DFL:
                signal.signal(signal.SIGALRM, old)
                signal.raise_signal(signal.SIGALRM)
            now = time.monotonic()
            if now < deadline:
                next_deadline = (
                    min(deadline, caller_deadline)
                    if caller_deadline is not None
                    else deadline
                )
                signal.setitimer(
                    signal.ITIMER_REAL, max(0.000001, next_deadline - time.monotonic())
                )
                return
        raise ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    # Dispatch the earlier deadline: replacing a caller's timer let a nested
    # 0.05-second guard return successfully after 0.159 seconds.
    signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        # Armed inside the ``try``: a 1 ms alarm can fire before it is entered.
        signal.setitimer(
            signal.ITIMER_REAL, min(timeout, pending) if pending else timeout
        )
        return run_fn(program, io_obj)
    finally:
        armed = False
        # Ignore first, then disarm, then restore: an alarm in flight after
        # ``old`` (the default disposition) is restored terminates the
        # process -- exit 142, one run in ten.  ``SIG_IGN`` is C-level.
        # An alarm between ``run_fn`` returning and here still raises a
        # timeout; closing that needs a flag read from a handler, not worth it.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        if caller_deadline is not None:
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.000001, caller_deadline - time.monotonic()),
                interval,
            )


def interpreter_module(name: str, *, catalog: Catalog | None = None) -> ModuleType:
    """Return the canonical language's interpreter module."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return importlib.import_module(catalog.interpreters[name])


@_capture_outcome
def execute_prepared(
    name: str,
    run_fn: Callable[..., Any],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float | None,
    *,
    catalog: Catalog | None = None,
) -> ExecutionOutcome:
    """Execute prepared source and retain output, input usage and declared reports."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    with interpreter_errors(
        f"the {name} interpreter recursed deeper than CPython's stack "
        "limit allows on this program; the program is well formed, and "
        "sys.setrecursionlimit can raise the limit if this interpreter's "
        "depth grows with program size",
        io_obj,
        language=name,
    ):
        value = run_guard(run_fn, program, io_obj, timeout)
        if not isinstance(value, CompletionReport):
            raise InterpreterLimitError(
                "completion runner returned no completion report",
                hint="check the declared completion entry point",
            )
        capabilities = catalog.languages[name].runtime.capabilities
        if not capabilities.accepts_native(value.kind):
            raise InterpreterLimitError(
                "completion report disagrees with declared policy",
                hint="check the descriptor and native completion runner",
            )
    return ExecutionOutcome(
        "completed",
        ExecutionResult(
            io_obj.getvalue(),
            io_obj.position(),
            io_obj.reads,
            io_obj.past_end,
            value,
        ),
    )


#: CPython's int/str digit-cap ValueError, an implementation limit.  Matched
#: from the start: a parse error echoing source "Exceeds the limit (" is not.
_DIGIT_CAP = re.compile(r"Exceeds the limit \(\d+ digits\) for integer string")


def _hit_digit_cap(error: BaseException | None) -> bool:
    """Whether CPython's digit cap raised ``error`` or anything it chains."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, ValueError) and _DIGIT_CAP.match(str(error)):
            return True
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return False


# Substrings of CPython's ValueError wording, mapped to the hint each
# failure deserves.  The wording is CPython's, not ours, so these match
# loosely on fragments rather than parsing structured data out of the
# message: if CPython rewords one, its hint falls through to the generic
# language-syntax fallback below instead of shipping a wrong hint.
_VALUE_ERROR_HINTS = (
    (
        "could not convert string to float",
        "use a decimal number for the numeric operand or input",
    ),
    (
        "chr() arg not in range",
        "keep character output values between 0 and 1114111",
    ),
    (
        "bytes must be in range",
        "keep byte values between 0 and 255",
    ),
)


def _value_error_hint(message: str, language: str | None) -> str:
    """Pick a hint for a ValueError that escaped a language implementation."""
    if "invalid literal for int()" in message:
        # Dimensional's ``x`` reads base 16; a decimal hint there is wrong.
        base = message.partition("with base ")[2].partition(":")[0]
        radix = {"10": "a decimal"}.get(base, f"a base-{base}" if base else "an")
        return f"use {radix} integer for the numeric operand or input"
    for fragment, hint in _VALUE_ERROR_HINTS:
        if fragment in message:
            return hint
    if language is not None:
        return (
            "check the language syntax with esolangs describe --spec "
            f"{shlex.quote(language)}"
        )
    return "check the operands and input against the language's syntax"


def _seed_refusal(name: str, *, catalog: Catalog | None = None) -> ArgumentError:
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    random_languages = ", ".join(
        language
        for language, lang in sorted(catalog.languages.items())
        if lang.runtime.random
    )
    alternatives = (
        f"the languages that draw are {random_languages}"
        if random_languages
        else "no registered language draws random values"
    )
    return with_hint(
        ArgumentError(
            f"{name} draws no random values, so a seed has nothing to fix; "
            f"{alternatives}"
        ),
        ("omit seed when running a deterministic language"),
    )


def check_seed_for(
    name: str, seed: int | None, *, catalog: Catalog | None = None
) -> None:
    """Refuse a seed for a language that draws nothing, before any input."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if seed is not None and not catalog.languages[name].runtime.random:
        raise _seed_refusal(name, catalog=catalog)


def prepare_call(
    name: str,
    program: Program,
    context: ExecutionContext,
    *,
    catalog: Catalog | None = None,
) -> tuple[RunnerProgram, dict[str, Any]]:
    """Prepare source shape and options for a runner or machine constructor."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    code = (
        program.splitlines()
        if catalog.languages[name].runtime.split and isinstance(program, str)
        else program
    )
    return code, execution_options(name, context, catalog=catalog)


def execution_options(
    name: str, context: ExecutionContext, *, catalog: Catalog | None = None
) -> dict[str, Any]:
    """Bind invocation choices and fresh RNG state without reshaping source."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    options: dict[str, Any] = {}
    if context.scale is not None:
        options["scale"] = context.scale
    runtime = catalog.languages[name].runtime
    if context.seed is not None and not runtime.random:
        raise _seed_refusal(name, catalog=catalog)
    if runtime.random and (context.seed is not None or context.reproducible):
        try:
            options["rng"] = Seeded(
                context.seed if context.seed is not None else runtime.reproducible_seed
            )
        except (TypeError, ValueError) as exc:
            raise with_hint(
                ArgumentError(str(exc)),
                ("use a supported seed value, for example the integer seed=0"),
            ) from exc
    options.update(dialect_options(name, context.settings, catalog=catalog))
    return options


@contextmanager
def interpreter_errors(
    recursion_message: str,
    io_obj: ScriptedIO | None = None,
    *,
    language: str | None = None,
) -> Iterator[None]:
    """Translate interpreter failures, preserving public errors and prior output."""
    try:
        yield
    except (
        RecursionError,
        MemoryError,
        OverflowError,
        EsolangError,
        ValueError,
    ) as original:
        error: EsolangError
        if isinstance(original, RecursionError):
            error = InterpreterLimitError(
                recursion_message, hint="reduce expression nesting or recursion depth"
            )
        elif isinstance(original, OverflowError):
            # A host limit: Fackward's ``$`` repeating past sys.maxsize
            # escaped bare.
            error = InterpreterLimitError(str(original))
        # Nested loading contexts must retain a normalized error's IO observation.
        elif not isinstance(original, InterpreterLimitError) and _hit_digit_cap(
            original
        ):
            # A valid Ascenic PRINT of a 4300-digit number was reported as a
            # load error.
            error = InterpreterLimitError(
                str(original),
                hint="shorten the decimal literal or set PYTHONINTMAXSTRDIGITS "
                "to a larger limit",
            )
        elif isinstance(original, MemoryError):
            # As isolated execution reports a worker that hit max_memory.
            error = InterpreterLimitError(
                "the program ran out of memory",
                hint="run it with isolated=True and max_memory to bound it",
            )
        elif isinstance(original, EsolangError):
            error = original
        else:
            error = ProgramError(str(original))
            for note in getattr(original, "__notes__", ()):
                error.add_note(note)
        if error is not original and isinstance(original, EsolangError):
            error.partial_output = original.partial_output
            error.execution = original.execution
        if isinstance(original, ValueError) and not any(
            note.startswith("hint:") for note in getattr(error, "__notes__", ())
        ):
            hint = _value_error_hint(str(original), language)
            error.add_note(f"hint: {hint}")
        if io_obj is not None:
            written = io_obj.getvalue()
            error.partial_output = written
            error.execution = ExecutionResult(
                written, io_obj.position(), io_obj.reads, io_obj.past_end
            )
            if written:
                error.add_note(f"the program printed {written[:200]!r} before this")
        if error is original:
            raise
        raise error from original


def run_guard[T](
    run_fn: Callable[..., T],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float | None,
) -> T:
    """Return ``run_fn``'s result, applying the wall-clock guard when set."""
    if timeout is None:
        return run_fn(program, io_obj)
    return run_under_alarm(run_fn, program, io_obj, timeout)
