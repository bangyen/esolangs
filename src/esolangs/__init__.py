"""Public API for the esolangs package.

Provides ``generate`` (produce a program computing a truth table),
``instantiate`` (fill a parameterized generator's ``{Xi}`` slots), ``run``
(execute a program through an interpreter), ``make_vm`` (a step-and-inspect
wrapper around the step-capable interpreters), ``make_debugger`` (a
breakpoint/watch layer over the VM), ``describe`` (a structured language
summary), and ``list_languages``.

``encode_inputs`` and ``read_answer`` are the two halves of feeding a
program and judging what it printed; ``check_stdin`` says whether stdin is
what a language wants before anything runs; ``check_program`` applies the
load-time checks on their own.

``evaluate`` and ``verify`` are the round trip those compose into: they
generate a program for a truth table, run it on every row, and return the
table it computes (or whether it matches).  They were missing from this
list and from the README while being the one-call answer to the question
both documents spend a paragraph posing, so a reader found them only by
calling ``dir()``.

Every language name is resolved case-insensitively
(:func:`esolangs.registry.resolve`), so ``Brainfuck`` and ``brainfuck``
reach the same interpreter and a near miss is answered with a suggestion.
Every error raised on purpose derives from
:class:`~esolangs.exceptions.EsolangError`.
"""

import importlib
import importlib.metadata as _metadata
import os
import pathlib
import re
import signal
import threading
import warnings
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any, cast

from esolangs._validate import check_bits, check_timeout, check_width
from esolangs.debugger import STOP_REASONS, Debugger, StopReason, make_debugger
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    HaltError,
    InputExhaustedError,
    InputMismatchWarning,
    InterpreterLimitError,
    ProgramError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import (
    LANGUAGES,
    RUNNERS,
    _fills,
    example_stems,
    parameterized_ids,
    resolve,
    wiki_url,
)

# Imported private: it takes a *generator function*, not a language name, so
# a caller reaching for ``esolangs.takes_width("LaserFuck")`` got False for
# every language in the registry, contradicting both its own docstring and
# ``describe(...)["width_aware"]`` -- which is the question they were asking.
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.tools.wrap import wrap_program
from esolangs.vm import VM, machine_traits, make_vm

#: Read from the installed distribution rather than written here: the
#: hand-kept copy said 0.1.0 while the package was 0.2.0, so ``--version``
#: named a release that does not exist.  The fallback covers a source tree
#: that was never installed.
try:
    __version__ = _metadata.version("esolangs")
except _metadata.PackageNotFoundError:  # pragma: no cover - installed in CI
    __version__ = "0.0.0+unknown"

#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ANSWER_MODES",
    "INPUT_SHAPES",
    "STOP_REASONS",
    "TERMINATION_OUTCOMES",
    "VM",
    "ArgumentError",
    "Debugger",
    "EsolangError",
    "ExecutionTimeoutError",
    "GeneratorCapError",
    "HaltError",
    "InputExhaustedError",
    "InputMismatchWarning",
    "InterpreterLimitError",
    "ProgramError",
    "StopReason",
    "TemplateError",
    "TruthTableError",
    "UnknownLanguageError",
    "__version__",
    "check_program",
    "check_stdin",
    "describe",
    "encode_inputs",
    "evaluate",
    "generate",
    "instantiate",
    "list_languages",
    "make_debugger",
    "make_vm",
    "read_answer",
    "run",
    "spec",
    "verify",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``.

    Without this ``dir(esolangs)`` also offered ``os``, ``re``, ``signal``,
    ``threading`` and a dozen internals -- every module this one imports --
    with nothing to mark which of them the package actually supports.
    """
    return sorted(__all__)


_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"

# An unfilled input slot in a parameterized generator's template.  Matched
# only for the languages whose generator emits one: ``{`` is a live command
# in several of the others, so a blanket search would refuse real programs.
_SLOT = re.compile(r"\{X\d+\}")
_SLOT_INDEX = re.compile(r"\{X(\d+)\}")

# Interpreter module family -> state model name.
_STATE_MODELS = {
    "register_based": "register",
    "tape_based": "tape",
    "stack_based": "stack",
    "grid_based": "grid",
    "queue_based": "queue",
    "other": "other",
}


class _Template(str):
    """A parameterized generator's template, tagged with the language.

    A template is otherwise an ordinary string of source with ``{Xi}`` slots
    in it, and that is the whole problem: :func:`instantiate` had no way to
    tell whose it was, so it accepted any name and substituted *that*
    language's setter code into another language's program.  The result was
    not an error and not obviously wrong -- it ran, and answered::

        mf = generate("Minifuck", "0110")     # XOR
        instantiate("RAM0", mf, [0, 1])       # wrong language, no complaint
        # ... and the program answers 0, where XOR of 0 and 1 is 1.

    Syntax cannot catch that; the mismatched program was well-formed. So the
    template carries its language and :func:`instantiate` compares.

    The tag is an attribute on a ``str`` subclass rather than a wrapper type
    so that a template stays a string everywhere else -- it is written to
    files, printed, and sliced by callers who should not have to know this
    exists.  Which also means the tag does not survive a round trip through
    disk, and a plain ``str`` is therefore accepted unchecked: the check
    catches the mistake where it is made, in one process, and does not
    pretend to cover the file the CLI wrote an hour ago.
    """

    language: str

    def __new__(cls, text: str, language: str) -> "_Template":
        """Return ``text`` tagged as ``language``'s template."""
        template = super().__new__(cls, text)
        template.language = language
        return template


def generate(language: str, truth_table: str, width: int | None = None) -> str:
    """Return a program in ``language`` computing ``truth_table``.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), so the table length implies the input
    count and the generators take no ``n``.

    **Seventeen languages return a *template*, not a runnable program.**
    Their generators embed the inputs in the code instead of reading them,
    leaving a ``{Xi}`` slot per input; :func:`instantiate` fills the slots
    with that language's own code for setting an input, and
    ``describe(language)["parameterized"]`` says in advance which kind you
    will get.  Passing an unfilled template to :func:`run` raises
    :class:`~esolangs.exceptions.TemplateError` rather than running it --
    the slots are not instructions, and a language that happens to ignore
    them computes a constant and reports it as the answer.

    **A generator may refuse a table that is too big for it**, with
    :class:`~esolangs.exceptions.GeneratorCapError`.  Several do, each for
    its own arithmetic reason, and a sweep over the registry should expect
    it::

        try:
            program = generate(language, table)
        except GeneratorCapError as refusal:
            print(f"{language} cannot build this one: {refusal}")

    There is deliberately no ``describe(...)["max_arity"]`` to consult
    first, because there is no such number: Polynomial refuses on how many
    minterms a table needs and Factor on how many digits it encodes to, so a
    sparse table can build at a size where a dense one is refused.  The
    refusal is the answer, and it is exact.

    ``width`` bounds the program to that many columns for readability;
    :data:`esolangs.tools.wrap.DEFAULT_WIDTH` is the conventional choice.
    The default of ``None`` asks for no bound, so a caller that does not
    want one gets exactly what the generator produces.

    Most languages honour it by *wrapping* the finished program, breaking
    only between whole tokens so it still means the same thing.  A few build
    a shape rather than a line -- LaserFuck folds its grid's straight runs
    -- and cannot be reflowed after the fact; those generators take the
    width themselves and lay the program out to fit.

    **``width`` is a request, not a guarantee.**  A language whose newlines
    are semantic (the 2D grid languages) or that rejects them outright
    (NoComment) ignores it rather than raising, so one width can be passed
    across every language -- but so does any language with no wrapper, and
    a language *with* one still overruns on a token longer than the width,
    since breaking that token is what wrapping exists to avoid.  At
    ``width=20`` twenty-nine of the sixty-nine come back with a longer line,
    across every state model rather than only the 2D ones.  Passing a width
    no generator can meet is safe; it just gets the narrowest program each
    of them can build, which is sometimes wider than you asked.
    """
    resolved = resolve(language)
    lang = LANGUAGES[resolved]
    fn = lang.boolean
    if fn is None:
        raise UnknownLanguageError(language)
    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    check_width(width)
    if width is not None and _takes_width(fn):
        return str(fn(truth_table, width))
    if lang.id in parameterized_ids():
        # A template is not wrapped.  No wrapper names ``{Xi}`` as a token,
        # so a narrow width breaks a slot in half -- ``{X`` ending one line
        # and ``1}`` starting the next -- and the template silently stops
        # being instantiable: ``generate --width 10 "Home Row" 0110`` then
        # reported one input slot where the table has two.  Wrapping belongs
        # after the slots are gone, so :func:`instantiate` takes the width.
        return _Template(str(fn(truth_table)), resolved)
    return wrap_program(str(fn(truth_table)), lang.id, width)


