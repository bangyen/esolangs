"""Exceptions raised by the public esolangs API."""


class EsolangError(Exception):
    """Base class for errors from the esolangs package."""


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
