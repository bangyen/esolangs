"""Public API for the esolangs package.

Provides ``generate`` (produce a program that prints a text), ``run``
(execute a program through an interpreter), ``make_vm`` (a step-and-inspect
wrapper around the step-capable interpreters), ``make_debugger`` (a
breakpoint/watch layer over the VM), ``transpile`` (rewrite a
program between languages), ``describe`` (a structured language summary),
and ``list_languages``.
"""

import importlib
import pathlib
import signal
import threading
from collections.abc import Callable
from typing import Any

from esolangs.debug import Debugger, make_debugger
from esolangs.exceptions import (
    HaltError,
    UnknownLanguageError,
    UnsupportedTranspilationError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import GENERATORS, LANGUAGES, RUNNERS
from esolangs.tools.transpilers import TRANSPILERS
from esolangs.tools.wrap import takes_width, wrap_program
from esolangs.vm import VM, make_vm

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


def generate(language: str, text: str, width: int | None = None) -> str:
    """Return a program in ``language`` that prints ``text``.

    ``width`` bounds the program to that many columns for readability;
    :data:`esolangs.tools.wrap.DEFAULT_WIDTH` is the conventional choice.
    The default of ``None`` asks for no bound, so a caller that does not
    want one gets exactly what the generator has always produced.

    Most languages honour it by *wrapping* the finished program, breaking
    only between whole tokens so it still means the same thing.  A few build
    a shape rather than a line -- Clockwise weaves its code through a grid
    the turtle walks -- and cannot be reflowed after the fact; those
    generators take the width themselves and lay the program out to fit.

    A language whose newlines are semantic (the 2D grid languages) or that
    rejects them outright (NoComment) ignores ``width`` rather than raising,
    so one width can be passed across every language.

    ``width`` is therefore considered but not guaranteed: every generator
    narrows what it can, and one asked for less than its construction can
    occupy returns its narrowest form rather than raising.  The floor is
    the generator's own -- four columns for Clockwise's weave, but a
    function of the *text* for the generators whose programs grow with it,
    so there is no one width below which a caller can expect a refusal.
    Passing a width no generator can meet is safe; it just gets the
    narrowest program each of them can build.
    """
    try:
        fn = GENERATORS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    if width is not None and takes_width(fn):
        return str(fn(text, width))
    return wrap_program(str(fn(text)), LANGUAGES[language].id, width)


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
        module, split = RUNNERS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    run_fn = importlib.import_module("esolangs.interpreters." + module).run
    io_obj = ScriptedIO(stdin)
    program_args: str | list[str] = program.splitlines() if split else program
    _run(run_fn, program_args, io_obj, timeout)
    return io_obj.getvalue()


def _run(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float | None,
) -> None:
    """Run ``run_fn``, applying the wall-clock ``timeout`` guard when set."""
    if timeout is None:
        run_fn(program, io_obj)
    elif threading.current_thread() is threading.main_thread() and hasattr(
        signal, "SIGALRM"
    ):
        _run_timed_signal(run_fn, program, io_obj, timeout)
    else:
        raise ValueError("the timeout guard uses SIGALRM and needs a Unix main thread")


def _run_timed_signal(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float,
) -> None:
    """Run ``run_fn`` under a ``SIGALRM`` wall-clock guard (main thread only)."""

    def _timeout_handler(_signum: int, _frame: object) -> None:
        # coverage cannot trace a raise inside a signal handler
        raise HaltError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        run_fn(program, io_obj)
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
        "text_generator": lang.text is not None,
        "boolean_generator": lang.boolean is not None,
        "transpilers": transpilers,
        "examples": examples,
        "wiki_url": f"https://esolangs.org/wiki/{language.replace(' ', '_')}",
    }


def transpile(source: str, target: str, program: str, **kwargs: int) -> str:
    """Rewrite a ``program`` in ``source`` into an equivalent one in ``target``.

    Extra keyword arguments are forwarded to the transpiler; none of the
    shipped ones takes any today.
    """
    try:
        fn = TRANSPILERS[(source, target)]
    except KeyError:
        raise UnsupportedTranspilationError(source, target) from None
    return fn(program, **kwargs)


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
