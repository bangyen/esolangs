"""Shared interpreter call preparation and public exception translation."""

from __future__ import annotations

import importlib
import inspect
import re
import shlex
import signal
import threading
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
from esolangs.registry import INTERPRETERS, LANGUAGES
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import Seeded
from esolangs.runtime.source_hints import with_hint


def check_signal_timeout(timeout: float | None, message: str) -> None:
    """Refuse a signal deadline outside a Unix main thread."""
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        raise ArgumentError(message)


def run_under_alarm(
    run_fn: Callable[..., Any],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float,
) -> None:
    """Run ``run_fn`` under a ``SIGALRM`` wall-clock guard (main thread only)."""
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
        run_fn(program, io_obj)
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


def interpreter_module(name: str) -> ModuleType:
    """Return the canonical language's interpreter module."""
    return importlib.import_module(INTERPRETERS[name])


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


def prepare_call(
    name: str,
    program: Program,
    target: Callable[..., Any],
    *,
    scale: int | None = None,
    seed: int | None = None,
    reproducible: bool = False,
) -> tuple[RunnerProgram, dict[str, Any]]:
    """Prepare source shape and options for a runner or machine constructor."""
    code = (
        program.splitlines()
        if LANGUAGES[name].split and isinstance(program, str)
        else program
    )
    options: dict[str, Any] = {}
    if scale is not None:
        options["scale"] = scale
    draws = "rng" in inspect.signature(target).parameters
    if seed is not None and not draws:
        random_languages = ", ".join(
            language for language, lang in sorted(LANGUAGES.items()) if lang.random
        )
        alternatives = (
            f"the languages that draw are {random_languages}"
            if random_languages
            else "no registered language draws random values"
        )
        raise with_hint(
            ArgumentError(
                f"{name} draws no random values, so a seed has nothing to fix; "
                f"{alternatives}"
            ),
            ("omit seed when running a deterministic language"),
        )
    if draws and (seed is not None or reproducible):
        try:
            options["rng"] = Seeded(
                seed if seed is not None else getattr(target, "reproducible_seed", 0)
            )
        except (TypeError, ValueError) as exc:
            raise with_hint(
                ArgumentError(str(exc)),
                ("use a supported seed value, for example the integer seed=0"),
            ) from exc
    return code, options


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
        elif _hit_digit_cap(original):
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
        if isinstance(original, ValueError) and not any(
            note.startswith("hint:") for note in getattr(error, "__notes__", ())
        ):
            hint = _value_error_hint(str(original), language)
            error.add_note(f"hint: {hint}")
        if io_obj is not None and (written := io_obj.getvalue()):
            error.partial_output = written
            error.add_note(f"the program printed {written[:200]!r} before this")
        if error is original:
            raise
        raise error from original