def instantiate(
    language: str,
    template: str,
    bits: list[int] | tuple[int, ...],
    width: int | None = None,
    truth_table: str | None = None,
) -> str:
    """Fill a parameterized generator's ``{Xi}`` slots with ``bits``.

    The seventeen parameterized generators embed their inputs in the program
    text rather than reading them, so :func:`generate` returns a template
    with one ``{Xi}`` slot per input.  This substitutes ``bits[i]`` into slot
    ``i`` using the language's own code for setting an input, returning a
    program that runs with no stdin at all::

        template = generate("Minifuck", "0110")
        run("Minifuck", instantiate("Minifuck", template, [1, 0]))

    The per-language substitution is the one each committed example already
    uses, so an instantiated program here is built exactly the way
    ``examples/boolean`` is.  Every setter spells a 0 and a 1 at the same
    width, so the program's length never leaks the bits it evaluates.

    A language whose generator reads its inputs instead raises
    :class:`~esolangs.exceptions.TemplateError`: there is nothing to fill,
    and returning the program unchanged would let a caller believe bits had
    been embedded when the program is still waiting on stdin.

    ``truth_table`` is optional and is the table the template should have
    come from; passing it checks that this *is* that template.  Worth
    having because the language tag cannot: a tag does not survive a file,
    so a plain string is accepted unchecked, and a hand-written
    ``"hello {X0}"`` was substituted into and returned a program that ran
    to nothing.  With the table there is something to compare against.

    ``bits`` is checked against the slots the template actually has, and
    every value must be 0 or 1.  Both are worth a check because neither is
    caught downstream: too few bits leaves a slot unfilled (which ``run``
    then refuses, one step from the cause), and a value like ``2`` is
    substituted without complaint into a program that no longer computes
    the table.
    """
    check_width(width)
    name = resolve(language)
    if truth_table is not None and template != generate(name, truth_table):
        # The provenance check a tag cannot make.  A template carries its
        # language, so filling one language's as another is refused -- but a
        # *hand-written* string is untagged by design (a tag cannot survive
        # a file), and `instantiate("Minifuck", "hello {X0}", [1])` happily
        # substituted into it and returned something that ran to nothing.
        # Given the table it should have come from, that is decidable.
        raise TemplateError(
            f"this is not the template generate({name!r}, {truth_table!r}) "
            f"returns, so filling it would produce a program that does not "
            f"compute that table"
        )
    fill = _fills().get(LANGUAGES[name].id)
    if fill is None:
        raise TemplateError(
            f"{name} reads its inputs rather than embedding them, so there "
            f"is nothing to instantiate; pass them in as stdin instead"
        )
    if not isinstance(template, str):
        raise TemplateError(
            f"template must be the string generate() returned, got "
            f"{type(template).__name__}"
        )
    origin = getattr(template, "language", None)
    if origin is not None and origin != name:
        raise TemplateError(
            f"this template came from generate({origin!r}, ...), so filling "
            f"it as {name} would substitute {name}'s setter code into a "
            f"{origin} program -- which runs, and answers the wrong row"
        )
    bits = check_bits(bits, "bits")
    wanted = len({int(slot) for slot in _SLOT_INDEX.findall(template)})
    if len(bits) != wanted:
        if wanted == 0:
            # The count is true and answers a question nobody asked.  Both
            # ways of getting here -- an ordinary program, and a template
            # instantiate() has already filled -- look the same from here,
            # so the message names both rather than guessing.
            raise TemplateError(
                f"this {name} text has no {{Xi}} slots to fill: it is either "
                f"an ordinary program or a template instantiate() has already "
                f"been applied to, and generate({name!r}, table) returns the "
                f"template to fill"
            )
        given = (
            f"{len(bits)} bit was given"
            if len(bits) == 1
            else f"{len(bits)} bits were given"
        )
        raise TemplateError(
            f"this {name} template has {wanted} input slot"
            f"{'' if wanted == 1 else 's'}, but {given}"
        )
    # The width lands here rather than on ``generate``, because a slot is
    # not a token any wrapper knows and a break inside one destroys the
    # template.  Once the bits are in, the program is ordinary text again.
    return wrap_program(fill(template, bits), LANGUAGES[name].id, width)


