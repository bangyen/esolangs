"""Public API for the esolangs package.

Provides ``generate`` (produce a program that prints a text), ``run``
(execute a program through an interpreter), ``transpile`` (rewrite a
program between languages), and ``list_languages``.
"""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.exceptions import (
    UnknownLanguageError,
    UnsupportedTranspilationError,
)
from esolangs.registry import GENERATORS, LANGUAGES, RUNNERS
from esolangs.tools.transpilers import TRANSPILERS


def generate(language: str, text: str) -> str:
    """Return a program in ``language`` that prints ``text``."""
    try:
        fn = GENERATORS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    return str(fn(text))


def run(language: str, program: str, stdin: str = "") -> str:
    """Execute ``program`` and return its output.

    Input is fed to the program line by line from ``stdin``.
    """
    try:
        module, split, kwargs = RUNNERS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    run_fn = importlib.import_module("esolangs.interpreters." + module).run
    lines = iter(stdin.splitlines())

    def read_input(_prompt: str = "") -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    buffer = io.StringIO()
    with patch("builtins.input", read_input), redirect_stdout(buffer):
        run_fn(program.splitlines() if split else program, **kwargs)
    return buffer.getvalue()


def transpile(source: str, target: str, program: str, **kwargs: int) -> str:
    """Rewrite a ``program`` in ``source`` into an equivalent one in ``target``.

    Transpilers with extra options accept them as keyword arguments (for
    example ``size`` when targeting CircleFuck).
    """
    try:
        fn = TRANSPILERS[(source, target)]
    except KeyError:
        raise UnsupportedTranspilationError(source, target) from None
    return fn(program, **kwargs)


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
