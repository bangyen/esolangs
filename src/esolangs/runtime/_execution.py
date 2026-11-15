"""Shared interpreter call preparation and public exception translation."""

from __future__ import annotations

import importlib
import shlex
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from types import ModuleType
from typing import Any

from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InterpreterLimitError,
    MissingDependencyError,
    ProgramError,
)
from esolangs.outcomes import (
    ExecutionOutcome,
    _capture_outcome,
    _remember_failure_evidence,
)
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.memory import _hit_digit_cap
from esolangs.runtime.randomness import Seeded
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import dialect_options


def invoke[T](
    run_fn: Callable[..., T], program: RunnerProgram, io_obj: ScriptedIO
) -> T:
    """Call one prepared runner; faults raised here reach public translation."""
    return run_fn(program, io_obj)


def interpreter_module(name: str, *, catalog: Catalog | None = None) -> ModuleType:
    """Return the canonical language's interpreter module."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(name)
    module = catalog._interpreters.get(name)  # noqa: SLF001
    if module is None:
        raise ProgramError(f"{name} has no declared interpreter")
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError as error:
        missing = error.name
        if missing is not None and (
            module == missing or module.startswith(f"{missing}.")
        ):
            raise ProgramError(
                f"{name}'s interpreter module {module!r} is missing"
            ) from error
        raise MissingDependencyError(
            f"{name}'s interpreter could not load {missing!r}"
        ) from error


def runtime_hook(module: ModuleType, language: str, name: str) -> Callable[..., Any]:
    """Resolve a declared entry point when its execution route needs it."""
    target: object = getattr(module, name, None)
    if not callable(target):
        raise ProgramError(f"{language}'s interpreter has no callable {name!r} hook")
    return target


@_capture_outcome
def execute_prepared(
    name: str,
    run_fn: Callable[..., Any],
    program: RunnerProgram,
    io_obj: ScriptedIO,
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
        value = invoke(run_fn, program, io_obj)
        if not _has_backing_type(value, CompletionReport):
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
            completion=value,
        ),
    )


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


def _matches_installed_value(selected: object, installed: object) -> bool:
    """Compare declared worker values without invoking caller equality methods."""
    if selected is installed:
        return True
    if type(selected) is not type(installed):
        return False
    if type(installed) in (str, int, bool):
        return selected == installed
    if type(selected) is tuple and type(installed) is tuple:
        return len(selected) == len(installed) and all(
            _matches_installed_value(value, expected)
            for value, expected in zip(selected, installed, strict=True)
        )
    if type(selected) is frozenset:
        # Native completion sets contain only the installed enum members.
        return (
            all(type(item) is Completion for item in selected) and selected == installed
        )
    if is_dataclass(installed):
        return all(
            _matches_installed_value(
                getattr(selected, field.name), getattr(installed, field.name)
            )
            for field in fields(installed)
        )
    # A distinct callable is unavailable in the worker. FunctionRef values
    # match by their stored declaration fields above.
    return False


def check_worker_runtime(name: str, catalog: Catalog) -> None:
    """Refuse scoped declarations that the fresh worker cannot reproduce."""
    from esolangs.registry._table import LANGUAGES

    default = LANGUAGES.get(name)
    selected = catalog.languages[name]
    if (
        default is None
        or selected.id != default.id
        or not _matches_installed_value(selected.runtime, default.runtime)
    ):
        raise ArgumentError(
            "isolated execution requires a runtime declared in the installed catalog"
        )


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
    input_acquired: bool = False,
    omit_empty_io: bool = False,
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
            if not omit_empty_io or written or any(counters):
                observation = ExecutionResult(written, *counters)
                if error.observation is not None:
                    _remember_failure_evidence(error, observation)
                else:
                    error.observation = observation
                    error.partial_output = written
                    if on_observation is not None:
                        on_observation(observation)
                    if written:
                        error.add_note(
                            f"the program printed {written[:200]!r} before this"
                        )
        elif input_acquired and error.observation is None:
            error.observation = ExecutionResult(error.partial_output, 0, 0, 0)
        if error is original:
            raise
        raise error from original
