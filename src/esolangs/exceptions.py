"""Exceptions raised by the public esolangs API.

Every error the package raises on purpose derives from
:class:`EsolangError`, so ``except EsolangError`` is the one handler a
caller needs.  Each also derives from the built-in type it replaced --
``ValueError`` for a bad argument, ``EOFError`` for exhausted input -- so
code written against those keeps working, and the repo-wide "exhausted
input raises ``EOFError``" convention the interpreters document still
holds.
"""


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

    def __init__(self, language: str, suggestions: tuple[str, ...] = ()) -> None:
        """Build the error for an unknown ``language`` name.

        ``suggestions`` are close registry names; naming them turns the
        commonest failure -- a case or spelling slip -- into a fix the
        reader can apply without opening ``esolangs list``.
        """
        hint = f" (did you mean {' or '.join(suggestions)}?)" if suggestions else ""
        super().__init__(f"unknown language: {language}{hint}")
        self.language = language
        self.suggestions = suggestions


class ProgramError(EsolangError, ValueError):
    """A program could not be loaded: it is malformed for its language."""


class TruthTableError(EsolangError, ValueError):
    """A truth table was not a binary string of length ``2**n``."""


class TemplateError(EsolangError, ValueError):
    """A parameterized generator's template was used as a program.

    The parameterized generators return a *template* whose ``{Xi}`` slots
    stand for the language's own code for setting input ``i``.  Running one
    unfilled is never what the caller meant: the slots are not instructions,
    so the program either faults on them or -- worse -- ignores them and
    computes a constant.  Filling them is :func:`esolangs.instantiate`.
    """


class InputExhaustedError(EsolangError, EOFError):
    """A program read past the end of its input.

    Derives from :class:`EOFError` because that is the repo-wide convention
    the interpreters document and detect on; it adds the message a bare
    ``EOFError()`` never carried.
    """

    def __init__(self, reads: int, supplied: int) -> None:
        """Build the error after ``reads`` reads against ``supplied`` lines."""
        super().__init__(
            f"program read past the end of input: {supplied} "
            f"line{'' if supplied == 1 else 's'} supplied, "
            f"read {reads + 1}"
        )
        self.reads = reads
        self.supplied = supplied
