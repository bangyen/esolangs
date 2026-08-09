"""Exceptions raised by the public esolangs API."""


class EsolangError(Exception):
    """Base class for errors from the esolangs package."""


class HaltError(EsolangError):
    """An interpreter halted on a runtime condition.

    Some languages terminate on conditions that would otherwise surface as
    incidental Python errors (e.g. popping an empty stack).  Raising
    ``HaltError`` makes the halt explicit so the fuzz suite can treat it as
    a normal outcome rather than a crash.
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
