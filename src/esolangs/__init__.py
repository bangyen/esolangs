"""Public API for the esolangs package.

Provides ``generate`` (produce a program that prints a text), ``run``
(execute a program through an interpreter), ``transpile`` (rewrite a
program between languages), ``describe`` (a structured language summary),
and ``list_languages``.
"""

import importlib
import pathlib
import signal
import threading
from collections.abc import Callable
from typing import Any

from esolangs.exceptions import (
    HaltError,
    UnknownLanguageError,
    UnsupportedTranspilationError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import GENERATORS, LANGUAGES, RUNNERS
from esolangs.tools.boolean import BOOLEAN
from esolangs.tools.transpilers import TRANSPILERS

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"

# Interpreter module family -> state model name.
_STATE_MODELS = {
    "register_based": "register",
    "tape_based": "tape",
    "stack_based": "stack",
    "grid_based": "grid",
    "queue_based": "queue",
    "other": "other",
}


def generate(language: str, text: str) -> str:
    """Return a program in ``language`` that prints ``text``."""
    try:
        fn = GENERATORS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    return str(fn(text))


def run(
    language: str,
    program: str,
    stdin: str = "",
    timeout: float | None = None,
) -> str:
    """Execute ``program`` and return its output.

    Input is fed to the program line by line from ``stdin``.  ``timeout``
    bounds execution wall-clock: after ``timeout`` seconds the run raises
    :class:`HaltError`.  The guard uses ``SIGALRM``, so it requires a Unix
    main thread; elsewhere a ``timeout`` raises :class:`ValueError`.
    """
    if timeout is not None and timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    try:
        module, split, kwargs = RUNNERS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    run_fn = importlib.import_module("esolangs.interpreters." + module).run
    io_obj = ScriptedIO(stdin)
    program_args: str | list[str] = program.splitlines() if split else program
    _run(run_fn, program_args, io_obj, timeout, dict(kwargs))
    return io_obj.getvalue()


def _run(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float | None,
    kwargs: dict[str, int],
) -> None:
    """Run ``run_fn``, applying the wall-clock ``timeout`` guard when set."""
    if timeout is None:
        run_fn(program, io_obj, **kwargs)
    elif threading.current_thread() is threading.main_thread() and hasattr(
        signal, "SIGALRM"
    ):
        _run_timed_signal(run_fn, program, io_obj, timeout, kwargs)
    else:
        raise ValueError("the timeout guard uses SIGALRM and needs a Unix main thread")


def _run_timed_signal(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float,
    kwargs: dict[str, int],
) -> None:
    """Run ``run_fn`` under a ``SIGALRM`` wall-clock guard (main thread only)."""

    def _timeout_handler(_signum: int, _frame: object) -> None:
        raise HaltError(f"execution exceeded the {timeout}-second timeout")

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        run_fn(program, io_obj, **kwargs)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def describe(language: str) -> dict[str, object]:
    """Return a structured description of ``language``.

    The summary carries the state model (derived from the interpreter's
    module family), whether the language has text and boolean generators,
    its transpilers, its example programs, and its esolangs.org page.
    """
    try:
        lang = LANGUAGES[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    module = RUNNERS.get(language)
    family = module[0].split(".")[0] if module else None
    examples = sorted(
        str(p.relative_to(_EXAMPLES.parent)) for p in _EXAMPLES.glob(f"*/{lang.id}.txt")
    )
    transpilers = sorted(
        (source, target)
        for (source, target) in TRANSPILERS
        if source == language or target == language
    )
    return {
        "name": language,
        "id": lang.id,
        "state_model": _STATE_MODELS.get(family) if family else None,
        "interpreter": lang.interpreter,
        "text_generator": lang.generator is not None,
        "boolean_generator": language in BOOLEAN,
        "transpilers": transpilers,
        "examples": examples,
        "wiki_url": f"https://esolangs.org/wiki/{language.replace(' ', '_')}",
    }


def transpile(source: str, target: str, program: str, **kwargs: int) -> str:
    """Rewrite a ``program`` in ``source`` into an equivalent one in ``target``.

    Transpilers with extra options accept them as keyword arguments (for
    example ``size`` when targeting Circlefuck).
    """
    try:
        fn = TRANSPILERS[(source, target)]
    except KeyError:
        raise UnsupportedTranspilationError(source, target) from None
    return fn(program, **kwargs)


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
