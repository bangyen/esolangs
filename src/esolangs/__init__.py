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
import importlib.metadata as _metadata
import os
import pathlib
import re
import signal
import threading
from collections.abc import Callable, Sequence
from typing import Any

from esolangs.debugger import Debugger, StopReason, make_debugger
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
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
    "VM",
    "ArgumentError",
    "Debugger",
    "EsolangError",
    "ExecutionTimeoutError",
    "HaltError",
    "InputExhaustedError",
    "ProgramError",
    "StopReason",
    "TemplateError",
    "TruthTableError",
    "UnknownLanguageError",
    "__version__",
    "describe",
    "encode_inputs",
    "generate",
    "instantiate",
    "list_languages",
    "make_debugger",
    "make_vm",
    "read_answer",
    "run",
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


def _check_width(width: object) -> None:
    """Refuse a width that is not a positive integer.

    Shared by :func:`generate` and :func:`instantiate` because they are the
    same option on the same program, and only one of them used to check it:
    ``instantiate(..., width=0)`` and ``width=-2`` were accepted and ignored
    while ``generate`` refused them, and ``width="8"`` reached the
    comparison and leaked a ``TypeError`` about ``str`` and ``int``.  A
    width of 0 bounds nothing, and returning the unwrapped program for it
    looked like the option had been honoured.
    """
    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, int):
        raise ArgumentError(f"width must be an integer or None, got {width!r}")
    if width <= 0:
        raise ArgumentError(f"width must be positive, got {width}")


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
    lang = LANGUAGES[resolve(language)]
    fn = lang.boolean
    if fn is None:
        raise UnknownLanguageError(language)
    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    _check_width(width)
    if width is not None and _takes_width(fn):
        return str(fn(truth_table, width))
    if lang.id in parameterized_ids():
        # A template is not wrapped.  No wrapper names ``{Xi}`` as a token,
        # so a narrow width breaks a slot in half -- ``{X`` ending one line
        # and ``1}`` starting the next -- and the template silently stops
        # being instantiable: ``generate --width 10 "Home Row" 0110`` then
        # reported one input slot where the table has two.  Wrapping belongs
        # after the slots are gone, so :func:`instantiate` takes the width.
        return str(fn(truth_table))
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
    _check_width(width)
    name = resolve(language)
    fill = _fills().get(LANGUAGES[name].id)
    if fill is None:
        raise TemplateError(
            f"{name} reads its inputs rather than embedding them, so there "
            f"is nothing to instantiate; pass them in as stdin instead"
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
    if timeout is not None and timeout <= 0:
        raise ArgumentError(f"timeout must be positive, got {timeout}")
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
    if isinstance(program, os.PathLike):
        # A committed program is a text file, so it ends with a newline; three
        # interpreters (CV(N)(C), Grapheme, NoComment) reject one as an
        # unknown command, which made ``run(lang, Path(describe(lang)
        # ["examples"][0]))`` fail on the very files this package ships.  The
        # trailing newline is the file's, not the program's.
        try:
            program = pathlib.Path(program).read_text(encoding="utf-8").rstrip("\n")
        except OSError as exc:
            raise ProgramError(f"cannot read {program}: {exc}") from exc
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
        raise ExecutionTimeoutError(
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
        "input_shape": example.input_shape if example else "line_per_bit",
        "answer_mode": example.answer_mode if example else "output",
        "answer_pattern": example.answer_pattern if example else "",
        "answer_encoding": example.answer_values if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        "examples": examples,
        "wiki_url": f"https://esolangs.org/wiki/{name.replace(' ', '_')}",
    }


def encode_inputs(language: str, bits: Sequence[int]) -> str:
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
    bits = list(bits)
    # Checked for the same reason ``instantiate`` checks it: a 2 or a "1"
    # is not caught downstream.  It encodes as a 1 and the program answers
    # a different row of the table, which is the wrong answer arriving with
    # no sign that anything went astray.
    if any(bit not in (0, 1) for bit in bits):
        raise ArgumentError(f"bits must each be 0 or 1, got {bits!r}")
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