def check_runnable(language: str, program: str) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are mistakes a running interpreter cannot report, because both are
    *valid* input to it: a filename is a string of characters the language
    mostly ignores, and a ``{Xi}`` slot is either a fault far from its cause
    or -- Minifuck's case -- silently nothing.  Each produced a confident
    wrong answer, which is the one outcome worth spending a check to avoid.

    Public because :func:`run` is not the only way to execute a program:
    the debugger stepped an unfilled template all the way to a confident
    ``output: '0'``, so the CLI's ``debug`` calls this too.
    """
    name = resolve(language)
    if "\n" not in program and program.endswith(".txt") and os.path.exists(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r})"
        )
    if LANGUAGES[name].id in parameterized_ids() and _SLOT.search(program):
        slots = sorted(set(_SLOT.findall(program)))
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled slots ({', '.join(slots)}); fill them with "
            f"esolangs.instantiate({name!r}, program, bits)"
        )


def check_program(
    language: str, program: str | os.PathLike[str], stdin: str = ""
) -> str:
    """Return ``program`` as source, having checked it and ``stdin``.

    The whole load-time contract in one place, because there are two ways
    to execute a program and only :func:`run` used to apply it:
    ``make_debugger("brainfuck", None)`` raised ``'NoneType' is not a
    container or iterable`` from inside an interpreter, where ``run`` had
    long said ``program must be a string of source or a Path``.

    A :class:`~pathlib.Path` is read here.  Its trailing newline is the
    file's rather than the program's, and three interpreters (CV(N)(C),
    Grapheme, NoComment) reject one as an unknown command, which made
    reading a committed example fail on the very files this package ships.

    That is fixed, but the one-liner this used to show as proof was not a
    working example: two of those three read stdin, so
    ``run(lang, Path(describe(lang)["examples"][0]))`` raises
    :class:`~esolangs.exceptions.InputExhaustedError` for them -- for want
    of input, not for the newline.  The whole call is::

        path = pathlib.Path(describe(lang)["examples"][0])
        run(lang, path, encode_inputs(lang, [0, 1]))
    """
    name = resolve(language)
    if isinstance(program, os.PathLike):
        try:
            program = pathlib.Path(program).read_text(encoding="utf-8").rstrip("\n")
        except OSError as exc:
            raise ProgramError(f"cannot read {program}: {exc}") from exc
        except UnicodeDecodeError as exc:
            # Named separately because it is a ``ValueError``, not an
            # ``OSError``, so the clause above never caught it: a Path to a
            # PNG raised a bare ``UnicodeDecodeError`` from inside pathlib
            # where every other unreadable file is a ``ProgramError``.
            raise ProgramError(
                f"cannot read {program}: not text (invalid UTF-8 at byte {exc.start})"
            ) from exc
    if not isinstance(program, str):
        raise ProgramError(
            f"program must be a string of source or a Path, got "
            f"{type(program).__name__}"
        )
    if not isinstance(stdin, str):
        # ArgumentError, not ProgramError: the stdin is not the program, and
        # ProgramError says "a program could not be loaded: it is malformed
        # for its language".  ``check_stdin`` filed the identical fault as an
        # ArgumentError all along, so the four entry points that reach here
        # disagreed with it -- and a caller who wrapped their bad-stdin guard
        # in ``except ArgumentError`` caught it for one function and missed
        # it for the other four.
        raise ArgumentError(
            f"stdin must be a string, got {type(stdin).__name__}; "
            f"join your lines with '\\n'"
        )
    check_runnable(name, program)
    return program


def run(
    language: str,
    program: str | os.PathLike[str],
    stdin: str = "",
    timeout: float | None = None,
    seed: int | None = None,
) -> str:
    """Execute ``program`` and return its output.

    **A Path and its text are not quite the same argument.**  Reading a
    file strips one trailing newline and passing a string does not, so
    ``run(lang, path)`` and ``run(lang, path.read_text())`` disagree for
    the languages where a newline is not a legal character -- CV(N)(C)
    answers the first and refuses the second, naming the newline as a
    symbol it does not have.  Both halves are deliberate: one in a file is
    the editor's, and a trailing newline in a string you built is yours.
    This said only that a Path "is read", which reads as equivalence.

    ``program`` is the program's *source*.  A :class:`~pathlib.Path` is read
    first, so the CLI's file-taking habit carries over; a plain string that
    names an existing ``.txt`` file is refused rather than executed, because
    a filename is a perfectly legal program in most of these languages and
    ``run(lang, "examples/boolean/brainfuck.txt")`` quietly printed a null
    byte instead of saying it had run the filename.

    Input is fed to the program line by line from ``stdin``.  A program
    that asks for more than it is given usually raises
    :class:`~esolangs.exceptions.InputExhaustedError`, and that is the
    package norm -- but not a universal one, and this sentence used to
    claim it was.

    Measured, underfeeding a three-input program by one bit across the
    fifty-two languages that read stdin at all: **43 raise**, 6 answer a
    different row of the table (Circuit Diagram, Clockwise, DINAC, Fargo,
    Flowchart, S*bleq), 2 run on and produce output :func:`read_answer`
    then refuses (Suffolk, Suptiftam), and Alight raises about its own
    arithmetic.

    Four of those six now say so, with an
    :class:`~esolangs.exceptions.InputMismatchWarning`; this said all six
    were silent, which understated the package.  The two that stay silent
    are Clockwise and Fargo, whose underfed input is a single line of
    exactly the right shape -- there is no read past an end to notice, and
    only ``check_stdin`` with the table can catch them.

    ``describe(language)["eof_is_a_value"]`` marks the ones that take an
    exhausted read as a value.  Clockwise is *not* among them and still
    answers: its input is a single line, so an underfed program gets a
    shorter string and never reads past an end -- undetectable in
    principle, like Taglate's pad order.  The zero-beyond-input convention
    was audited against the wiki pages and settled deliberately, so it is
    reported here rather than rewritten.  **How a language
    spells its input bits is not universal** -- Grapheme reads ``%``/``A``
    and Fargo one number whose bits are the inputs -- so take the encoding
    from ``describe(language)["input_encoding"]`` rather than assuming
    ``"0"``/``"1"``; feeding the wrong alphabet is answered with a wrong
    result, not an error.

    ``timeout`` bounds execution wall-clock: after ``timeout`` seconds the
    run raises :class:`~esolangs.exceptions.ExecutionTimeoutError`, a
    :class:`HaltError` that is also a :class:`TimeoutError` -- catch that
    rather than the base, so a program halting on an invalid operation is
    not mistaken for the clock running out.  The guard uses ``SIGALRM``, so it
    requires a Unix main thread; elsewhere a ``timeout`` raises
    :class:`ValueError` and :meth:`Debugger.run`'s cooperative ``timeout``
    is the way to bound a run off the main thread.

    A program the interpreter cannot load raises
    :class:`~esolangs.exceptions.ProgramError`, so every deliberate failure
    here derives from :class:`~esolangs.exceptions.EsolangError`.
    """
    check_timeout(timeout)
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        # Checked here rather than inside ``_run`` so that every ValueError
        # from the run itself is the interpreter refusing the program, and
        # can be re-raised as one.
        raise ArgumentError(
            "the timeout guard uses SIGALRM and needs a Unix main thread"
        )
    # No guard on the lookup: ``resolve`` raises for a name outside the
    # registry, and every registered language has an interpreter, so a name
    # that reaches here is always in ``RUNNERS``.  The guard that used to sit
    # here re-raised the error ``resolve`` had already raised.
    name = resolve(language)
    module, split = RUNNERS[name]
    program = check_program(name, program, stdin)
    run_fn = importlib.import_module("esolangs.interpreters." + module).run
    io_obj = ScriptedIO(stdin)
    program_args: str | list[str] = program.splitlines() if split else program
    _warn_about_stdin(name, stdin)
    if seed is not None:
        run_fn = _seeded(name, run_fn, seed)
    try:
        _run(run_fn, program_args, io_obj, timeout)
    except RecursionError as exc:
        # An interpreter that recurses runs out of Python stack on a large
        # enough program, and the bare ``RecursionError`` was the only
        # exception in the package that escaped ``EsolangError``.  A sweep
        # written to the documented handler crashed on it.
        #
        # The message used to end "this interpreter cannot carry one that
        # large", which was not true: the limit is CPython's, and a caller
        # raising it made the same program run.  Qoibl was the language this
        # fired for and its tokenizer carries its own stack now, so the
        # remaining reach of this handler is any interpreter that recurses
        # per construct -- and the honest thing to tell that caller is where
        # the limit actually lives.
        raise InterpreterLimitError(
            f"the {name} interpreter recursed deeper than CPython's stack "
            f"limit allows on this program ({len(program)} characters); the "
            f"program is well formed, and sys.setrecursionlimit can raise "
            f"the limit if this interpreter's depth grows with program size"
        ) from exc
    except ValueError as exc:
        # The interpreters signal a malformed program with a plain
        # ValueError, one per language and each well worded.  Re-raising as
        # a ProgramError keeps those words and makes the package's promise
        # true: `except EsolangError` around user-supplied source now holds,
        # which is the handler an embedder actually writes.
        raise _keeping_output(ProgramError(str(exc)), io_obj) from exc
    except EsolangError as exc:
        # A halt, a timeout, an exhausted input: the program ran and stopped
        # badly, which is exactly the case where what it printed first is
        # worth keeping.  Re-raised as itself, so the class and everything
        # hanging off it are untouched, and a bare ``raise`` keeps the
        # traceback rather than starting a new one from here.
        _keeping_output(exc, io_obj)
        raise
    _warn_about_surplus(name, io_obj)
    return io_obj.getvalue()


def _warn_about_stdin(name: str, stdin: str) -> None:
    """Warn, once, if ``stdin`` contradicts what ``name`` declares it reads.

    A warning and not a refusal, for the reason :func:`run` gives: this
    executes arbitrary programs of a language, not only the generated
    truth-table ones, so a shape that looks wrong for a boolean program may
    be exactly what a hand-written one wants.  But silence was
    indistinguishable from correctness, and the checks already existed --
    the command line applied them and a Python caller got nothing.

    :func:`check_stdin` raises; this is the same judgement rendered as
    advice, so the strict path and the advisory path cannot disagree.
    """
    if not stdin:
        # An empty stdin is "I am not feeding this anything", which is a
        # legitimate thing to do with an arbitrary program -- the protocol
        # tests run sixty-nine programs that way.  Judging it by *shape*
        # warned about all of them.  The case that matters, a program that
        # reads anyway and gets a value, is decided after the run from the
        # counts, where there is no guessing: see below.
        return
    if not describe(name)["reads_input"]:
        # A language that embeds its inputs is *given* no stdin by design --
        # ``evaluate`` passes "" for all seventeen of them -- so there is
        # nothing here to be wrong.  ``check_stdin`` refuses the pair
        # outright, which is right for a caller who asked; as advice it was
        # just noise, and it fired once per row of every template language.
        return
    try:
        check_stdin(name, stdin)
    except EsolangError as exc:
        warnings.warn(str(exc), InputMismatchWarning, stacklevel=3)


def _seeded(name: str, run_fn: Callable[..., Any], seed: int) -> Callable[..., Any]:
    """Bind ``seed`` to ``run_fn``'s random source, refusing where there is none.

    Seven languages draw -- COD, Interprogck8, LaserFuck, Modulous,
    Painfuck, Super SNUSP and WII2D -- and their interpreters each take an
    ``rng``.  Nothing public passed one.  So LaserFuck's docstring said "a
    caller that needs a particular one passes an ``rng``" while ``run``,
    ``make_vm``, ``make_debugger``, ``evaluate`` and ``verify`` all had no
    parameter for it, and the only route was to import the private module
    and hand-build an ``IO``.  Ten identical runs of ``o+++.`` gave ``3``
    five times and nothing five times.

    ``make_vm`` was never affected: it always seeds, from the interpreter's
    own ``reproducible_seed``, which is why stepping was reproducible and
    running was not -- an asymmetry with no reason behind it.

    A seed for a language that draws nothing is refused rather than
    ignored.  Passing one means expecting the run to repeat, and it will
    repeat whatever happens here, so silence would be right by accident;
    but it would also hide the likelier reading, which is that the caller
    has the wrong language.
    """
    import inspect

    if "rng" not in inspect.signature(run_fn).parameters:
        raise ArgumentError(
            f"{name} draws no random values, so a seed has nothing to fix; "
            f"the languages that draw are COD, Interprogck8, LaserFuck, "
            f"Modulous, Painfuck, Super SNUSP and WII2D"
        )
    from esolangs.interpreters.randomness import Seeded

    return partial(run_fn, rng=Seeded(seed))


def _keeping_output[E: EsolangError](exc: E, io_obj: ScriptedIO) -> E:
    """Attach what the program printed before ``exc``, and return it.

    A note as well as the attribute: the attribute is what the CLI prints,
    and the note is for anyone reading a traceback who would otherwise
    conclude the program produced nothing at all.
    """
    written = io_obj.getvalue()
    if written:
        exc.partial_output = written
        exc.add_note(f"the program printed {written[:200]!r} before this")
    return exc


def _warn_about_surplus(name: str, io_obj: ScriptedIO) -> None:
    """Warn if the program left supplied input unread.

    Six lines fed to a three-input program answered the first three and
    ignored the rest, with nothing to show it had happened -- while feeding
    too *few* had always said "2 lines supplied, read 3".  The count was
    there the whole time; only the other direction was never checked.

    It cannot be an error: reading less than it is given is what a great
    many perfectly good programs do.  The arity mismatch it usually means
    is the thing worth naming.
    """
    read, supplied = io_obj.reads, io_obj.supplied
    if supplied > read > 0:
        warnings.warn(
            f"{name} read {read} of the {supplied} lines supplied on stdin; "
            f"the rest were ignored -- is this the right arity?",
            InputMismatchWarning,
            stacklevel=3,
        )
    if io_obj.past_end and describe(name)["eof_is_a_value"]:
        # The exact signal, and the one worth having most: this run asked
        # for input that was not there and *kept going*.  Only the seven
        # languages ``eof_is_a_value`` marks reach here -- for the other
        # forty-five the read raises and nothing below runs -- and this is
        # the wrong answer those seven produce in silence: an underfed
        # program answers a different row, and a program given no stdin at
        # all answers row 0.
        #
        # Counted rather than inferred from ``supplied == 0``: that missed
        # the underfeed case, where some input was supplied and the reads
        # past the end came after it.
        #
        # Gated on ``eof_is_a_value`` because reading past the end is not
        # always a mistake: Suffolk's generated programs end *by* running
        # out of input -- it is that language's documented stop, and it
        # halts rather than taking a value -- so counting the read alone
        # warned about every correct Suffolk run there is.
        warnings.warn(
            f"{name} read past the end of its input {io_obj.past_end} time(s) "
            f"and took a value each time rather than stopping; the answer is "
            f"for the row that implies, not the one the input names",
            InputMismatchWarning,
            stacklevel=3,
        )


def _run(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float | None,
) -> None:
    """Run ``run_fn``, applying the wall-clock ``timeout`` guard when set.

    Whether a timeout *can* be applied is settled in :func:`run` before this
    is reached, so there is no third case here.
    """
    if timeout is None:
        run_fn(program, io_obj)
    else:
        _run_timed_signal(run_fn, program, io_obj, timeout)


def _run_timed_signal(
    run_fn: Callable[..., Any],
    program: str | list[str],
    io_obj: ScriptedIO,
    timeout: float,
) -> None:
    """Run ``run_fn`` under a ``SIGALRM`` wall-clock guard (main thread only)."""
    # Whether an arriving alarm still means "the run is overrunning".  The
    # handler fires between two bytecodes -- *any* two, including the ones
    # in the cleanup below -- so without this it could raise into its own
    # teardown and skip the rest of it, leaving the timer armed and the old
    # handler unrestored.  A later alarm then arrived with SIGALRM's default
    # disposition, which is to terminate the process: a short timeout killed
    # the interpreter outright roughly one run in three, no traceback and no
    # exception, which is the worst way for a guard against hanging to fail.
    #
    # Clearing it is a single store, so the cleanup cannot be interrupted by
    # the thing it is cleaning up.
    armed = True

    def _timeout_handler(_signum: int, _frame: object) -> None:
        # coverage cannot trace a raise inside a signal handler
        if not armed:  # pragma: no cover - a late alarm, not an overrun
            return
        raise ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    # The caller's alarm, saved and put back.  Arming our own cancels
    # theirs, so a ``signal.alarm(30)`` set before a timed run came back
    # with zero seconds left and would never have fired.
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    pending = signal.setitimer(signal.ITIMER_REAL, timeout)[0]
    try:
        run_fn(program, io_obj)
    finally:
        armed = False
        # Ignore the signal *first*, then disarm, then put the old handler
        # back.  Disarming first looks sufficient and is not: an alarm can
        # already be in flight when the run finishes, and if it is delivered
        # after ``old`` is restored -- and ``old`` is the default
        # disposition -- SIGALRM's default action is to **terminate the
        # process**.  It did: a very short timeout killed the interpreter
        # outright about one run in ten, no traceback, no exception, exit
        # 142, which is the worst way for a guard against hanging to fail.
        #
        # ``SIG_IGN`` is installed at the C level, so an alarm arriving in
        # this window is discarded rather than reaching that default.
        #
        # One window remains by design: an alarm delivered between
        # ``run_fn`` returning and the line below still finds the custom
        # handler and raises, reporting a timeout for a run that had just
        # finished.  That is an exception rather than a death, and closing
        # it would need the handler to know whether the run was still going
        # -- a flag read from a signal handler, to save a caller from a
        # timeout they did set.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        if pending:
            # Whatever was left of the caller's alarm, resumed.  Not exact
            # -- the run's own duration is not deducted -- but a timer that
            # fires late is a great deal better than one silently cancelled.
            signal.setitimer(signal.ITIMER_REAL, pending)


def describe(language: str) -> dict[str, object]:
    """Return a structured description of ``language``.

    The summary carries the ``state_model`` (derived from the
    interpreter's module family), whether the language has a
    ``boolean_generator``, whether that generator returns a template rather
    than a runnable program (``parameterized``) and so takes no stdin
    (``reads_input``), what a width does to it (``width_effect``), its
    ``examples``, and its ``wiki_url``.

    ``width_effect`` is what a ``width`` actually does to this language,
    and it is the one of the two width keys to read:

    * ``"layout"`` -- the generator is handed the width and builds a shape
      to fit.  A *hint*, not a bound: LaserFuck asked for 10 gives 18, and
      asked for 200 gives 56, because it folds straight runs rather than
      breaking lines.
    * ``"wrap"`` -- the finished program is reflowed between whole tokens,
      so the width is honoured except by a single token longer than it.
    * ``"none"`` -- the width is ignored, because the language's newlines
      are semantic or the language rejects them outright.  This is the one
      worth knowing, because it was a silent no-op.

    ``width_aware`` answers the narrower question ``width_effect ==
    "layout"`` -- whether the *generator* takes the width itself -- and is
    exactly that, for every language.  It is the older key, and on its own
    it could not tell "reflowed afterwards" from "ignored": both are
    ``False``, and those two groups are most of the registry.  A reader hit
    that and said so.  The split is counted in
    ``test_all_three_effects_are_represented`` rather than here.

    Neither key promises the result fits: see :func:`generate` on why a
    width is a request.  Both ``layout`` languages can still overrun.  This
    used to name LaserFuck as the one that does, which was the wrong one to
    single out: Streetcode overruns at more widths and by a wider margin.
    No numbers here -- they are what
    ``test_both_width_aware_generators_can_overrun`` measures, and a count
    in prose is a second copy of something a run can answer.

    ``self_halts``, ``dumps_on_the_post_halt_step``, ``steppable_to_answer``
    and ``eof_is_a_value`` are the machine traits, merged in from
    :func:`~esolangs.vm.machine_traits` and documented there rather than
    copied to here.

    Two keys exist because assuming their default is answered with a wrong
    result rather than an error, which is the failure worth spending an API
    on.  ``input_encoding`` is the ``(zero, one)`` pair the language spells
    its input bits with -- ``("0", "1")`` almost everywhere, ``("%", "A")``
    for Grapheme, whose generator reads a 1 only from a line beginning
    ``A``.
    For an ``answer_mode`` of ``"termination"``, ``answer_encoding`` is the
    *polarity* -- ``("halts", "diverges")`` -- so which way the answer goes
    is data rather than something to read out of the prose.  Otherwise
    ``answer_pattern`` and ``answer_encoding`` are how :func:`read_answer`
    finds the answer: the regex whose first group holds it (empty means the
    last non-whitespace character) and the ``(zero, one)`` pair that
    position is spelled with.  They mirror ``input_shape`` and
    ``input_encoding`` on the way in.  **They describe the raw output, not
    what :func:`read_answer` gives back** -- that is always ``"0"`` or
    ``"1"`` -- so A Painter Ant's ``("o", "@")`` is the mark in its grid,
    not a value you will be handed.

    ``answer_mode`` is the same fact in a form you can branch on:
    ``"output"`` (the program prints the answer -- read it as the last
    non-whitespace character, since a few languages terminate their output
    with a newline), ``"termination"`` (it
    halts for a 0 and loops forever for a 1, so a timeout *is* the 1), or
    ``"dump"`` (it prints its whole final state and the answer sits at a
    fixed place in it).  ``answer_convention`` is the prose beside it, and
    names that place.  Both exist because the prose alone could not be
    consumed: a sweep that hardcoded two of the dumps and forgot a third
    reported a passing language as broken.  The prose says how to read the
    answer out of a program that does not simply print it: several dump
    their whole state and the answer sits at a fixed place in it, three
    answer by *terminating* (they halt for a 0 and loop forever for a 1, so
    a timeout is the 1), and Fargo reads one number whose bits are the
    inputs rather than a line per bit.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    module = RUNNERS.get(name)
    family = module[0].split(".")[0] if module else None
    stem = example_stems().get(lang.id, lang.id)
    # Absolute.  These were relative to the repository root, which made the
    # recipe this package advertises -- ``run(lang, Path(describe(lang)
    # ["examples"][0]))`` -- work from one directory and nowhere else: a
    # ``chdir`` away it is ``cannot read examples/boolean/brainfuck.txt``,
    # and for anyone who pip-installed there is no such directory at all.
    examples = sorted(str(p) for p in _EXAMPLES.glob(f"*/{stem}.txt"))
    parameterized = lang.id in parameterized_ids()
    example = _example_for(lang.id)
    return {
        "name": name,
        "id": lang.id,
        "state_model": _STATE_MODELS.get(family) if family else None,
        "interpreter": lang.interpreter,
        "boolean_generator": lang.boolean is not None,
        "parameterized": parameterized,
        "reads_input": lang.boolean is not None and not parameterized,
        # Derived, not recomputed: this was a second copy of the very
        # expression _width_effect() evaluates, so the two could drift into
        # disagreeing about the same language.
        "width_aware": _width_effect(lang) == "layout",
        "width_effect": _width_effect(lang),
        "input_encoding": example.alphabet if example else ("0", "1"),
        "input_shape": example.input_shape if example else "line_per_bit",
        "answer_mode": example.answer_mode if example else "output",
        "answer_pattern": example.answer_pattern if example else "",
        "answer_encoding": example.answer_values if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        **machine_traits(name),
        "examples": examples,
        "wiki_url": wiki_url(name),
    }


def _width_effect(lang: Any) -> str:
    """Return what ``width`` actually does to this language's program.

    ``width_aware`` answered a narrower question than anyone was asking --
    whether the *generator* takes the width itself -- so it was ``False``
    for Sophie, whose program is reflowed to the width afterwards, and
    ``False`` for Clockwise, which ignores the width entirely.  One flag,
    three behaviours, and no way to tell them apart without reading the
    source; a reader said so in as many words.

    * ``"layout"`` -- the generator is handed the width and builds a shape
      to fit.  A *hint*, not a bound: LaserFuck asked for 10 gives 18, and
      asked for 200 gives 56, because it folds straight runs rather than
      breaking lines.
    * ``"wrap"`` -- the finished program is reflowed between whole tokens,
      so the width is honoured except by a single token longer than it.
    * ``"none"`` -- the width is ignored, because the language's newlines
      are semantic or it rejects them outright.  This is the one worth
      knowing: it was a silent no-op.
    """
    from esolangs.tools.wrap import WRAPPERS

    # One expression rather than an early return for the generator-less
    # case: every registered language has a generator, so that return was a
    # line no input could reach.
    if lang.boolean is not None and _takes_width(lang.boolean):
        return "layout"
    return "wrap" if lang.id in WRAPPERS else "none"


def spec(language: str) -> str:
    """Return the interpreter's own description of ``language``.

    Every one of the 69 interpreters carries a module docstring giving the
    command table and -- more useful -- where this implementation *differs*
    from the wiki page, which is the thing no wiki page can tell you.  They
    run from 200 to 9700 characters and the median is around 2400, so they
    are the best documentation the package has for writing a program.

    Nothing pointed at them.  ``docs/`` has a capability matrix and two
    per-language notes, neither a spec; ``describe`` reported
    ``interpreter: stack_based.unsquare`` with no hint that it names an
    importable module whose ``__doc__`` is what you want; and every CLI
    subcommand except ``run`` and ``debug`` is about truth tables.  A
    reader who came to this package with a program rather than a truth
    table found the content by guessing at ``importlib``.

    Read rather than stored, so it cannot drift from the interpreter it
    describes.
    """
    name = resolve(language)
    module = RUNNERS[name][0]
    interpreter = importlib.import_module("esolangs.interpreters." + module)
    return (interpreter.__doc__ or "").strip()


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    truth_table: str | None = None,
) -> str:
    r"""Return the stdin that feeds ``bits`` to a ``language`` program.

    Most languages read one ``0``/``1`` line per input, and for those this
    is just ``"".join(f"{bit}\\n" ...)``.  Four are not most languages, and
    every one of them fails *silently* when fed the obvious thing:

    * **Grapheme** reads a whole line and counts any non-empty string as
      true, so its bits are spelled ``%`` and ``A``; a ``"0"`` line is a 1.
    * **Clockwise** packs seven bits per character and reads them in one
      go, so they go on a single line with no separator.
    * **Fargo** reads one *number* before the program starts and indexes
      its bits, so the input is the row index.
    * **Taglate** takes a line per bit, but an odd input count above one is
      padded with a leading zero it consumes like any other digit, so an
      n=3 program wants four lines.

    Each of those was found by a reader feeding digits a line at a time and
    getting a plausible wrong answer back -- or, for Taglate at three
    inputs, an input-exhausted error.  The knowledge existed, in a table in
    the test suite; this is that table, shipped, so the answer is available
    to the callers who need it rather than to the suite alone.

    ``describe(language)["input_shape"]`` and ``["input_encoding"]`` report
    the same facts one at a time, for a caller who wants to branch on them.

    ``truth_table`` is optional and is the table the program was generated
    from; passing it checks that ``bits`` is the width that program reads.
    Worth having because this is the one function whose whole purpose is to
    stop a silent mis-encoding, and it could not catch the *simplest* one:
    it takes no arity, so three bits aimed at a four-input program were
    encoded as cheerfully as four.  For Fargo that means
    ``encode_inputs("Fargo", [1, 0, 1])`` emits row ``5`` of a table with
    four rows, and the program answers it without complaint.

    How far the underfed program gets before anything notices was measured
    rather than assumed, because the sentence here used to assume it and
    was wrong twice over -- it named the wrong group of languages *and* the
    wrong outcome.  Of the fifty-two that read stdin, 43 raise
    :class:`~esolangs.exceptions.InputExhaustedError`, 6 answer a different
    row in silence, 2 produce output :func:`read_answer` refuses, and one
    raises about its own arithmetic.  See :func:`run` for the split and
    ``describe(language)["eof_is_a_value"]`` for the flag.

    ``truth_table`` stays optional and will: the CLI's ``encode`` cannot
    pass it, since it runs before any table exists
    (``esolangs encode Taglate 101``).  Requiring it would break a real
    caller to move a check that :func:`evaluate` and :func:`verify` already
    make on every row.
    """
    # Every registered language has a committed example, so the lookup
    # always finds one; ``example_stems`` covers all 69 and a test pins that.
    name = resolve(language)
    example = _example_for(LANGUAGES[name].id)
    if example.fill is not None:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin, so "
            f"there is nothing to encode; pass the bits to instantiate() "
            f"instead"
        )
    # Checked for the same reason ``instantiate`` checks it: a 2 or a "1"
    # is not caught downstream.  It encodes as a 1 and the program answers
    # a different row of the table, which is the wrong answer arriving with
    # no sign that anything went astray.
    bits = check_bits(bits, "bits")
    if truth_table is not None:
        from esolangs.tools.boolean.helpers import _validate_truth_table

        if not isinstance(truth_table, str):
            raise TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            )
        arity = _validate_truth_table(truth_table)
        if len(bits) != arity:
            raise ArgumentError(
                f"that table has {arity} input{'' if arity == 1 else 's'}, "
                f"but {len(bits)} bit{' was' if len(bits) == 1 else 's were'} "
                f"given; a {name} program built from it reads {arity}"
            )
    if example.input_shape == "row_index":
        row = sum(bit << (len(bits) - 1 - i) for i, bit in enumerate(bits))
        return f"{row}\n"
    zero, one = example.alphabet
    padded = [0, *bits] if example.ghost_digit and len(bits) % 2 and bits[1:] else bits
    digits = [one if bit else zero for bit in padded]
    if example.input_shape == "one_line":
        return "".join(digits)
    return "".join(f"{digit}\n" for digit in digits)


