"""Public API for the esolangs package.

Provides ``generate`` (produce a program computing a truth table),
``instantiate`` (fill a parameterized generator's ``{Xi}`` slots), ``run``
(execute a program through an interpreter), ``make_vm`` (a step-and-inspect
wrapper around the step-capable interpreters), ``make_debugger`` (a
breakpoint/watch layer over the VM), ``describe`` (a structured language
summary), and ``list_languages``.

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
from collections.abc import Callable, Sequence
from typing import Any

from esolangs._validate import check_bits, check_timeout, check_width
from esolangs.debugger import STOP_REASONS, Debugger, StopReason, make_debugger
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    HaltError,
    InputExhaustedError,
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
    "STOP_REASONS",
    "VM",
    "ArgumentError",
    "Debugger",
    "EsolangError",
    "ExecutionTimeoutError",
    "GeneratorCapError",
    "HaltError",
    "InputExhaustedError",
    "ProgramError",
    "StopReason",
    "TemplateError",
    "TruthTableError",
    "UnknownLanguageError",
    "__version__",
    "check_program",
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

    ``bits`` is checked against the slots the template actually has, and
    every value must be 0 or 1.  Both are worth a check because neither is
    caught downstream: too few bits leaves a slot unfilled (which ``run``
    then refuses, one step from the cause), and a value like ``2`` is
    substituted without complaint into a program that no longer computes
    the table.
    """
    check_width(width)
    name = resolve(language)
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
    ``run(lang, Path(describe(lang)["examples"][0]))`` fail on the very
    files this package ships.
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
        raise ProgramError(
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
) -> str:
    """Execute ``program`` and return its output.

    ``program`` is the program's *source*.  A :class:`~pathlib.Path` is read
    first, so the CLI's file-taking habit carries over; a plain string that
    names an existing ``.txt`` file is refused rather than executed, because
    a filename is a perfectly legal program in most of these languages and
    ``run(lang, "examples/boolean/brainfuck.txt")`` quietly printed a null
    byte instead of saying it had run the filename.

    Input is fed to the program line by line from ``stdin``; a program that
    asks for more than it is given raises
    :class:`~esolangs.exceptions.InputExhaustedError`.  **How a language
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
    try:
        _run(run_fn, program_args, io_obj, timeout)
    except ValueError as exc:
        # The interpreters signal a malformed program with a plain
        # ValueError, one per language and each well worded.  Re-raising as
        # a ProgramError keeps those words and makes the package's promise
        # true: `except EsolangError` around user-supplied source now holds,
        # which is the handler an embedder actually writes.
        raise ProgramError(str(exc)) from exc
    return io_obj.getvalue()


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

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
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


def describe(language: str) -> dict[str, object]:
    """Return a structured description of ``language``.

    The summary carries the state model (derived from the interpreter's
    module family), whether the language has a boolean generator, whether
    that generator returns a template rather than a runnable program
    (``parameterized``) and so takes no stdin (``reads_input``), whether it
    lays its own program out to a width (``width_aware``), its example
    programs, and its esolangs.org page.

    ``width_aware`` says the generator takes the width *itself* and builds a
    narrower shape, rather than emitting a line that
    :func:`~esolangs.tools.wrap.wrap_program` reflows afterwards.  It is not
    a promise the result fits: see :func:`generate` on why a width is a
    request.  Two languages have it, and one of them (LaserFuck) can still
    overrun.

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
        "width_aware": lang.boolean is not None and _takes_width(lang.boolean),
        "width_effect": _width_effect(lang),
        "input_encoding": example.alphabet if example else ("0", "1"),
        "input_shape": example.input_shape if example else "line_per_bit",
        "answer_mode": example.answer_mode if example else "output",
        "answer_pattern": example.answer_pattern if example else "",
        "answer_encoding": example.answer_values if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        **machine_traits(name),
        "examples": examples,
        "wiki_url": f"https://esolangs.org/wiki/{name.replace(' ', '_')}",
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


def encode_inputs(
    language: str, bits: Sequence[int], truth_table: str | None = None
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
    four rows, and the program answers it without complaint.  Only the
    line-per-bit languages catch it at all, and only by accident -- the
    program reads a fourth line that is not there and raises
    :class:`~esolangs.exceptions.InputExhaustedError`.
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
    where = (
        f"matching {example.answer_pattern!r}"
        if example.answer_pattern
        else "as the last character"
    )
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}"
    )


#: A termination-answering language proves a 1 by *not* halting, so
#: :func:`evaluate` pays this once for every such row.  Three languages
#: carry that convention, so the floor is real and small.
_TERMINATION_TIMEOUT = 5.0

#: The bound on an ordinary row.  Generous: it exists to stop a hang, not
#: to hold anything to a schedule.
_ROW_TIMEOUT = 30.0


def evaluate(language: str, truth_table: str, timeout: float | None = None) -> str:
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

    ``timeout`` bounds each row.  The default is 30 seconds for an ordinary
    row and 5 for one of the termination languages, where the timeout is
    the answer and so is paid on every 1.
    """
    facts = describe(language)
    name = str(facts["name"])
    inputs = _validate_shape_for_evaluate(truth_table)
    terminating = facts["answer_mode"] == "termination"
    bound = (
        timeout
        if timeout is not None
        else (_TERMINATION_TIMEOUT if terminating else _ROW_TIMEOUT)
    )
    program = generate(name, truth_table)
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
            source, stdin = instantiate(name, program, bits), ""
        else:
            source, stdin = program, encode_inputs(name, bits, truth_table)
        if terminating:
            try:
                run(name, source, stdin=stdin, timeout=bound)
                answers.append(halts_is)
            except ExecutionTimeoutError:
                answers.append(diverges_is)
        else:
            answers.append(read_answer(name, run(name, source, stdin, bound)))
    return "".join(answers)


def verify(language: str, truth_table: str, timeout: float | None = None) -> bool:
    """Whether a generated ``language`` program really computes ``truth_table``.

    :func:`evaluate` with the comparison done, for the common case where
    only the verdict is wanted.  Use ``evaluate`` when a mismatch needs
    locating: it returns the table the program computed, so the rows that
    disagree are visible rather than summarized to ``False``.
    """
    return evaluate(language, truth_table, timeout) == truth_table


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
