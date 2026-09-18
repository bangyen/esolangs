"""Public API for the esolangs package.

``generate`` produces a program computing a truth table; ``instantiate``
fills a parameterized generator's input runs; ``run`` executes a program;
``make_vm`` and ``make_debugger`` step one; ``describe`` and
``list_languages`` summarize the registry.  ``encode_inputs`` and
``read_answer`` feed a program and judge what it printed; ``check_stdin``,
``check_program`` and ``check_runnable`` apply the checks before anything
runs; ``evaluate`` and ``verify`` are the whole round trip; ``spec`` is the
interpreter's own description of a language.

Names resolve case-insensitively (:func:`esolangs.registry.resolve`), and
every deliberate error derives from :class:`~esolangs.exceptions.EsolangError`.
"""

import importlib
import os
import pathlib
import re
import signal
import threading
import warnings
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any, TypedDict, cast

from esolangs._answers import (
    check_stdin,
    encode_inputs,
    read_answer,
)
from esolangs._describe import (
    _EXAMPLES,
    LanguageInfo,
    describe,
    list_languages,
    spec,
)
from esolangs._evaluate import _Default, evaluate, verify
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
    ProgramNotFoundError,
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
    recover_setters,
    render_template,
    resolve,
    template_body,
    template_char,
    wiki_url,
)
from esolangs.tagged import _Tagged, _Template

# Imported private: it takes a *generator function*, not a language name, so
# a caller reaching for ``esolangs.takes_width("LaserFuck")`` got False for
# every language in the registry, contradicting both its own docstring and
# ``describe(...)["width_aware"]`` -- which is the question they were asking.
from esolangs.tools.wrap import WRAPPERS, wrap_program
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.vm import VM, machine_traits, make_vm


#: From the installed distribution (a hand-kept copy said 0.1.0 at 0.2.0);
#: the fallback covers an uninstalled tree.  Read on first access, not
#: import: ``importlib.metadata`` was 23ms of the 56ms import (PEP 562).
def __getattr__(name: str) -> str:
    """Resolve ``__version__`` lazily; everything else is a normal miss."""
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib.metadata

    try:
        version = importlib.metadata.version("esolangs")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - CI installs
        # A source tree that was never installed.
        version = "0.0.0+unknown"
    globals()["__version__"] = version
    return version


#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "STOP_REASONS",
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
    "LanguageInfo",
    "ProgramError",
    "ProgramNotFoundError",
    "StopReason",
    "TemplateError",
    "TruthTableError",
    "UnknownLanguageError",
    "check_program",
    "check_runnable",
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
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)


def generate(language: str, truth_table: str, width: int | None = None) -> str:
    """Return a program in ``language`` computing ``truth_table``.

    ``truth_table`` is a binary string of length ``2**n``, MSB first, so its
    length implies ``n``.  Eighteen languages embed their inputs in the
    program text; for those this returns a *template* with each input as a
    run of one character (``$`` unless the language declares another), one
    run per input, exactly as long as the code :func:`instantiate` fills it
    with.  ``describe(language)["parameterized"]`` says which you have; a
    template handed to :func:`run` is refused.

    ``width`` is a request, not a bound (``describe(language)["width_effect"]``):
    it does nothing where newlines are semantic, and a single token longer
    than the width still overruns it.  A template wraps with each run kept
    whole, so every row breaks in the same places.
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
    laid_out = width is not None and _takes_width(fn)
    slots = str(fn(truth_table, width) if laid_out else fn(truth_table))
    if lang.id not in parameterized_ids():
        program = slots if laid_out else wrap_program(slots, lang.id, width)
        return _Tagged(program, resolved)
    # The generator spells each input as a run; the public template is
    # that, wrapped with every run whole (see render_template).
    inputs = len(truth_table).bit_length() - 1
    wrap_to = None if laid_out else width
    text, char, pairs = render_template(lang.id, slots, inputs, wrap_to)
    return _Template(text, resolved, char, pairs)


def _is_template_for(template: str, name: str, truth_table: str) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    A wrapped template passes where the plain one is a single line.
    """
    plain = generate(name, truth_table)
    return template == plain or (
        "\n" not in plain and template.replace("\n", "") == plain
    )


