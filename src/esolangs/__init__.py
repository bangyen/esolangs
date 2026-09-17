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


#: The committed examples, inside the package so the wheel ships them
#: (at the repo root, ``parents[2]`` from an install was above ``site-packages``).
_EXAMPLES = pathlib.Path(__file__).resolve().parent / "examples"

# An unfilled input slot in a parameterized generator's template.  Matched
# only for the languages whose generator emits one: ``{`` is a live command
# in several of the others, so a blanket search would refuse real programs.

# Interpreter module family -> state model name.
_STATE_MODELS = {
    "register_based": "register",
    "tape_based": "tape",
    "stack_based": "stack",
    "grid_based": "grid",
    "queue_based": "queue",
    "other": "other",
}


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
        # Empty stdin is legitimate (the protocol tests run 65 programs
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

    Seven languages draw (COD, Interprogck8, LaserFuck, Modulous, Painfuck,
    Super SNUSP, WII2D) and nothing public passed an ``rng``: ten runs of
    ``o+++.`` gave ``3`` five times and nothing five times, while ``make_vm``
    always seeded.  A seed for a language that draws nothing is refused: the
    likelier reading is the wrong language.
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


class LanguageInfo(TypedDict):
    """What :func:`describe` returns, as a type a caller can annotate with.

    ``dict[str, object]`` cost a cast per field (five ``mypy --strict`` errors
    in an ordinary consumer).  ``total=True``: a field that does not apply is
    a documented empty value, so a caller iterates the registry without branching.
    """

    name: str
    id: str
    state_model: str | None
    interpreter: str | None
    boolean_generator: bool
    parameterized: bool
    reads_input: bool
    width_aware: bool
    width_effect: str
    input_encoding: tuple[str, str]
    input_shape: str
    answer_mode: str
    answer_pattern: str
    answer_encoding: tuple[str, str]
    answer_convention: str | None
    self_halts: bool
    dumps_on_the_post_halt_step: bool
    steppable_to_answer: bool
    eof_is_a_value: bool
    examples: list[str]
    wiki_url: str


