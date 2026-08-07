"""Public API for the esolangs package.

Provides ``generate`` (produce a program that prints a text), ``run``
(execute a program through an interpreter), and ``list_languages``.
"""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.exceptions import UnknownLanguageError
from esolangs.registry import GENERATORS, LANGUAGES, RUNNERS


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

    def read_input(prompt: str = "") -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    buffer = io.StringIO()
    with patch("builtins.input", read_input), redirect_stdout(buffer):
        run_fn(program.splitlines() if split else program, **kwargs)
    return buffer.getvalue()


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
