"""Public API for the esolangs package.

See ``test_hi``, ``test_cat_echoes_until_its_input_runs_out``, and
``test_truth_machine_prints_zero_once_and_halts``.

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
table it computes (or whether it matches).  ``spec`` returns the
interpreter's own description of a language, for writing one by hand.

Every language name is resolved case-insensitively
(:func:`esolangs.registry.resolve`), so ``Brainfuck`` and ``brainfuck``
reach the same interpreter and a near miss is answered with a suggestion.
Every error raised on purpose derives from
:class:`~esolangs.exceptions.EsolangError`.
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
    resolve,
    wiki_url,
)

# Imported private: it takes a.
# a caller reaching for.
# every language in the.
# ``describe(...)["width_aware"].
from esolangs.tools.wrap import WRAPPERS, wrap_program
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.vm import VM, machine_traits, make_vm


# : Read from the installed.
# : hand-kept copy said 0.1.0.
# : named a release that does.
#: that was never installed.
# : Read on first access rather.
# : drags in ``email.parser``.
# : of this package's 56ms.
# : most callers never read.
def __getattr__(name: str) -> str:
    """Resolve ``__version__`` lazily; everything else is a normal miss."""
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib.metadata

    try:
        version = importlib.metadata.version("esolangs")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - CI installs
        # A source tree that was never.
        version = "0.0.0+unknown"
    globals()["__version__"] = version
    return version


# : The public surface.
# : ``Callable``,.
# : alongside the six functions.
# : from the outside which was.
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


# : The committed example.
# :.
# : They used to sit at the.
# : wheel: ``parents[2]`` is.
# : above ``site-packages``.
# : no examples at all -- and.
# : ``examples/`` that happened.
#: is the same either way.
_EXAMPLES = pathlib.Path(__file__).resolve().parent / "examples"

# An unfilled input slot in a.
# only for the languages whose.
# in several of the others, so.
_SLOT = re.compile(r"\{X\d+\}")
_SLOT_INDEX = re.compile(r"\{X(\d+)\}")

# Interpreter module family ->.
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
    unwrapped: str

    def __new__(cls, text: str, language: str, unwrapped: str = "") -> "_Template":
        """Return ``text`` tagged as ``language``'s template.

        ``unwrapped`` is the same template before a width was applied, kept
        because :func:`instantiate` cannot recover it: a reflow wrapper
        leaves ordinary newlines behind and there is no way to tell the ones
        it inserted from ones the generator meant.  Without it a width on
        ``instantiate`` was a no-op for every parameterized language --
        ``wrap_program`` declines to reflow a program that already has
        newlines, which after ``generate(table, width)`` it always does.
        """
        template = super().__new__(cls, text)
        template.language = language
        template.unwrapped = unwrapped or text
        return template


def generate(language: str, truth_table: str, width: int | None = None) -> str:
    """Return a program in ``language`` computing ``truth_table``.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs, most significant first, so its length implies the input count
    and the generators take no ``n``.

    Seventeen languages embed their inputs in the program text rather than
    reading them.  For those this returns a *template* with one ``{Xi}``
    slot per input, which :func:`instantiate` fills;
    ``describe(language)["parameterized"]`` says which you have, and a
    template handed to :func:`run` is refused rather than executed.

    ``width`` is a *request*, not a bound.  What it does depends on the
    language -- see ``describe(language)["width_effect"]`` -- and for the
    22 whose newlines are semantic, or that reject one outright, it does
    nothing at all.  A single token longer than the width still overruns
    it.

    The count is not a constant.  It said 38 while the answer was 22,
    because a round of teaching generators to lay themselves out moved
    sixteen languages out of that group without moving the sentence.
    ``describe`` is derived and cannot drift; prefer it to this number.
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
        # A template wraps like.
        # width broke a slot in half --.
        # starting the next -- and the.
        # instantiable, so ``generate.
        # one input slot where the.
        # rules rather than here:.
        # (:data:`~esolangs.tools.wrap._.
        # inside one.
        # parameterized languages with.
        plain = str(fn(truth_table))
        return _Template(wrap_program(plain, lang.id, width), resolved, plain)
    return wrap_program(str(fn(truth_table)), lang.id, width)