def instantiate(
    language: str,
    template: str,
    bits: list[int] | tuple[int, ...],
    width: int | None = None,
    truth_table: str | None = None,
) -> str:
    """Fill a parameterized generator's template with ``bits``.

    Substituting the runs by hand does not work: each language spells a
    set-input its own way.  A language whose generator reads its inputs, or
    a template from a different language, raises
    :class:`~esolangs.exceptions.TemplateError`.  ``width`` applies here too.
    A template :func:`generate` returned carries its setters; a plain string
    has them recovered from the language's own.
    """
    check_width(width)
    name = resolve(language)
    if truth_table is not None and not _is_template_for(template, name, truth_table):
        # The provenance check a tag cannot make: a hand-written string is
        # untagged by design (a tag cannot survive a file), and
        # `instantiate("Minifuck", "hello $$", [1])` filled it happily.
        # Given the table it should have come from, that is decidable.
        raise TemplateError(
            f"this is not the template generate({name!r}, {truth_table!r}) "
            f"returns, so filling it would produce a program that does not "
            f"compute that table"
        )
    char = template_char(LANGUAGES[name].id)
    if char is None:
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
    tagged = template if isinstance(template, _Template) else None
    if tagged is None:
        if char not in template:
            # An ordinary program and an already-filled template look the
            # same from here, so the message names both.
            raise TemplateError(
                f"this {name} text has no run of {char!r} to fill: it is either "
                f"an ordinary program or a template instantiate() has already "
                f"been applied to, and generate({name!r}, table) returns the "
                f"template to fill"
            )
        try:
            pairs = recover_setters(LANGUAGES[name].id, template)
        except ValueError as exc:
            raise TemplateError(f"not a {name} template: {exc}") from exc
        tagged = _Template(template, name, char, pairs)
    if len(bits) != tagged.inputs:
        given = (
            f"{len(bits)} bit was given"
            if len(bits) == 1
            else f"{len(bits)} bits were given"
        )
        raise TemplateError(
            f"this {name} template has {tagged.inputs} input"
            f"{'' if tagged.inputs == 1 else 's'}, but {given}"
        )
    program = template_body(LANGUAGES[name].id, tagged.fill(bits))
    return _Tagged(wrap_program(program, LANGUAGES[name].id, width), name)


#: Characters a filename is made of, and a program mostly is not.
_PATH_CHARS = re.compile(r"^[\w./\\~-]+$")

#: A short extension, which is what makes a bare name look like a file.
_PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _looks_like_a_path(program: str) -> bool:
    """Whether ``program`` is a filename someone meant to open.

    A path is legal text in most of these languages
    (``run("brainfuck", "prog.bf")`` returns a null byte).  Shape-based: one
    line of path characters, rooted (``/``, ``./``, ``../``, ``~/``) or ending
    in a short extension.  ``.``, ``..`` and ``~`` are accepted as programs
    (``~~`` is two ArrowQueue commands).
    """
    if "\n" in program or not _PATH_CHARS.match(program):
        return False
    rooted = program.startswith(("/", "./", "../", "~/"))
    return rooted or bool(_PATH_EXTENSION.search(program))