#: The three ways a language hands back its answer, as data.  The closed set
#: a generic caller branches on, exported for the same reason
#: :data:`STOP_REASONS` and :data:`TERMINATION_OUTCOMES` are: a verifier that
#: branches on ``answer_mode`` otherwise has to spell ``"termination"`` as a
#: magic string, which is the one thing those two constants exist to stop.
ANSWER_MODES: tuple[str, ...] = ("output", "dump", "termination")

#: The four stdin layouts, likewise.  ``line_per_bit`` is the rule;
#: ``line_per_bit_padded`` prepends a zero line for an odd input count,
#: ``one_line`` puts every bit on one line, and ``row_index`` sends a single
#: decimal number whose bits are the inputs.
INPUT_SHAPES: tuple[str, ...] = (
    "line_per_bit",
    "line_per_bit_padded",
    "one_line",
    "row_index",
)


def check_stdin(language: str, stdin: str, truth_table: str | None = None) -> None:
    """Refuse ``stdin`` that cannot be what ``language`` wants to read.

    The judge the CLI has always applied, moved here so Python callers get
    it too -- it was the one place the API was strictly weaker than the
    command line, and the sharp edges it guards are the ones every blind
    reader of this package has found: a ``0``/``1`` line fed to Grapheme,
    several lines fed to Clockwise, anything but a number fed to Fargo.

    Raises :class:`~esolangs.exceptions.ArgumentError`.  A *raise* rather
    than a warning because a caller reaching for this function has asked
    to be told; :func:`run` itself still executes whatever it is given,
    since it runs arbitrary programs of a language and not only the
    generated truth-table ones, and a shape this rejects may be exactly
    what a hand-written program wants.

    ``truth_table`` is optional and adds the count: with it, stdin must
    hold as many bits as the program reads, which catches the *surplus*
    case too.  Six lines fed to a three-input program answered the first
    three and ignored the rest, at exit 0 -- and the count was available
    all along, since the too-few case has always reported "2 lines
    supplied, read 3".

    Every check reads a :func:`describe` field, so a language with a new
    shape is covered by declaring it.
    """
    facts = describe(language)
    name = str(facts["name"])
    if not facts["reads_input"]:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin; "
            f"there is nothing to check"
        )
    if not isinstance(stdin, str):
        raise ArgumentError(f"stdin must be a string, got {type(stdin).__name__}")
    shape = str(facts["input_shape"])
    zero, one = cast("tuple[str, str]", facts["input_encoding"])
    # ``splitlines``, which is what :class:`ScriptedIO` uses to cut stdin
    # into the lines it hands over -- so this counts exactly the lines the
    # program will read.  It was ``stdin.strip().split("\n")``, and the
    # ``strip`` silently dropped a *leading or trailing blank line*: neither
    # counted nor alphabet-checked here, while the interpreter consumed it
    # as an input bit.  ``run("brainfuck", xor, "\n\n")`` answered 1 where
    # XOR of two zeros is 0, with no warning, because this function had
    # already decided there was nothing there.
    lines = stdin.splitlines()
    wanted = None
    if truth_table is not None:
        wanted = _validate_shape_for_evaluate(truth_table)
        if shape == "line_per_bit_padded" and wanted % 2 and wanted > 1:
            # Taglate's pad is a digit the program reads like any other, so
            # an odd input count above one costs an extra line.  Read off
            # the shape, which is where that fact already lives.
            wanted += 1

    if shape == "row_index":
        if len(lines) != 1 or not lines[0].isdigit():
            raise ArgumentError(
                f"{name} reads one decimal row index, but stdin is {stdin.strip()!r}"
            )
        if len(lines[0]) > 1 and lines[0][0] == "0":
            # A decimal row index never has a leading zero, so this is
            # almost always the bit string typed out: `0010` fed to a
            # 16-row program parses as *ten* and answers row 10 instead of
            # row 2.  Neither a count nor a range check catches it -- ten
            # is one line and is in range -- and no table is needed to see
            # it, which is why the rule is shaped this way.
            # The bit-string reading is only offered when the digits *are*
            # bits.  ``int(x, 2)`` on ``'02'`` raises, so the message meant
            # to explain a leading zero crashed on one -- a traceback out
            # of the function whose whole job is to refuse cleanly.
            if not set(lines[0]) - {"0", "1"}:
                raise ArgumentError(
                    f"{name} reads one decimal row index, and {lines[0]!r} "
                    f"has a leading zero -- if those are the input bits, the "
                    f"index is {int(lines[0], 2)}: "
                    f"`esolangs encode {name} {lines[0]}`"
                )
            raise ArgumentError(
                f"{name} reads one decimal row index, and {lines[0]!r} has a "
                f"leading zero, which a decimal index never has"
            )
        if wanted is not None and int(lines[0]) >= 2**wanted:
            raise ArgumentError(
                f"{name} row index {lines[0]} is out of range for a "
                f"{wanted}-input program (0..{2**wanted - 1})"
            )
        return
    if shape == "one_line":
        if len(lines) != 1:
            raise ArgumentError(
                f"{name} wants every bit on one line, but stdin is {len(lines)} line(s)"
            )
        if wanted is not None and len(lines[0]) != wanted:
            raise ArgumentError(
                f"{name} wants {wanted} bits on its one line, got {len(lines[0])}"
            )
        return
    stray = [line for line in lines if line not in (zero, one)]
    if stray:
        # Phrased around the alphabet rather than the stray count, because
        # the useful half is what this language *does* spell its bits with:
        # a reader who fed 0/1 lines to Grapheme needs '%' and 'A', not a
        # tally of how many lines were wrong.
        raise ArgumentError(
            f"{name} spells its bits {zero!r} and {one!r}, and {len(stray)} "
            f"stdin line(s) are outside that -- the first is {stray[0]!r}"
        )
    if wanted is not None and len(lines) != wanted:
        raise ArgumentError(
            f"{name} reads {wanted} line(s) for this table, but stdin has {len(lines)}"
        )