def describe(language: str) -> LanguageInfo:
    """Return a structured description of ``language``.

    Identity: ``name``, ``id``, ``state_model``, ``interpreter``, ``wiki_url``.
    Generation: ``boolean_generator``; ``parameterized`` (a template, filled by
    :func:`instantiate`, ``reads_input`` false).  Width: ``width_effect`` is
    ``"layout"`` (a shape built to fit; a hint), ``"wrap"`` (reflowed between
    tokens) or ``"none"`` (newlines are semantic); ``width_aware`` is the
    narrower ``== "layout"``.  Input: ``input_shape`` and ``input_encoding``,
    the ``(zero, one)`` pair (``("%", "A")`` for Grapheme) -- the wrong
    alphabet is a wrong answer.  Answer: ``answer_mode`` is ``"output"``
    (last non-whitespace character), ``"dump"`` (a fixed place in the final
    state) or ``"termination"`` (a timeout *is* an answer);
    ``answer_pattern`` is the regex whose first group holds it;
    ``answer_encoding`` the ``(zero, one)`` or ``("halts", "diverges")``;
    ``answer_convention`` prose.  These describe raw output (A Painter Ant's
    ``("o", "@")`` is a grid mark); :func:`read_answer` returns ``"0"``/``"1"``.
    Machine traits (``self_halts``, ``dumps_on_the_post_halt_step``,
    ``steppable_to_answer``, ``eof_is_a_value``) are documented on
    :func:`~esolangs.vm.machine_traits`.  ``examples`` lists the committed
    programs; ``examples/MANIFEST.md`` says what each computes.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    module = RUNNERS.get(name)
    family = module[0].split(".")[0] if module else None
    stem = example_stems().get(lang.id, lang.id)
    # Absolute.  These were relative to the repository root, which made the
    # recipe this package advertises -- ``run(lang, Path(describe(lang)
    # ["examples"][0]))`` -- work from one directory and nowhere else: a
    # ``chdir`` away it is ``cannot read examples/brainfuck.txt``,
    # and for anyone who pip-installed there is no such directory at all.
    examples = sorted(str(p) for p in _EXAMPLES.glob(f"{stem}.txt"))
    traits = machine_traits(name)
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
        # Spelled out rather than ``**machine_traits(name)``: that returns
        # a ``dict[str, bool]``, which a TypedDict cannot verify a
        # ``**``-expansion of, so the merge would have silently accepted a
        # renamed or dropped trait.  ``test_describe_agrees_with_the_machine``
        # keeps the four in step with what the VM reports.
        "self_halts": traits["self_halts"],
        "dumps_on_the_post_halt_step": traits["dumps_on_the_post_halt_step"],
        "steppable_to_answer": traits["steppable_to_answer"],
        "eof_is_a_value": traits["eof_is_a_value"],
        "examples": examples,
        "wiki_url": wiki_url(name),
    }


def _width_effect(lang: Any) -> str:
    """Return what ``width`` actually does to this language's program.

    ``width_aware`` was ``False`` for both Sophie (reflowed afterwards) and
    Clockwise (ignores it).  ``"layout"``: a shape built to fit, a hint
    (LaserFuck asked for 10 gives 18, for 200 gives 56); ``"wrap"``:
    reflowed between tokens; ``"none"``: ignored, newlines semantic.
    """
    # One expression rather than an early return for the generator-less
    # case: every registered language has a generator, so that return was a
    # line no input could reach.
    if lang.boolean is not None and _takes_width(lang.boolean):
        return "layout"
    return "wrap" if lang.id in WRAPPERS else "none"


def spec(language: str) -> str:
    """Return the interpreter's own description of ``language``.

    The module docstring: the command table and where this implementation
    differs from the wiki -- the documentation for *writing* a program.
    Raises under ``-OO``, which strips docstrings.
    """
    name = resolve(language)
    module = RUNNERS[name][0]
    interpreter = importlib.import_module("esolangs.interpreters." + module)
    text = (interpreter.__doc__ or "").strip()
    if not text:
        # ``-OO`` strips docstrings, so this returned ``""`` for all 65 --
        # a silent wrong answer from the function whose whole promise is
        # "read rather than stored, so it cannot drift".  Nothing to say is
        # worth an abort, not an empty string that looks like an answer.
        raise ProgramError(
            f"{name}'s spec is its interpreter's docstring, and this "
            f"interpreter has none -- Python was started with -OO (or "
            f"PYTHONOPTIMIZE=2), which strips them"
        )
    return text


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    truth_table: str | None = None,
) -> str:
    """Return the stdin that feeds ``bits`` to a ``language`` program.

    Most read one ``0``/``1`` line per input; Grapheme spells ``%``/``A``,
    Clockwise wants one line, Fargo one number, Taglate pads an odd count --
    each answering the obvious guess with a wrong bit.  ``truth_table`` is
    needed only where the encoding depends on arity.  A language that embeds
    its inputs is refused; use :func:`instantiate`.
    """
    # Every registered language has a committed example, so the lookup
    # always finds one; ``example_stems`` covers all 65 and a test pins that.
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
        from esolangs.tools.helpers import _validate_truth_table

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

    The CLI's judge, for Python callers: a ``0``/``1`` line to Grapheme,
    several lines to Clockwise, a non-number to Fargo.  Raises
    :class:`~esolangs.exceptions.ArgumentError`; :func:`run` only warns.
    ``truth_table`` adds the count, catching surplus lines.  Every check reads
    a :func:`describe` field.
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
    zero, one = facts["input_encoding"]
    # ``splitlines``, as :class:`ScriptedIO` cuts it.  ``strip().split``
    # dropped a leading/trailing blank line the interpreter still read:
    # ``run("brainfuck", xor, "\n\n")`` answered 1 unwarned.
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
            # A leading zero is almost always the bit string typed out
            # (``0010`` parses as ten, answers row 10 not 2; count and range
            # both pass).  The bit reading is offered only when the digits
            # are bits: ``int('02', 2)`` crashed the refusal.
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
        # Per character (a character is a bit here); this branch used to
        # return past the per-line alphabet check, so
        # ``check_stdin("Clockwise", "999", table)`` was accepted.
        astray = [char for char in lines[0] if char not in (zero, one)]
        if astray:
            raise ArgumentError(
                f"{name} spells its bits {zero!r} and {one!r}, and "
                f"{len(astray)} character(s) of its one line are outside "
                f"that -- the first is {astray[0]!r}"
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

    Most print it (last non-whitespace character); six dump their state, and
    two differ -- RAM0's answer is its ``z`` register three lines up, A
    Painter Ant marks the ant's cell ``o``/``@``.
    ``describe(language)["answer_pattern"]`` is the same fact as data (a
    verifier that hardcoded two dumps and forgot a third reported a passing
    language as broken).  A termination-answer language (123, ArrowQueue,
    Point Break) raises :class:`~esolangs.exceptions.ArgumentError`: bound
    the run and catch :class:`~esolangs.exceptions.ExecutionTimeoutError`.
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


#: The two outcomes of ``answer_mode == "termination"``, in
#: ``describe(...)["answer_encoding"]`` order (index = answer), so
#: ``encoding.index("diverges")`` is the polarity.  Not a stop reason,
#: despite sitting beside :data:`STOP_REASONS`.  Exported because a reader
#: hand-copied it.
TERMINATION_OUTCOMES: tuple[str, str] = ("halts", "diverges")


class _Default:
    """The "argument was not given" marker for :func:`evaluate`.

    ``None`` already means *unbounded* in :func:`run`, and meaning "default"
    here too left no value that turned the alarm off from a thread.
    """

    def __repr__(self) -> str:
        """Render as ``<default>`` in a signature rather than as an address."""
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

    Generates, runs every row, returns the answers as a binary string;
    :func:`verify` is this with the comparison done.  ``timeout`` bounds each
    row: omit for the defaults, ``None`` for unbounded (callable off the main
    thread).  The three termination-answer languages do not pay it: those rows are
    settled by a repeated machine state, so the bound is only a backstop
    for growth.
    ``width`` is passed through.  A failure carries the row as a note and
    ``partial_output``.
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
        # ``None`` is unbounded, as in :func:`run`, and the thread escape
        # hatch (the guard is ``SIGALRM``).  Safe: every program here is
        # generated, and the divergers are settled by a repeated state.
        bound = timeout
    # The width goes to whichever call builds the runnable text: for a
    # template that is ``instantiate`` below, which keeps every input's
    # run whole where a break inside one would destroy it.
    program = generate(name, truth_table, None if facts["parameterized"] else width)
    if terminating:
        # Which of halting and diverging means 1, as data.  It is
        # ``("halts", "diverges")`` for all three, but reading the order
        # rather than assuming it is what keeps this branch language-free.
        encoding = list(facts["answer_encoding"])
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
            # The row and its bits as a note (the classes share no
            # constructor); a 1024-row failure otherwise names no row.
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

    A repeated snapshot proves the loop in milliseconds (these programs
    revisit a state within a hundred steps) where waiting cost five seconds
    per 1-row.  The clock stays for growth, which never repeats.  A step
    budget was rightly refused earlier; a repeated state is a fact, not a guess.
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
        # No cycle inside the bound: unbounded growth or slow.  Unreached
        # by the suite (every program repeats within ~100 steps); kept
        # because the detector proves only cycles.
        return diverges
    except InputExhaustedError:  # pragma: no cover - see below
        # Reading past the end is a halt.  Unreachable via :func:`evaluate`
        # (it never underfeeds); kept for a caller passing its own stdin.
        return halts
    return halts if verdict and verdict[0] else diverges


def verify(
    language: str,
    truth_table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
) -> bool:
    """Whether a generated ``language`` program really computes ``truth_table``.

    Use :func:`evaluate` to see which rows disagree.
    """
    return evaluate(language, truth_table, timeout, width) == truth_table


def _validate_shape_for_evaluate(truth_table: str) -> int:
    """Return the input count of ``truth_table``, refusing a malformed one.

    The row loop needs the arity before :func:`generate` validates, and a
    generator's error named the generator rather than the table.
    """
    from esolangs.tools.helpers import _validate_truth_table

    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    return _validate_truth_table(truth_table)


def _example_for(language_id: str) -> Any:
    """Return the committed boolean example for ``language_id``, or None.

    Deferred: ``examples`` imports the registry.
    """
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    stem = example_stems().get(language_id)
    return BOOLEAN_EXAMPLES.get(stem) if stem is not None else None


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
