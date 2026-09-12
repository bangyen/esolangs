r"""Exceptions raised by the public esolangs API."""


class EsolangError(Exception):
    r"""Base class for errors from the esolangs package."""

    # : What the program had.
    # :.
    # : A program that prints and.
    # : :func:`esolangs.run` used.
    # : buffer went out of scope,.
    # : and then pops an empty.
    # : the debugger, driving the.
    # : For someone debugging their.
    #: are most of the diagnosis.
    # :.
    # : Empty for every error.
    #: of them.
    partial_output: str = ""


class HaltError(EsolangError):
    r"""An interpreter halted on an invalid operation."""

    # : What a bare ``raise.
    DEFAULT = "the interpreter halted on an operation with no defined result"

    def __init__(self, *args: object) -> None:
        r"""Fall back to :data:`DEFAULT` when raised with no message."""
        super().__init__(*(args or (self.DEFAULT,)))


class ExecutionTimeoutError(HaltError, TimeoutError):
    r"""A run was stopped by its wall-clock bound rather than by the."""


class UnknownLanguageError(EsolangError, ValueError):
    r"""A language name was not in the registry."""

    def __init__(self, language: str, suggestions: tuple[str, ...] = ()) -> None:
        r"""Build the error for an unknown ``language`` name."""
        # With nothing close enough to.
        # true, and no help at all to.
        # rather than mistyped one.
        hint = (
            f" (did you mean {' or '.join(suggestions)}?)"
            if suggestions
            else "; `esolangs list` shows all of them"
        )
        # Quoted only when the bare.
        # read as "unknown language: ;.
        # a sentence with a hole in it.
        # an unprintable character.
        # which is how a suggestion.
        # The ordinary case stays.
        # cover the rare one makes the.
        shown = (
            language
            if language and language == language.strip() and language.isprintable()
            else repr(language)
        )
        super().__init__(f"unknown language: {shown}{hint}")
        self.language = language
        self.suggestions = suggestions

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        r"""Rebuild from the arguments, not from the rendered message."""
        return (type(self), (self.language, self.suggestions))


class ArgumentError(EsolangError, ValueError):
    r"""An argument's value is outside what the call accepts."""


class ProgramError(EsolangError, ValueError):
    r"""A program could not be loaded: it is malformed for its language."""


class ProgramNotFoundError(ProgramError, FileNotFoundError):
    r"""A program file could not be read because it is not there."""


class TruthTableError(EsolangError, ValueError):
    r"""A truth table was not a usable binary string of length ``2**n``."""


class TemplateError(EsolangError, ValueError):
    r"""A parameterized generator's template was used as a program."""


class InputExhaustedError(EsolangError, EOFError):
    r"""A program read past the end of its input."""

    def __init__(self, reads: int, supplied: int) -> None:
        r"""Build the error after ``reads`` reads against ``supplied`` lines."""
        super().__init__(
            f"program read past the end of input: {supplied} "
            f"line{'' if supplied == 1 else 's'} supplied, "
            f"read {reads + 1}"
        )
        self.reads = reads
        self.supplied = supplied

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        r"""Rebuild from the arguments, not from the rendered message."""
        return (type(self), (self.reads, self.supplied))


class GeneratorCapError(EsolangError, ValueError):
    r"""A boolean generator refusing a table that is too big for it."""


class InputMismatchWarning(UserWarning):
    r"""Warned when stdin does not look like what the program read."""


class InterpreterLimitError(HaltError):
    r"""An interpreter hit an implementation limit running a program."""
