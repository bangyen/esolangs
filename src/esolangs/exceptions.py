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

    #: What the program had already written when this was raised.
    #:
    #: A program that prints and *then* fails had printed something, and
    #: :func:`esolangs.run` used to drop it: the exception went up and the
    #: buffer went out of scope, so a Modulous program that prints ``Hi``
    #: and then pops an empty stack gave a caller nothing at all -- while
    #: the debugger, driving the same interpreter, showed ``output: 'Hi'``.
    #: For someone debugging their own program the bytes before the failure
    #: are most of the diagnosis.
    #:
    #: Empty for every error raised before the program ran, which is most
    #: of them.
    partial_output: str = ""


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
        # Quoted only when the bare rendering would mislead.  An empty name
        # read as "unknown language: ; `esolangs list` shows all of them" --
        # a sentence with a hole in it -- and a name carrying whitespace or
        # an unprintable character showed as the name the reader typed,
        # which is how a suggestion came to look identical to the input.
        # The ordinary case stays unquoted, since quoting every miss to
        # cover the rare one makes the common message worse.
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

        An exception that composes its message in ``__init__`` cannot use
        the default, which replays ``self.args`` -- and ``self.args`` here is
        the *message*, not the arguments.  So unpickling called
        ``__init__(message)`` and this class needs two, which is why a
        message got the prefix and the suffix applied *again* on every
        round trip -- "unknown language: unknown language: nosuchlang" after
        one hop, tripled after two -- so a bad name coming back from a
        worker process arrived already doubled.
        """
        return (type(self), (self.language, self.suggestions))


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
    """A truth table was not a usable binary string of length ``2**n``.

    *Usable* because the length rule alone is not the rule: ``"0"`` is a
    binary string of length ``2**0`` and is refused, since a one-entry
    table is a constant rather than a function of any input, and every
    generator here exists to read inputs and branch on them.
    """


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

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """Rebuild from the arguments, not from the rendered message.

        An exception that composes its message in ``__init__`` cannot use
        the default, which replays ``self.args`` -- and ``self.args`` here is
        the *message*, not the arguments.  So unpickling called
        ``__init__(message)`` and this class needs two, which is why a
        worker raising it took a ``ProcessPoolExecutor`` down with
        ``BrokenProcessPool`` and no diagnostic: the error could not survive
        the trip home.  It is the commonest error in the package, and a
        parallel sweep over the registry is the obvious thing to build.
        """
        return (type(self), (self.reads, self.supplied))


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


class InterpreterLimitError(HaltError):
    """An interpreter hit an implementation limit running a program.

    Not a fault in the program and not a refusal by a generator: the
    program is well formed and the interpreter simply cannot carry it.
    Qoibl's is recursive, so a large enough program exhausts Python's
    stack, and a bare ``RecursionError`` came straight out of
    :func:`esolangs.verify` -- the one exception in the package that was
    not an :class:`EsolangError`, which is the single promise the module
    docstring makes about errors.

    Separate from :class:`~esolangs.exceptions.GeneratorCapError` because
    the two say different things.  A cap is a generator declining to build;
    this is a program that was built, is correct, and cannot be run here.
    """