def read_answer(language: str, output: str) -> str:
    """Return the answer bit a ``language`` program's ``output`` carries.

    The counterpart to :func:`encode_inputs`.  Most languages print the
    answer and this is the last non-whitespace character; the six that dump
    their whole final state instead need to be told where in the dump it
    sits, and two of those genuinely differ -- RAM0's answer is its ``z``
    register, three lines above the end, and A Painter Ant marks the ant's
    own cell ``o`` on black and ``@`` on white rather than printing a digit.
    ``describe(language)["answer_pattern"]`` is the same fact as data.

    This exists because ``answer_mode`` alone was not enough: it said *that*
    a language dumps without saying *where*, so a verifier still had to read
    the prose, and one that hardcoded two of the dumps and forgot a third
    reported a passing language as broken.  The other four dumps happen to
    end on the answer, which is what makes the gap easy to miss.

    A language whose answer is its *termination* raises
    :class:`~esolangs.exceptions.ArgumentError`: 123, ArrowQueue and Point
    Break halt for a 0 and loop forever for a 1, so their output is not the
    answer and reading one out of it would invent a result.  Bound the run
    and catch :class:`~esolangs.exceptions.ExecutionTimeoutError` instead.
    """
    name = resolve(language)
    if not isinstance(output, str):
        raise ProgramError(f"output must be a string, got {type(output).__name__}")
    example = _example_for(LANGUAGES[name].id)
    if example.answer_mode == "termination":
        raise ArgumentError(
            f"{name} answers by terminating, not by printing: run it under a "
            f"timeout and read a caught ExecutionTimeoutError as the 1"
        )
    if example.answer_pattern:
        found = re.findall(example.answer_pattern, output)
        raw = found[-1] if found else ""
    else:
        raw = output.strip()[-1:]
    zero, one = example.answer_values
    if raw == one:
        return "1"
    if raw == zero:
        return "0"
    # For a pattern language the regex used to be the *whole* explanation,
    # which is the right thing to hand a maintainer and nothing at all to
    # hand a reader wondering where the answer was supposed to be.  The note
    # is the plain-language half and already exists; the pattern follows it
    # in parentheses, so neither reader loses.
    where = "in its final state" if example.answer_pattern else "as the last character"
    # The note whenever there is one, not just for the two pattern
    # languages: Back, Minsky Swap and LaserFuck dump their state and are
    # read by last character, so "as the last character" is a true account
    # of the mechanism and no account at all of where the answer lives.
    detail = f" -- {example.note}" if example.note else ""
    if example.answer_pattern:
        detail += f" (matched with {example.answer_pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )


