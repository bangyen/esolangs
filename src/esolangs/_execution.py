"""Shared interpreter call preparation and public exception translation."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any

from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InterpreterLimitError,
    ProgramError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import Seeded
from esolangs.raster import Raster
from esolangs.registry import INTERPRETERS, LANGUAGES


def interpreter_module(name: str) -> ModuleType:
    """Return the canonical language's interpreter module."""
    return importlib.import_module(INTERPRETERS[name])


def prepare_call(
    name: str,
    program: str | Raster,
    target: Callable[..., Any],
    *,
    scale: int | None = None,
    seed: int | None = None,
    reproducible: bool = False,
) -> tuple[str | list[str] | Raster, dict[str, Any]]:
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
        raise ArgumentError(
            f"{name} draws no random values, so a seed has nothing to fix; "
            "the languages that draw are Befunge, Fish, LaserFuck, "
            "Modulous, Painfuck, Super SNUSP, Thue and thisthat"
        )
    if draws and (seed is not None or reproducible):
        try:
            options["rng"] = Seeded(
                seed if seed is not None else getattr(target, "reproducible_seed", 0)
            )
        except (TypeError, ValueError) as exc:
            raise ArgumentError(str(exc)) from exc
    return code, options


@contextmanager
def interpreter_errors(
    recursion_message: str, io_obj: ScriptedIO | None = None
) -> Iterator[None]:
    """Translate interpreter failures, preserving public errors and prior output."""
    try:
        yield
    except (RecursionError, EsolangError, ValueError) as original:
        error: EsolangError
        if isinstance(original, RecursionError):
            error = InterpreterLimitError(recursion_message)
        elif isinstance(original, EsolangError):
            error = original
        else:
            error = ProgramError(str(original))
        if io_obj is not None and (written := io_obj.getvalue()):
            error.partial_output = written
            error.add_note(f"the program printed {written[:200]!r} before this")
        if error is original:
            raise
        raise error from original
