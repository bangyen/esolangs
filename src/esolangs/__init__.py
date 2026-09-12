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

# Imported private: it takes a *generator function*, not a language name, so
# a caller reaching for ``esolangs.takes_width("LaserFuck")`` got False for
# every language in the registry, contradicting both its own docstring and
# ``describe(...)["width_aware"]`` -- which is the question they were asking.
from esolangs.tools.wrap import WRAPPERS, wrap_program
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.vm import VM, machine_traits, make_vm


#: Read from the installed distribution rather than written here: the
#: hand-kept copy said 0.1.0 while the package was 0.2.0, so ``--version``
#: named a release that does not exist.  The fallback covers a source tree
#: that was never installed.
#: Read on first access rather than on import.  ``importlib.metadata``
#: drags in ``email.parser`` to parse a wheel's metadata, and measured 23ms
#: of this package's 56ms import -- two fifths of it, spent on a string
#: most callers never read.  PEP 562 defers it to whoever asks.
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


#: The committed example programs, shipped inside the package.
#:
#: They used to sit at the repository root, which put them outside the
#: wheel: ``parents[2]`` is the repo root from a checkout and the directory
#: above ``site-packages`` from an install, so an installed copy reported
#: no examples at all -- and could in principle have globbed an unrelated
#: ``examples/`` that happened to sit there.  Inside the package the path
#: is the same either way.
_EXAMPLES = pathlib.Path(__file__).resolve().parent / "examples"

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
        # A template wraps like anything else.  It did not use to: a narrow
        # width broke a slot in half -- ``{X`` ending one line and ``1}``
        # starting the next -- and the template silently stopped being
        # instantiable, so ``generate --width 10 "Home Row" 0110`` reported
        # one input slot where the table has two.  The fix is in the token
        # rules rather than here: ``{Xi}`` is one token in every wrapper
        # (:data:`~esolangs.tools.wrap._PLACEHOLDER`), so no width can land
        # inside one.  Skipping the wrap instead would leave the eleven
        # parameterized languages with a ``width`` that quietly did nothing.
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
    # Reflowed from the template *before* its width, when there is one.
    #
    # ``wrap_program`` declines to reflow a program that already has
    # newlines, since for most languages a newline is layout rather than
    # something it put there.  After ``generate(table, width)`` a template
    # always has them, so re-wrapping the filled program did nothing at all
    # -- a width here was inert for all seventeen parameterized languages,
    # which is exactly the call this function's docstring recommends.
    # Filling the unwrapped source instead gives the wrapper the single-line
    # program it needs, and the answer is the same either way because the
    # slots are in the same places.
    #
    # Only for the languages a wrapper actually reflows.  A layout language
    # -- COD, WII2D -- lays its *template* out to the width in the generator
    # and has no wrapper here, so for those the width-laid-out template is
    # the one to fill and unwrapping it would throw the layout away.
    source: str = template
    if width is not None and LANGUAGES[name].id in WRAPPERS:
        source = getattr(template, "unwrapped", template)
    return wrap_program(fill(source, bits), LANGUAGES[name].id, width)


#: Characters a filename is made of, and a program mostly is not.
_PATH_CHARS = re.compile(r"^[\w./\\~-]+$")

#: A short extension, which is what makes a bare name look like a file.
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
        # Checked here rather than inside ``_run`` so that every ValueError
        # from the run itself is the interpreter refusing the program, and
        # can be re-raised as one.
        #
        # The message used to stop after the constraint, which left a
        # caller on a worker thread with two options and no third: a
        # timeout that raises, or ``None`` that runs forever.  Both routes
        # out already exist and neither was mentioned.
        #
        # Deliberately *not* a silent fallback to the stepping path.  Two
        # execution paths for one function is how the step route and this
        # one came to disagree in the first place -- which is why
        # ``tests/test_stepping_parity.py`` exists -- and a divergence a
        # caller cannot see is worse than a refusal they can read.
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
    # Absolute.  These were relative to the repository root, which made the
    # recipe this package advertises -- ``run(lang, Path(describe(lang)
    # ["examples"][0]))`` -- work from one directory and nowhere else: a
    # ``chdir`` away it is ``cannot read examples/boolean/brainfuck.txt``,
    # and for anyone who pip-installed there is no such directory at all.
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
        # ``-OO`` strips docstrings, so this returned ``""`` for all 69 --
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
    zero, one = facts["input_encoding"]
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


#: Not a stop reason.  It sits beside :data:`STOP_REASONS` in ``dir()`` and
#: reads like a sibling of it; it is not one.  A stop reason says why a
#: *debugger* stopped, and this says how one of the three answer-by-running
#: languages spells its answer.
#:
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