#: The two outcomes an ``answer_mode`` of ``"termination"`` reports, in the
#: order ``describe(...)["answer_encoding"]`` gives them: index 0 is the
#: answer 0 and index 1 the answer 1, so ``encoding.index("diverges")`` is
#: which way round the polarity goes.
#:
#: Exported because a caller writing the generic round trip needs the
#: vocabulary and there was nowhere to read it: one reader hand-copied this
#: tuple into their own code and said so, which is the same gap
#: :data:`STOP_REASONS` was added to close for the debugger.
TERMINATION_OUTCOMES: tuple[str, str] = ("halts", "diverges")


class _Default:
    """The "argument was not given" marker for :func:`evaluate`.

    Needed because ``None`` already means something: in :func:`run` it means
    *unbounded*, and a reader found that the same word meant "use the
    default" here -- so there was no value at all that turned the alarm off,
    and the two headline convenience functions could not be called from a
    thread.  Now omitting the argument takes the defaults and passing
    ``None`` means what it means everywhere else.
    """

    def __repr__(self) -> str:
        """Render as ``<default>`` in a signature rather than as an address.

        ``help(esolangs.evaluate)`` showed ``timeout: float |
        esolangs._Default | None = <esolangs._Default object at
        0x105fa12b0>`` -- an address, in the documentation, changing every
        run.  A reader has to work out that the sentinel means "omit it".
        """
        return "<default>"


