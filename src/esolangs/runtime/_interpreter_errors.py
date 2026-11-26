"""Public exception translation and failure observations for interpreters."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from esolangs.exceptions import EsolangError, InterpreterLimitError, ProgramError
from esolangs.outcomes import _remember_failure_evidence
from esolangs.results import ExecutionResult
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.memory import _hit_digit_cap
from esolangs.runtime.source_hints import shell_argument, syntax_repair

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
    return syntax_repair(shell_argument(language) if language is not None else None)


@contextmanager
def interpreter_errors(
    recursion_message: str,
    io_obj: ScriptedIO | None = None,
    *,
    language: str | None = None,
    input_acquired: bool = False,
    on_observation: Callable[[ExecutionResult], None] | None = None,
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
            error.observation = original.observation
        if isinstance(original, ValueError) and not any(
            note.startswith("hint:") for note in getattr(error, "__notes__", ())
        ):
            hint = _value_error_hint(str(original), language)
            error.add_note(f"hint: {hint}")
        if io_obj is not None:
            written = io_obj.getvalue()
            counters = io_obj.position(), io_obj.reads, io_obj.past_end
            observation = ExecutionResult(written, *counters)
            if error.observation is not None:
                _remember_failure_evidence(error, observation)
            else:
                error.observation = observation
                error.partial_output = written
                if on_observation is not None:
                    on_observation(observation)
                if written:
                    error.add_note(f"the program printed {written[:200]!r} before this")
        elif input_acquired and error.observation is None:
            error.observation = ExecutionResult(error.partial_output, 0, 0, 0)
        if error is original:
            raise
        raise error from original
