"""Public API for the esolangs package.

Provides ``generate`` (produce a program computing a truth table),
``instantiate`` (fill a parameterized generator's ``{Xi}`` slots), ``run``
(execute a program through an interpreter), ``make_vm`` (a step-and-inspect
wrapper around the step-capable interpreters), ``make_debugger`` (a
breakpoint/watch layer over the VM), ``describe`` (a structured language
summary), and ``list_languages``.

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
from collections.abc import Callable
from typing import Any

from esolangs.debugger import Debugger, StopReason, make_debugger
from esolangs.exceptions import (
    EsolangError,
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
from esolangs.vm import VM, make_vm

__version__ = "0.1.0"

#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "VM",
    "Debugger",
    "EsolangError",
    "HaltError",
    "InputExhaustedError",
    "ProgramError",
    "StopReason",
    "TemplateError",
    "TruthTableError",
    "UnknownLanguageError",
    "__version__",
    "describe",
    "generate",
    "instantiate",
    "list_languages",
    "make_debugger",
    "make_vm",
    "run",
]

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

    ``width`` bounds the program to that many columns for readability;
    :data:`esolangs.tools.wrap.DEFAULT_WIDTH` is the conventional choice.
    The default of ``None`` asks for no bound, so a caller that does not
    want one gets exactly what the generator produces.

    Most languages honour it by *wrapping* the finished program, breaking
    only between whole tokens so it still means the same thing.  A few build
    a shape rather than a line -- LaserFuck folds its grid's straight runs
    -- and cannot be reflowed after the fact; those generators take the
    width themselves and lay the program out to fit.

    A language whose newlines are semantic (the 2D grid languages) or that
    rejects them outright (NoComment) ignores ``width`` rather than raising,
    so one width can be passed across every language.  Passing a width no
    generator can meet is safe; it just gets the narrowest program each of
    them can build.
    """
    lang = LANGUAGES[resolve(language)]
    fn = lang.boolean
    if fn is None:
        raise UnknownLanguageError(language)
    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    if width is not None and not isinstance(width, int):
        raise ValueError(f"width must be an integer or None, got {width!r}")
    if width is not None and _takes_width(fn):
        return str(fn(truth_table, width))
    return wrap_program(str(fn(truth_table)), lang.id, width)


def instantiate(language: str, template: str, bits: list[int] | tuple[int, ...]) -> str:
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
    name = resolve(language)
    fill = _fills().get(LANGUAGES[name].id)
    if fill is None:
        raise TemplateError(
            f"{name} reads its inputs rather than embedding them, so there "
            f"is nothing to instantiate; pass them to run() as stdin"
        )
    bits = list(bits)
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
    if any(bit not in (0, 1) for bit in bits):
        raise TemplateError(f"bits must each be 0 or 1, got {list(bits)}")
    return fill(template, bits)


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
    run raises :class:`HaltError`.  The guard uses ``SIGALRM``, so it
    requires a Unix main thread; elsewhere a ``timeout`` raises
    :class:`ValueError` and :meth:`Debugger.run`'s cooperative ``timeout``
    is the way to bound a run off the main thread.

    A program the interpreter cannot load raises
    :class:`~esolangs.exceptions.ProgramError`, so every deliberate failure
    here derives from :class:`~esolangs.exceptions.EsolangError`.
    """
    if timeout is not None and timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        # Checked here rather than inside ``_run`` so that every ValueError
        # from the run itself is the interpreter refusing the program, and
        # can be re-raised as one.
        raise ValueError("the timeout guard uses SIGALRM and needs a Unix main thread")
    # No guard on the lookup: ``resolve`` raises for a name outside the
    # registry, and every registered language has an interpreter, so a name
    # that reaches here is always in ``RUNNERS``.  The guard that used to sit
    # here re-raised the error ``resolve`` had already raised.
    name = resolve(language)
    module, split = RUNNERS[name]
    if isinstance(program, os.PathLike):
        # A committed program is a text file, so it ends with a newline; three
        # interpreters (CV(N)(C), Grapheme, NoComment) reject one as an
        # unknown command, which made ``run(lang, Path(describe(lang)
        # ["examples"][0]))`` fail on the very files this package ships.  The
        # trailing newline is the file's, not the program's.
        program = pathlib.Path(program).read_text(encoding="utf-8").rstrip("\n")
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

    def _timeout_handler(_signum: int, _frame: object) -> None:
        # coverage cannot trace a raise inside a signal handler
        raise HaltError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        run_fn(program, io_obj)
    finally:
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

    Two keys exist because assuming their default is answered with a wrong
    result rather than an error, which is the failure worth spending an API
    on.  ``input_encoding`` is the ``(zero, one)`` pair the language spells
    its input bits with -- ``("0", "1")`` almost everywhere, ``("%", "A")``
    for Grapheme, whose read counts any non-empty line as true.
    ``answer_convention`` is a sentence, or ``None``, saying how to read the
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
    examples = sorted(
        str(p.relative_to(_EXAMPLES.parent)) for p in _EXAMPLES.glob(f"*/{stem}.txt")
    )
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
        "input_encoding": example.alphabet if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        "examples": examples,
        "wiki_url": f"https://esolangs.org/wiki/{name.replace(' ', '_')}",
    }


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
