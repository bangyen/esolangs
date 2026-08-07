"""Exceptions raised by the public esolangs API."""


class EsolangError(Exception):
    """Base class for errors from the esolangs package."""


class UnknownLanguageError(EsolangError, ValueError):
    """A language name was not in the registry."""

    def __init__(self, language: str) -> None:
        super().__init__(f"unknown language: {language}")
