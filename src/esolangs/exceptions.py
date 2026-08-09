"""Exceptions raised by the public esolangs API."""


class EsolangError(Exception):
    """Base class for errors from the esolangs package."""


class HaltError(EsolangError):
    """An interpreter halted on an invalid operation.

    A program that performs a mathematically or structurally invalid
    operation (e.g. division by zero, popping an empty stack) has no defined
    result, so the interpreter halts rather than inventing one.  Raising
    ``HaltError`` makes that halt explicit instead of leaking an incidental
    Python error.
    """


class UnknownLanguageError(EsolangError, ValueError):
    """A language name was not in the registry."""

    def __init__(self, language: str) -> None:
        """Build the error for an unknown ``language`` name."""
        super().__init__(f"unknown language: {language}")


class UnsupportedTranspilationError(EsolangError, ValueError):
    """No transpiler exists for a (source, target) language pair."""

    def __init__(self, source: str, target: str) -> None:
        """Build the error for an unsupported ``source`` to ``target`` pair."""
        super().__init__(f"no transpiler from {source} to {target}")