def check_runnable(language: str, program: str) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are valid input to an interpreter and each produced a confident
    wrong answer (Minifuck runs a ``$`` run as nothing).  Public because the
    debugger stepped a template to ``output: '0'``; the CLI's ``debug`` calls it.
    """
    name = resolve(language)
    if _looks_like_a_path(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r})"
        )
    char = template_char(LANGUAGES[name].id)
    if char is not None and char in program:
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled runs of {char!r} ({program.count(char)} characters); "
            f"fill them with esolangs.instantiate({name!r}, program, bits)"
        )


def check_program(
    language: str, program: str | os.PathLike[str], stdin: str = ""
) -> str:
    """Return ``program`` as source, having checked what can be checked here.

    Not a load check: it refuses the wrong *kind* of thing (a path as a
    string, an unfilled template, a non-string, an unreadable file, an
    unknown name) and type-checks ``stdin``, but ``check_program("brainfuck",
    "[")`` returns the program and :func:`make_vm` raises ``ProgramError``.
    :func:`make_vm` calls this, so it cannot build a machine to check.
    :func:`check_stdin` judges ``stdin``'s shape.  A :class:`~pathlib.Path`
    is read here with its trailing newline stripped (CV(N)(C), Grapheme and
    NoComment reject one), so the whole call is::

        path = pathlib.Path(describe(lang)["examples"][0])
        run(lang, path, encode_inputs(lang, [0, 1]))
    """
    name = resolve(language)
    if isinstance(program, os.PathLike):
        try:
            program = pathlib.Path(program).read_text(encoding="utf-8").rstrip("\n")
        except FileNotFoundError as exc:
            # Split from the OSError clause below so a caller who passed a
            # Path can write ``except FileNotFoundError`` and have it work.
            raise ProgramNotFoundError(f"cannot read {program}: {exc}") from exc
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
    origin = getattr(program, "language", None)
    if origin is not None and origin != name:
        # The program says where it came from; a plain string does not and
        # is taken at its word (see :class:`_Tagged`).
        raise ProgramError(
            f"this program was generated for {origin}, so running it as "
            f"{name} would read it as {name} source -- which may well run, "
            f"and answer nonsense"
        )
    if not isinstance(stdin, str):
        # ArgumentError, matching ``check_stdin``: stdin is not the program,
        # and the four entry points here used to disagree with it.
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

    ``program`` is source or a :class:`~pathlib.Path`; a string shaped like a
    filename is refused.  A Path and its text are
    not quite the same argument: a file loses one trailing newline, a
    string keeps it.

    ``stdin`` is fed line by line.  Reading past the end usually raises
    :class:`~esolangs.exceptions.InputExhaustedError`;
    ``describe(language)["eof_is_a_value"]`` marks the languages that take a
    value and answer a *different row*, warning with
    :class:`~esolangs.exceptions.InputMismatchWarning` (Clockwise and Fargo
    read one line, so only ``check_stdin`` with the table catches them).
    Two are neither: Alight halts on ``cannot apply '+' to 2.0 and 'eof'``,
    Suffolk ends the program.  Take the alphabet from
    ``describe(language)["input_encoding"]``; the wrong one is a wrong result.

    ``timeout`` is wall-clock seconds and raises
    :class:`~esolangs.exceptions.ExecutionTimeoutError` (a
    :class:`TimeoutError` and a :class:`~esolangs.exceptions.HaltError`; catch
    it, not the base).  It is ``SIGALRM``, so needs a Unix main thread; off it,
    :meth:`Debugger.run` bounds by stepping.  ``seed`` fixes the seven
    languages that draw.  An unloadable program raises
    :class:`~esolangs.exceptions.ProgramError`.
    """
    check_timeout(timeout)
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        # Before ``_run``, so every ValueError from the run is the
        # interpreter's.  The message names both routes out for a worker
        # thread.  Not a silent fallback to stepping: two paths for one
        # function is how they diverged (``tests/test_stepping_parity.py``).
        raise ArgumentError(
            "the timeout guard uses SIGALRM and needs a Unix main thread; "
            "off it, either bound the run cooperatively with "
            "make_debugger(language, program, stdin).run(timeout=...), "
            "which steps and so needs no signal, or use evaluate/verify "
            "with timeout=None -- they settle a diverging row by proving "
            "the loop rather than waiting for it"
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
        # ``RecursionError`` was the one exception escaping ``EsolangError``.
        # The limit is CPython's, not the interpreter's (raising it made the
        # program run); Qoibl's tokenizer carries its own stack now.
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

    A warning, not a refusal: ``run`` executes arbitrary programs.  The same
    judgement :func:`check_stdin` raises, rendered as advice.
    """
    if not stdin:
        # Empty stdin is legitimate (the protocol tests run 63 programs
        # that way); a program that reads anyway is caught by the counts below.
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

    Five languages draw (COD, LaserFuck, Modulous, Painfuck,
    Super SNUSP) and nothing public passed an ``rng``: ten runs of
    ``o+++.`` gave ``3`` five times and nothing five times, while ``make_vm``
    always seeded.  A seed for a language that draws nothing is refused: the
    likelier reading is the wrong language.
    """
    import inspect

    if "rng" not in inspect.signature(run_fn).parameters:
        raise ArgumentError(
            f"{name} draws no random values, so a seed has nothing to fix; "
            f"the languages that draw are COD, LaserFuck, "
            f"Modulous, Painfuck and Super SNUSP"
        )
    from esolangs.interpreters.randomness import Seeded

    return partial(run_fn, rng=Seeded(seed))


def _keeping_output[E: EsolangError](exc: E, io_obj: ScriptedIO) -> E:
    """Attach what the program printed before ``exc``, and return it.

    The attribute is what the CLI prints; the note is for a traceback reader.
    """
    written = io_obj.getvalue()
    if written:
        exc.partial_output = written
        exc.add_note(f"the program printed {written[:200]!r} before this")
    return exc


def _warn_about_surplus(name: str, io_obj: ScriptedIO) -> None:
    """Warn if the program left supplied input unread.

    Six lines to a three-input program answered the first three silently,
    while too few always said "2 lines supplied, read 3".  Not an error:
    reading less than given is what many programs do.
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
        # Read past the end and kept going: the silent wrong answer the
        # seven ``eof_is_a_value`` languages give (a different row, or row
        # 0).  Counted, not ``supplied == 0``, which missed underfeeding.
        # Gated because Suffolk ends *by* running out of input.
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
    """Run ``run_fn``, applying the wall-clock ``timeout`` guard when set."""
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
    # The handler fires between any two bytecodes, including the cleanup's;
    # raising into its own teardown left the timer armed and the default
    # SIGALRM disposition killed one run in three.  Clearing this is one store.
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
        # Ignore first, then disarm, then restore: an alarm in flight after
        # ``old`` (the default disposition) is restored terminates the
        # process -- exit 142, one run in ten.  ``SIG_IGN`` is C-level.
        # An alarm between ``run_fn`` returning and here still raises a
        # timeout; closing that needs a flag read from a handler, not worth it.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        if pending:
            # Whatever was left of the caller's alarm, resumed.  Not exact
            # -- the run's own duration is not deducted -- but a timer that
            # fires late is a great deal better than one silently cancelled.
            signal.setitimer(signal.ITIMER_REAL, pending)