_DEFAULT = _Default()

#: A termination-answering language proves a 1 by *not* halting, so
#: :func:`evaluate` pays this once for every such row.  Three languages
#: carry that convention, so the floor is real and small.
_TERMINATION_TIMEOUT = 5.0

#: The bound on an ordinary row.  Generous: it exists to stop a hang, not
#: to hold anything to a schedule.
_ROW_TIMEOUT = 30.0


def evaluate(
    language: str,
    truth_table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
) -> str:
    """Return the truth table a generated ``language`` program *actually* computes.

    Generates the program for ``truth_table``, runs it on every row of its
    input space, and returns the answers as a binary string of the same
    length.  So the round trip this whole package is for is one call, and
    ``evaluate(lang, table) == table`` is the question everything else here
    exists to make answerable -- which is :func:`verify` below.

    This is shipped because it kept being rewritten.  Two independent
    readers given nothing but the public API wrote this same function as
    the first thing they did with it, and the test suite had a third copy;
    the interesting part is that all three came out with **no per-language
    branches at all**.  Every decision it makes reads a
    :func:`describe` field:

    * ``parameterized`` picks :func:`instantiate` over :func:`encode_inputs`
      -- whether the bits go into the program or into its stdin;
    * ``answer_mode`` picks :func:`read_answer` over a bounded run, since
      three languages answer by not halting and have no output to read;
    * ``answer_encoding`` gives *which way* that goes, rather than leaving
      "halting means zero" to be read out of the prose.

    ``width`` is passed straight through to the build, so this answers the
    question a round trip is usually written for: *does the program still
    compute its table once it has been wrapped?*  Hand-rolling that meant
    reimplementing the loop below and losing the divergence proof with it,
    which turns three languages from milliseconds into a full bound per
    1-row.  A width is a request rather than a promise -- see
    :func:`generate` -- and ``width_effect`` on :func:`describe` says which
    of the three things it does to a given language, including the 38 it
    does nothing to.

    ``timeout`` bounds each row, and for most languages that is all it
    does.  **The three that answer by not terminating do not pay it**:
    their rows are settled by a repeated machine state, which proves the
    loop in microseconds, and the bound is only the backstop for a program
    that diverges by growing instead of repeating.  So a whole table from
    one of them comes back in milliseconds, not in five seconds per 1.

    This said the timeout "is paid on every 1", which was true when it was
    written and stopped being true in the same change that added the
    proof -- while :meth:`~esolangs.debugger.Debugger.snapshot`'s docstring
    described the new mechanism.  Two docstrings in one package disagreeing
    about how something works is worse than either being merely out of
    date, so: the proof is the mechanism, and this is the backstop.

    Omitting the argument takes the defaults (30 seconds for an ordinary
    row, 5 for a termination one); passing ``None`` explicitly means
    *unbounded*, as it does in :func:`run`, which is what makes these
    callable off the main thread.
    """
    # Checked here, not only inside ``run``: the termination path drives the
    # machine itself and never reaches ``run``, so a bound too small to
    # service was refused for sixty-six languages and silently read as
    # "diverges" for the other three -- the same argument answering a
    # different table depending on which kind of language it was.
    if not isinstance(timeout, _Default):
        check_timeout(timeout)
    facts = describe(language)
    name = str(facts["name"])
    inputs = _validate_shape_for_evaluate(truth_table)
    terminating = facts["answer_mode"] == "termination"
    bound: float | None
    if isinstance(timeout, _Default):
        bound = _TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT
    else:
        # An explicit ``None`` means *unbounded*, the way it does in
        # :func:`run` -- and it is the escape hatch for a thread, since the
        # wall-clock guard is a ``SIGALRM`` and needs the main one.  Safe
        # here in a way it would not be for arbitrary programs: every
        # program this runs is one it generated, and the three that diverge
        # are settled by a repeated state rather than a clock.
        bound = timeout
    # The width goes to whichever call builds the runnable text: for a
    # template that is ``instantiate`` below, since a ``{Xi}`` slot is not a
    # token any wrapper knows and a break inside one destroys it.
    program = generate(name, truth_table, None if facts["parameterized"] else width)
    if terminating:
        # Which of halting and diverging means 1, as data.  It is
        # ``("halts", "diverges")`` for all three, but reading the order
        # rather than assuming it is what keeps this branch language-free.
        encoding = list(facts["answer_encoding"])  # type: ignore[call-overload]
        diverges_is = str(encoding.index("diverges"))
        halts_is = str(encoding.index("halts"))
    answers = []
    for row in range(len(truth_table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, bits, width), ""
        else:
            source, stdin = program, encode_inputs(name, bits, truth_table)
        try:
            if terminating:
                answers.append(
                    _terminates(name, source, stdin, bound, halts_is, diverges_is)
                )
            else:
                answers.append(read_answer(name, run(name, source, stdin, bound)))
        except EsolangError as exc:
            # Which row, as a note rather than a new exception: the classes
            # here do not share a constructor -- ``InputExhaustedError``
            # takes two counts and builds its own message -- so re-raising
            # with a longer string would mean knowing all of them.
            #
            # Without this a failure on a 1024-row table said only that
            # something exceeded the bound, and "row 0 is pathological" and
            # "row 900 is" are different problems with the same message.
            # The bits are here too, since they are what makes the row
            # reproducible in one call.
            exc.add_note(
                f"while evaluating row {row} of {len(truth_table)} "
                f"(inputs {''.join(str(b) for b in bits)}), after "
                f"{len(answers)} row{'' if len(answers) == 1 else 's'} "
                f"answered {''.join(answers) or '(none)'}"
            )
            raise
    return "".join(answers)


def _terminates(
    name: str,
    source: str,
    stdin: str,
    bound: float | None,
    halts: str,
    diverges: str,
) -> str:
    """Return this row's answer for a language that answers by terminating.

    A *proof* where one is available.  These three answer 1 by never
    stopping, so the obvious reading is "wait and see", and waiting is what
    this did: five seconds per 1-row, twenty seconds per language at two
    inputs and forty at three, which is most of what a sweep over the
    registry cost.

    A deterministic machine that returns to a state it has already been in
    will do the same thing again forever, so a repeated snapshot settles it
    exactly -- and settles it in milliseconds, because these programs
    revisit a state within a hundred steps.  The clock stays as the
    backstop :func:`~esolangs.vm.run_until_halt_or_cycle` asks for: it
    proves *cycles*, and a loop that grows without bound never repeats a
    state, so a program that does that still has to be timed out.

    This was declined two rounds ago, when the proposal was a step budget.
    That refusal was right and this is not the same thing: a budget guesses
    that a program still running will never stop, and can be wrong about a
    slow one; a repeated state is a fact about every future step.
    """
    from esolangs.vm import run_until_halt_or_cycle

    machine = make_vm(name, source, stdin)
    # A box, because ``_run`` exists to apply the timeout and discards what
    # it drove -- which is right for ``run``, whose result is the io buffer.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        verdict.append(run_until_halt_or_cycle(machine))

    try:
        _run(_drive, source, ScriptedIO(""), bound)
    except ExecutionTimeoutError:  # pragma: no cover - see below
        # No cycle inside the bound: unbounded growth, or simply slow.  The
        # old answer, and still the right one.
        #
        # Not reached by any table the suite runs, and not for want of
        # trying to: these programs revisit a state inside a hundred steps,
        # so even a one-millisecond bound proves the cycle before the clock
        # can fire.  It stays because the detector only proves *cycles* --
        # a loop that grows without bound never repeats a state -- and its
        # own docstring asks callers to keep a clock for that case.
        return diverges
    except InputExhaustedError:  # pragma: no cover - see below
        # Reading past the end is how some of these stop; that is a halt.
        #
        # Not reachable through :func:`evaluate`, which encodes every row
        # itself and so never underfeeds one -- kept because this is the
        # one ending a *cycle* search cannot see coming, and a future
        # caller passing its own stdin would hit it.
        return halts
    return halts if verdict and verdict[0] else diverges


def verify(
    language: str,
    truth_table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
) -> bool:
    """Whether a generated ``language`` program really computes ``truth_table``.

    :func:`evaluate` with the comparison done, for the common case where
    only the verdict is wanted.  Use ``evaluate`` when a mismatch needs
    locating: it returns the table the program computed, so the rows that
    disagree are visible rather than summarized to ``False``.
    """
    return evaluate(language, truth_table, timeout, width) == truth_table


def _validate_shape_for_evaluate(truth_table: str) -> int:
    """Return the input count of ``truth_table``, refusing a malformed one.

    :func:`generate` validates it too, a few lines later, but the row loop
    needs the arity *before* that happens -- and a bad table reported by
    whichever generator ran first named the generator rather than the table.
    """
    from esolangs.tools.boolean.helpers import _validate_truth_table

    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    return _validate_truth_table(truth_table)


def _example_for(language_id: str) -> Any:
    """Return the committed boolean example for ``language_id``, or None.

    Deferred like the rest of the example lookups: ``examples`` imports the
    registry, so importing it at module scope would close a cycle.
    """
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    stem = example_stems().get(language_id)
    return BOOLEAN_EXAMPLES.get(stem) if stem is not None else None


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
