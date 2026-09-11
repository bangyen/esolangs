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


class ExecutionTimeoutError(HaltError, TimeoutError):
    """A run was stopped by its wall-clock bound rather than by the program.

    Separate from a plain :class:`HaltError` because the two mean opposite
    things to a caller checking a truth table.  Three languages answer by
    *terminating* -- they halt for a 0 and loop forever for a 1 -- so
    ``except HaltError: answer = 1`` is the natural code, and it would score
    an invalid-operation halt as a 1.  Catching this instead says only what
    it means: the clock ran out.
    """


class UnknownLanguageError(EsolangError, ValueError):
    """A language name was not in the registry."""

    def __init__(self, language: str, suggestions: tuple[str, ...] = ()) -> None:
        """Build the error for an unknown ``language`` name.

        ``suggestions`` are close registry names; naming them turns the
        commonest failure -- a case or spelling slip -- into a fix the
        reader can apply without opening ``esolangs list``.
        """
        # With nothing close enough to suggest, the message was a dead end:
        # true, and no help at all to someone who has misremembered a name
        # rather than mistyped one.  So it names the command that lists them.
        hint = (
            f" (did you mean {' or '.join(suggestions)}?)"
            if suggestions
            else "; `esolangs list` shows all of them"
        )
        super().__init__(f"unknown language: {language}{hint}")
        self.language = language
        self.suggestions = suggestions


class ArgumentError(EsolangError, ValueError):
    """An argument's value is outside what the call accepts.

    A width of zero, a non-positive timeout, a width that is not an integer.
    These were plain ``ValueError``s, which made the package's one promise --
    that everything raised on purpose derives from :class:`EsolangError` --
    false for three of the commonest mistakes.
    """


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


class GeneratorCapError(EsolangError, ValueError):
    """A boolean generator refusing a table that is too big for it.

    Deliberate, and that is the whole point of the class.  Five generators
    stop rather than build: Factor's encoded integer outgrows its digit
    budget, Polynomial emits one instruction per prime and runs out of them,
    WII2D's decode spans more points than its cost guard allows, ZTOALC L
    needs more command lines than its committed anchors offer, and
    Interprogck8 cannot find a rung slot for a jump.

    All five used to raise a plain :class:`ValueError` -- Interprogck8 a
    *private* ``_StuckError`` nothing exported, so a caller could not name
    it to catch it -- which broke this package's one stated promise about
    errors: "Every error raised on purpose derives from ``EsolangError``".
    The refusals are as on-purpose as an error gets; each carries a
    hand-written sentence explaining the arithmetic that defeated it.  A
    sweep over the registry written to the documented idiom crashed on the
    first of them.

    Still a :class:`ValueError`, so code catching that keeps working.

    This is also the answer to "what is this generator's maximum arity?",
    which ``describe`` deliberately does not carry.  The caps are not
    arity-bounded: Polynomial refuses on how many minterms a table needs and
    Factor on how many digits it encodes to, so a sparse table can build at
    a size where a dense one is refused.  A per-language number would be
    wrong for half the tables it was consulted about; catching this is
    right for all of them.
    """


class InputMismatchWarning(UserWarning):
    """Warned when stdin does not look like what the program read.

    Its own class so a caller can silence or escalate exactly these and
    nothing else: ``filterwarnings("error", category=InputMismatchWarning)``
    turns a silent wrong answer into a test failure, which is what someone
    sweeping the registry wants, while a plain ``UserWarning`` filter would
    have caught every other warning in the process too.
    """
