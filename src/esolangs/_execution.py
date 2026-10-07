"""Shared interpreter call preparation and public exception translation."""

from __future__ import annotations

import importlib
import inspect
import shlex
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any

from esolangs._program import Program, RunnerProgram
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InterpreterLimitError,
    ProgramError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import Seeded
from esolangs.interpreters.source_hints import with_hint
from esolangs.registry import INTERPRETERS, LANGUAGES


def check_signal_timeout(timeout: float | None, message: str) -> None:
    """Refuse a signal deadline outside a Unix main thread."""
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        raise ArgumentError(message)


def interpreter_module(name: str) -> ModuleType:
    """Return the canonical language's interpreter module."""
    return importlib.import_module(INTERPRETERS[name])


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
        raise with_hint(
            ArgumentError(
                f"{name} draws no random values, so a seed has nothing to fix; "
                "the languages that draw are Befunge, Fish, INTERCAL, "
                "LaserFuck, Modulous, Painfuck, Super SNUSP, Thue and thisthat"
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
    except (RecursionError, MemoryError, EsolangError, ValueError) as original:
        error: EsolangError
        if isinstance(original, RecursionError):
            error = InterpreterLimitError(
                recursion_message, hint="reduce expression nesting or recursion depth"
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
            message = str(original)
            if message.startswith("invalid literal for int()"):
                base = message.partition("with base ")[2].partition(":")[0]
                hint = (
                    "use a decimal integer for the numeric operand or input"
                    if base == "10"
                    else f"use a base-{base} integer for the numeric operand or input"
                )
            elif message.startswith("could not convert string to float"):
                hint = "use a decimal number for the numeric operand or input"
            elif message.startswith("chr() arg not in range"):
                hint = "keep character output values between 0 and 1114111"
            elif message.startswith("bytes must be in range"):
                hint = "keep byte values between 0 and 255"
            elif message.startswith("Exceeds the limit ("):
                hint = (
                    "shorten the decimal literal or set PYTHONINTMAXSTRDIGITS "
                    "to a larger limit"
                )
            elif language is not None:
                hint = (
                    "check the language syntax with esolangs describe --spec "
                    f"{shlex.quote(language)}"
                )
            else:
                hint = "check the operands and input against the language's syntax"
            error.add_note(f"hint: {hint}")
        if io_obj is not None and (written := io_obj.getvalue()):
            error.partial_output = written
            error.add_note(f"the program printed {written[:200]!r} before this")
        if error is original:
            raise
        raise error from original