def _is_template_for(template: str, name: str, truth_table: str) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    Compared against the *unwrapped* template, then again with the newlines
    taken out of both.  The second pass is what lets a wrapped template
    through: ``generate(name, table, 40)`` is the same program with line
    breaks added between tokens, and refusing it would make the width and
    the provenance check mutually exclusive.

    Only for a language whose unwrapped template is a single line, since
    for the rest a newline is layout and dropping it compares two different
    programs.
    """
    plain = generate(name, truth_table)
    if template == plain:
        return True
    return "\n" not in plain and template.replace("\n", "") == plain


def instantiate(
    language: str,
    template: str,
    bits: list[int] | tuple[int, ...],
    width: int | None = None,
    truth_table: str | None = None,
) -> str:
    """Fill a parameterized generator's ``{Xi}`` slots with ``bits``.

    The seventeen parameterized generators embed their inputs in the
    program text, so :func:`generate` returns a template and this makes it
    runnable.  Substituting the slots by hand does not work: each language
    spells a set-input its own way, and a bare ``0`` or ``1`` in the slot
    is a different program.

    A language whose generator reads its inputs instead has nothing to
    fill and raises :class:`~esolangs.exceptions.TemplateError`, as does a
    template from a *different* language -- which would otherwise run and
    answer the wrong row.

    ``width`` is taken here as well as on :func:`generate`, and this is the
    one that a caller filling a template wants: a slot is four columns and
    the setter code that replaces it is not, so a template wrapped to a
    width no longer meets it once the slots are gone.
    """
    check_width(width)
    name = resolve(language)
    if truth_table is not None and not _is_template_for(template, name, truth_table):
        # The provenance check a tag.
        # language, so filling one.
        # *hand-written* string is.
        # a file), and.
        # substituted into it and.
        # Given the table it should.
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
            # The count is true and answers.
            # ways of getting here -- an.
            # instantiate() has already.
            # so the message names both.
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
    # Reflowed from the template.
    # .
    # ``wrap_program`` declines to.
    # newlines, since for most.
    # something it put there.
    # always has them, so.
    # -- a width here was inert for.
    # which is exactly the call.
    # Filling the unwrapped source.
    # program it needs, and the.
    # slots are in the same places.
    # .
    # Only for the languages a.
    # -- COD, WII2D -- lays its.
    # and has no wrapper here, so.
    # the one to fill and.
    source: str = template
    if width is not None and LANGUAGES[name].id in WRAPPERS:
        source = getattr(template, "unwrapped", template)
    return wrap_program(fill(source, bits), LANGUAGES[name].id, width)


# : Characters a filename is.
_PATH_CHARS = re.compile(r"^[\w./\\~-]+$")

# : A short extension, which is.
_PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _looks_like_a_path(program: str) -> bool:
    """Whether ``program`` is a filename someone meant to open.

    A program is source; a filename handed over as a plain ``str`` is a
    mistake that *runs*, because a path is legal text in most of these
    languages -- ``run("brainfuck", "prog.bf")`` returns a null byte,
    since the ``.`` is brainfuck's print.

    The rule keys on shape: one line, only the characters a path is made
    of, and either rooted (``/``, ``./``, ``../``, ``~``) or ending in a
    short extension.  It checked for a literal ``.txt`` before, which
    caught ``prog.txt`` and let ``prog.bf`` -- the natural extension for
    this package's flagship language -- and ``/etc/hosts`` straight
    through.

    ``.`` and ``..`` are accepted, and so is a bare ``~``: they are legal
    programs -- ``~~`` is two ArrowQueue commands -- and a rule that
    refuses a real program is worse than the bug it prevents.  Only
    ``~/`` counts as rooted for that reason.
    """
    if "\n" in program or not _PATH_CHARS.match(program):
        return False
    rooted = program.startswith(("/", "./", "../", "~/"))
    return rooted or bool(_PATH_EXTENSION.search(program))


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
    if _looks_like_a_path(program):
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
    """Return ``program`` as source, having checked what can be checked here.

    **Not a load check.**  It refuses a program that is the wrong *kind* of
    thing -- a path handed over as a string, an unfilled template, a
    non-string, an unreadable file, a name outside the registry -- and it
    type-checks ``stdin``.  It does not ask the language whether the source
    parses: ``check_program("brainfuck", "[")`` returns the program, and
    :func:`make_vm` on the same string raises ``ProgramError: unmatched
    '['``.  Thirty-five of the sixty-nine languages have some program this
    accepts and the interpreter then rejects.

    That is structural rather than an oversight waiting to be fixed here.
    :func:`make_vm` *calls* this function, so validating by building a
    machine would recurse; the load check belongs to the interpreter and
    happens when one is built.  Use this as a pre-flight for the mistakes
    above, and :func:`make_vm` or :func:`run` inside ``except
    EsolangError`` when the question is "will this program load".

    ``stdin`` is checked for its type only, not its content.
    :func:`check_stdin` is the one that reads it against the shape and
    alphabet a language declares, and it needs the truth table to do the
    whole job.

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
        except FileNotFoundError as exc:
            # Split from the OSError clause.
            # Path can write ``except.
            raise ProgramNotFoundError(f"cannot read {program}: {exc}") from exc
        except OSError as exc:
            raise ProgramError(f"cannot read {program}: {exc}") from exc
        except UnicodeDecodeError as exc:
            # Named separately because it.
            # ``OSError``, so the clause.
            # PNG raised a bare.
            # where every other unreadable.
            raise ProgramError(
                f"cannot read {program}: not text (invalid UTF-8 at byte {exc.start})"
            ) from exc
    if not isinstance(program, str):
        raise ProgramError(
            f"program must be a string of source or a Path, got "
            f"{type(program).__name__}"
        )
    if not isinstance(stdin, str):
        # ArgumentError, not.
        # ProgramError says "a program.
        # for its language".
        # ArgumentError all along, so.
        # disagreed with it -- and a.
        # in ``except ArgumentError``.
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

    ``program`` is the program's *source*, or a :class:`~pathlib.Path` to
    read it from.  A plain string shaped like a filename is refused rather
    than executed, because a filename is a legal program in most of these
    languages and running one silently answers with nonsense.

    **A Path and its text are not quite the same argument**: reading a file
    strips one trailing newline and passing a string does not, so the two
    disagree wherever a newline is not a legal character.  Both are
    deliberate -- a trailing newline in a file is the editor's, one in a
    string you built is yours.

    ``stdin`` is fed to the program line by line.  A program that asks for
    more than it is given usually raises
    :class:`~esolangs.exceptions.InputExhaustedError`, but not always:
    ``describe(language)["eof_is_a_value"]`` marks the languages that take
    an exhausted read as a value and carry on, which answers a *different
    row* of the table.  Those cases warn with an
    :class:`~esolangs.exceptions.InputMismatchWarning` where there is a
    read past the end to notice; Clockwise and Fargo take their input as a
    single line, so an underfed program is undetectable here and only
    ``check_stdin`` with the table catches it.

    Two languages do neither, and the flag does not separate them out:

    * **Alight** is marked ``eof_is_a_value`` and does not carry on -- the
      sentinel reaches its arithmetic and it halts with ``cannot apply '+'
      to 2.0 and 'eof'``.  So it refuses, loudly, which is the safe half
      of the flag's two outcomes but not the one it names.
    * **Suffolk** is marked ``False`` and does not raise.  An exhausted
      read *ends* the program, so a run comes back ``halted`` with no
      output and no warning at all.  That is written down under
      ``self_halts``, which says Suffolk "ends when a read runs out of
      input" -- the two traits describe the same fact and only one of them
      is where a reader looks for it.

    Swept rather than sampled: the other fifty of the fifty-two
    stdin-reading languages do exactly what the flag says.

    How a language spells its bits is not universal -- Grapheme reads
    ``%``/``A``, Fargo one number whose bits are the inputs -- so take the
    alphabet from ``describe(language)["input_encoding"]``; feeding the
    wrong one is answered with a wrong result, not an error.

    ``timeout`` bounds the run in wall-clock seconds and raises
    :class:`~esolangs.exceptions.ExecutionTimeoutError`, which is a
    :class:`TimeoutError` as well as a
    :class:`~esolangs.exceptions.HaltError` -- catch it rather than the
    base, so a program halting on an invalid operation is not mistaken for
    the clock.  The guard is ``SIGALRM`` and so needs a Unix main thread;
    off it, :meth:`Debugger.run` bounds cooperatively by stepping.

    ``seed`` fixes the random draws of the seven languages that make them.

    A program the interpreter cannot load raises
    :class:`~esolangs.exceptions.ProgramError`, so every deliberate failure
    here derives from :class:`~esolangs.exceptions.EsolangError`.
    """
    check_timeout(timeout)
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        # Checked here rather than.
        # from the run itself is the.
        # can be re-raised as one.
        # .
        # The message used to stop.
        # caller on a worker thread.
        # timeout that raises, or.
        # out already exist and neither.
        # .
        # Deliberately *not* a silent.
        # execution paths for one.
        # one came to disagree in the.
        # ``tests/test_stepping_parity.p.
        # caller cannot see is worse.
        raise ArgumentError(
            "the timeout guard uses SIGALRM and needs a Unix main thread; "
            "off it, either bound the run cooperatively with "
            "make_debugger(language, program, stdin).run(timeout=...), "
            "which steps and so needs no signal, or use evaluate/verify "
            "with timeout=None -- they settle a diverging row by proving "
            "the loop rather than waiting for it"
        )
    # No guard on the lookup:.
    # registry, and every.
    # that reaches here is always.
    # here re-raised the error.
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
        # An interpreter that recurses.
        # enough program, and the bare.
        # exception in the package that.
        # written to the documented.
        # .
        # The message used to end "this.
        # large", which was not true:.
        # raising it made the same.
        # fired for and its tokenizer.
        # remaining reach of this.
        # per construct -- and the.
        # the limit actually lives.
        raise InterpreterLimitError(
            f"the {name} interpreter recursed deeper than CPython's stack "
            f"limit allows on this program ({len(program)} characters); the "
            f"program is well formed, and sys.setrecursionlimit can raise "
            f"the limit if this interpreter's depth grows with program size"
        ) from exc
    except ValueError as exc:
        # The interpreters signal a.
        # ValueError, one per language.
        # a ProgramError keeps those.
        # true: `except EsolangError`.
        # which is the handler an.
        raise _keeping_output(ProgramError(str(exc)), io_obj) from exc
    except EsolangError as exc:
        # A halt, a timeout, an.
        # badly, which is exactly the.
        # worth keeping.
        # hanging off it are untouched,.
        # traceback rather than.
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
        # An empty stdin is "I am not.
        # legitimate thing to do with.
        # tests run sixty-nine programs.
        # warned about all of them.
        # reads anyway and gets a.
        # counts, where there is no.
        return
    if not describe(name)["reads_input"]:
        # A language that embeds its.
        # ``evaluate`` passes "" for.
        # nothing here to be wrong.
        # outright, which is right for.
        # just noise, and it fired once.
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
        # The exact signal, and the one.
        # for input that was not there.
        # languages ``eof_is_a_value``.
        # forty-five the read raises.
        # the wrong answer those seven.
        # program answers a different.
        # all answers row 0.
        # .
        # Counted rather than inferred.
        # the underfeed case, where.
        # past the end came after it.
        # .
        # Gated on ``eof_is_a_value``.
        # always a mistake: Suffolk's.
        # out of input -- it is that.
        # halts rather than taking a.
        # warned about every correct.
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
    # Whether an arriving alarm.
    # handler fires between two.
    # in the cleanup below -- so.
    # teardown and skip the rest of.
    # handler unrestored.
    # disposition, which is to.
    # the interpreter outright.
    # exception, which is the worst.
    # .
    # Clearing it is a single.
    # the thing it is cleaning up.
    armed = True

    def _timeout_handler(_signum: int, _frame: object) -> None:
        # coverage cannot trace a raise.
        if not armed:  # pragma: no cover - a late alarm, not an overrun
            return
        raise ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    # The caller's alarm, saved and.
    # theirs, so a.
    # with zero seconds left and.
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    pending = signal.setitimer(signal.ITIMER_REAL, timeout)[0]
    try:
        run_fn(program, io_obj)
    finally:
        armed = False
        # Ignore the signal *first*,.
        # back.
        # already be in flight when the.
        # after ``old`` is restored --.
        # disposition -- SIGALRM's.
        # process**.
        # outright about one run in.
        # 142, which is the worst way.
        # .
        # ``SIG_IGN`` is installed at.
        # this window is discarded.
        # .
        # One window remains by design:.
        # ``run_fn`` returning and the.
        # handler and raises, reporting.
        # finished.
        # it would need the handler to.
        # -- a flag read from a signal.
        # timeout they did set.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        if pending:
            # Whatever was left of the.
            # -- the run's own duration is.
            # fires late is a great deal.
            signal.setitimer(signal.ITIMER_REAL, pending)


class LanguageInfo(TypedDict):
    """What :func:`describe` returns, as a type a caller can annotate with.

    It was ``dict[str, object]``, which is accurate and useless: every
    field access needs a cast, and ``mypy --strict`` over an ordinary
    consumer program reported five errors, all of them this.  The
    docstring on :func:`describe` already specified every key -- this is
    that specification in a form the type checker can read.

    ``total=True``: every language has every key.  A field that does not
    apply is a documented empty value rather than a missing one, which is
    what lets a caller iterate the registry without branching -- the
    property four rounds of this package's history were spent on.
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

    Identity: ``name``, ``id``, ``state_model``, ``interpreter``,
    ``wiki_url``.

    Generation: ``boolean_generator`` says a truth-table generator exists;
    ``parameterized`` says it returns a ``{Xi}`` template, which takes its
    bits from :func:`instantiate` and so has ``reads_input`` false.

    Width: ``width_effect`` is what a ``width`` does -- ``"layout"`` (the
    generator builds a shape to fit; a hint, not a bound), ``"wrap"`` (the
    finished program is reflowed between whole tokens), or ``"none"`` (it
    is ignored, because newlines are semantic here).  ``width_aware`` is
    the narrower ``width_effect == "layout"``.  Neither promises the
    result fits; see :func:`generate`.

    Input: ``input_shape`` is how the bits are laid out and
    ``input_encoding`` the ``(zero, one)`` pair they are spelled with --
    ``("0", "1")`` almost everywhere, ``("%", "A")`` for Grapheme.  Feed
    the wrong alphabet and you get a wrong answer rather than an error, so
    read them rather than assuming.

    Answer: ``answer_mode`` is ``"output"`` (printed; read the last
    non-whitespace character), ``"dump"`` (the whole final state is
    printed and the answer sits at a fixed place in it) or
    ``"termination"`` (it halts for one value and runs forever for the
    other, so a timeout *is* an answer).  ``answer_pattern`` is the regex
    whose first group holds the answer, empty when the last character is
    it; ``answer_encoding`` is the ``(zero, one)`` that position is
    spelled with, or the polarity ``("halts", "diverges")`` for a
    termination language; ``answer_convention`` is prose naming where to
    look.  These describe the *raw output*: :func:`read_answer` always
    hands back ``"0"`` or ``"1"``, so A Painter Ant's ``("o", "@")`` is a
    mark in its grid, not a value you will see.

    Machine traits: ``self_halts``, ``dumps_on_the_post_halt_step``,
    ``steppable_to_answer`` and ``eof_is_a_value``, documented on
    :func:`~esolangs.vm.machine_traits`.

    ``examples`` lists the committed programs for the language, which
    ship with the package; ``examples/boolean/MANIFEST.md`` beside them
    says what each one computes.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    module = RUNNERS.get(name)
    family = module[0].split(".")[0] if module else None
    stem = example_stems().get(lang.id, lang.id)
    # Absolute.
    # recipe this package.
    # ["examples"][0]))`` -- work.
    # ``chdir`` away it is ``cannot.
    # and for anyone who.
    examples = sorted(str(p) for p in _EXAMPLES.glob(f"*/{stem}.txt"))
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
        # Derived, not recomputed: this.
        # expression _width_effect().
        # disagreeing about the same.
        "width_aware": _width_effect(lang) == "layout",
        "width_effect": _width_effect(lang),
        "input_encoding": example.alphabet if example else ("0", "1"),
        "input_shape": example.input_shape if example else "line_per_bit",
        "answer_mode": example.answer_mode if example else "output",
        "answer_pattern": example.answer_pattern if example else "",
        "answer_encoding": example.answer_values if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        # Spelled out rather than.
        # a ``dict[str, bool]``, which.
        # ``**``-expansion of, so the.
        # renamed or dropped trait.
        # keeps the four in step with.
        "self_halts": traits["self_halts"],
        "dumps_on_the_post_halt_step": traits["dumps_on_the_post_halt_step"],
        "steppable_to_answer": traits["steppable_to_answer"],
        "eof_is_a_value": traits["eof_is_a_value"],
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

    # One expression rather than an.
    # case: every registered.
    # line no input could reach.
    if lang.boolean is not None and _takes_width(lang.boolean):
        return "layout"
    return "wrap" if lang.id in WRAPPERS else "none"


