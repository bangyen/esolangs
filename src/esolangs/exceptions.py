"""Exceptions raised by the public esolangs API.

Every deliberate error derives from :class:`EsolangError`, and each also
from the built-in it replaced (``ValueError``, ``EOFError``).
"""


class EsolangError(Exception):
    """Base class for errors from the esolangs package."""

    #: Output written before the raise; empty for errors raised before the
    #: program ran.  (``run`` once dropped it while the debugger showed it.)
    partial_output: str = ""


class HaltError(EsolangError):
    """An interpreter halted on an invalid operation.

    Raised bare it carries :data:`DEFAULT`, deliberately weak.
    """

    #: Message for a bare ``raise HaltError``.
    DEFAULT = "the interpreter halted on an operation with no defined result"

    def __init__(self, *args: object) -> None:
        """Fall back to :data:`DEFAULT` when raised with no message."""
        super().__init__(*(args or (self.DEFAULT,)))


class ExecutionTimeoutError(HaltError, TimeoutError):
    """A run was stopped by its wall-clock bound rather than by the program.

    Not a plain :class:`HaltError`: three languages answer by terminating.
    """


class UnknownLanguageError(EsolangError, ValueError):
    """A language name was not in the registry."""

    def __init__(self, language: str, suggestions: tuple[str, ...] = ()) -> None:
        """Build the error for an unknown ``language``, with close ``suggestions``."""
        # No close match: point at the command that lists them.
        hint = (
            f" (did you mean {' or '.join(suggestions)}?)"
            if suggestions
            else "; `esolangs list` shows all of them"
        )
        # Quote only when bare would mislead (an empty name, whitespace,
        # unprintables).
        shown = (
            language
            if language and language == language.strip() and language.isprintable()
            else repr(language)
        )
        super().__init__(f"unknown language: {shown}{hint}")
        self.language = language
        self.suggestions = suggestions

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """Rebuild from the arguments, not from the rendered message.

        The default replays ``self.args`` -- the message -- and re-prefixed it per hop.
        """
        return (type(self), (self.language, self.suggestions))


class ArgumentError(EsolangError, ValueError):
    """An argument's value is outside what the call accepts."""


class ProgramError(EsolangError, ValueError):
    """A program could not be loaded: it is malformed for its language."""


class ProgramNotFoundError(ProgramError, FileNotFoundError):
    """A program file could not be read because it is not there.

    Also a :class:`FileNotFoundError`, for callers who catch the stdlib's.
    """


class TruthTableError(EsolangError, ValueError):
    """A truth table was not a usable binary string of length ``2**n``.

    ``"0"`` is refused: a constant, not a function.
    """


class TemplateError(EsolangError, ValueError):
    """A parameterized generator's template was used as a program.

    Fill the runs with :func:`esolangs.instantiate`.
    """


class InputExhaustedError(EsolangError, EOFError):
    """A program read past the end of its input.

    An :class:`EOFError`, the convention the interpreters detect on.
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

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """Rebuild from the arguments, not from the rendered message.

        Unpicklable, it took a ``ProcessPoolExecutor`` down with ``BrokenProcessPool``.
        """
        return (type(self), (self.reads, self.supplied))


class GeneratorCapError(EsolangError, ValueError):
    """A boolean generator refusing a table that is too big for it.

    Polynomial (primes), WII2D (decode points).  Still a
    :class:`ValueError`.  The caps are not arity-bounded, which is why
    ``describe`` carries no maximum arity.
    """


class InputMismatchWarning(UserWarning):
    """Warned when stdin does not look like what the program read.

    Its own class so ``filterwarnings("error", category=...)`` escalates exactly these.
    """


class InterpreterLimitError(HaltError):
    """An interpreter hit an implementation limit running a program.

    The program is well formed (Qoibl's recursion); distinct from a generator's cap.
    """