def spec(language: str) -> str:
    """Return the interpreter's own description of ``language``.

    Every interpreter carries a module docstring giving the command table
    and -- more useful -- where this implementation differs from the wiki
    page.  It is the best documentation here for *writing* a program, as
    opposed to generating one.

    Read from the module rather than stored, so it cannot drift.  Python
    started with ``-OO`` strips docstrings, and this raises rather than
    returning an empty string.
    """
    name = resolve(language)
    module = RUNNERS[name][0]
    interpreter = importlib.import_module("esolangs.interpreters." + module)
    text = (interpreter.__doc__ or "").strip()
    if not text:
        # ``-OO`` strips docstrings, so.
        # a silent wrong answer from.
        # "read rather than stored, so.
        # worth an abort, not an empty.
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

    Most languages read one ``0``/``1`` line per input.  Four do not, and
    each of them answers the obvious guess with a *wrong bit* rather than
    an error, which is why this exists: Grapheme spells its bits ``%`` and
    ``A``, Clockwise wants them all on one line, Fargo wants one number
    whose bits are the inputs, and Taglate pads an odd count with a
    leading zero.

    ``truth_table`` is needed only where the encoding depends on the
    arity.  A language that embeds its inputs in the program reads no
    stdin at all and is refused here -- use :func:`instantiate`.
    """
    # Every registered language has.
    # always finds one;.
    name = resolve(language)
    example = _example_for(LANGUAGES[name].id)
    if example.fill is not None:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin, so "
            f"there is nothing to encode; pass the bits to instantiate() "
            f"instead"
        )
    # Checked for the same reason.
    # is not caught downstream.
    # a different row of the table,.
    # no sign that anything went.
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


# : The three ways a language.
# : a generic caller branches.
# : :data:`STOP_REASONS` and.
# : branches on ``answer_mode``.
# : magic string, which is the.
ANSWER_MODES: tuple[str, ...] = ("output", "dump", "termination")

# : The four stdin layouts,.
# : ``line_per_bit_padded``.
# : ``one_line`` puts every bit.
# : decimal number whose bits.
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
    zero, one = facts["input_encoding"]
    # ``splitlines``, which is what.
    # into the lines it hands over.
    # program will read.
    # ``strip`` silently dropped a.
    # counted nor alphabet-checked.
    # as an input bit.
    # XOR of two zeros is 0, with.
    # already decided there was.
    lines = stdin.splitlines()
    wanted = None
    if truth_table is not None:
        wanted = _validate_shape_for_evaluate(truth_table)
        if shape == "line_per_bit_padded" and wanted % 2 and wanted > 1:
            # Taglate's pad is a digit the.
            # an odd input count above one.
            # the shape, which is where.
            wanted += 1

    if shape == "row_index":
        if len(lines) != 1 or not lines[0].isdigit():
            raise ArgumentError(
                f"{name} reads one decimal row index, but stdin is {stdin.strip()!r}"
            )
        if len(lines[0]) > 1 and lines[0][0] == "0":
            # A decimal row index never has.
            # almost always the bit string.
            # 16-row program parses as.
            # row 2.
            # is one line and is in range.
            # it, which is why the rule is.
            # The bit-string reading is.
            # bits.
            # to explain a leading zero.
            # of the function whose whole.
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
        # Per *character*, because for.
        # and the alphabet check below.
        # to return past.
        # declared alphabet enforced.
        # "999", table)`` was accepted,.
        # different row of the table.
        # what this function exists to.
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
        # Phrased around the alphabet.
        # the useful half is what this.
        # a reader who fed 0/1 lines to.
        # tally of how many lines were.
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
    # For a pattern language the.
    # which is the right thing to.
    # hand a reader wondering where.
    # is the plain-language half.
    # in parentheses, so neither.
    where = "in its final state" if example.answer_pattern else "as the last character"
    # The note whenever there is.
    # languages: Back, Minsky Swap.
    # read by last character, so.
    # of the mechanism and no.
    detail = f" -- {example.note}" if example.note else ""
    if example.answer_pattern:
        detail += f" (matched with {example.answer_pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )


# : Not a stop reason.
# : reads like a sibling of it;.
# : *debugger* stopped, and.
#: languages spells its answer.
# :.
# : The two outcomes an.
# : order.
# : answer 0 and index 1 the.
# : which way round the.
# :.
# : Exported because a caller.
# : vocabulary and there was.
# : tuple into their own code.
# : :data:`STOP_REASONS` was.
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

# : A termination-answering.
# : :func:`evaluate` pays this.
# : carry that convention, so.
_TERMINATION_TIMEOUT = 5.0

# : The bound on an ordinary.
# : to hold anything to a.
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
    length -- so the round trip is one call, and a mismatch tells you which
    rows disagree.  :func:`verify` is this with the comparison done.

    ``timeout`` bounds each row.  Omit it for the defaults; pass ``None``
    for unbounded, which is what makes this callable off the main thread.
    The three languages that answer by *not terminating* do not pay it:
    those rows are settled by a repeated machine state, which proves the
    loop in microseconds, so the bound is only a backstop for a program
    that diverges by growing instead of repeating.

    ``width`` is passed through to the build, so this answers whether a
    program still computes its table once it has been wrapped.

    A failure carries the row it happened on as an exception note, and
    whatever the program printed first as ``partial_output``.
    """
    # Checked here, not only inside.
    # machine itself and never.
    # service was refused for.
    # "diverges" for the other.
    # different table depending on.
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
        # An explicit ``None`` means.
        # :func:`run` -- and it is the.
        # wall-clock guard is a.
        # here in a way it would not be.
        # program this runs is one it.
        # are settled by a repeated.
        bound = timeout
    # The width goes to whichever.
    # template that is.
    # token any wrapper knows and a.
    program = generate(name, truth_table, None if facts["parameterized"] else width)
    if terminating:
        # Which of halting and.
        # ``("halts", "diverges")`` for.
        # rather than assuming it is.
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
            # Which row, as a note rather.
            # here do not share a.
            # takes two counts and builds.
            # with a longer string would.
            # .
            # Without this a failure on a.
            # something exceeded the bound,.
            # "row 900 is" are different.
            # The bits are here too, since.
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
    # A box, because ``_run``.
    # it drove -- which is right.
    verdict: list[bool] = []

    def _drive(*_args: object) -> None:
        verdict.append(run_until_halt_or_cycle(machine))

    try:
        _run(_drive, source, ScriptedIO(""), bound)
    except ExecutionTimeoutError:  # pragma: no cover - see below
        # No cycle inside the bound:.
        # old answer, and still the.
        # .
        # Not reached by any table the.
        # trying to: these programs.
        # so even a one-millisecond.
        # can fire.
        # a loop that grows without.
        # own docstring asks callers to.
        return diverges
    except InputExhaustedError:  # pragma: no cover - see below
        # Reading past the end is how.
        # .
        # Not reachable through.
        # itself and so never.
        # one ending a *cycle* search.
        # caller passing its own stdin.
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
