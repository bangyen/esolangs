"""Generate programs, run supplied source, and describe languages.

Public operations split by who supplies the program:

* Generator-made: ``generate`` builds source from a truth table and
  ``instantiate`` fills a generator-made template.
* Caller-supplied: ``run`` executes source the caller supplies.
  Stepping and debugging live in :mod:`esolangs.debugger`.
* Contract adapters: ``encode_inputs`` spells input bits as stdin,
  ``read_answer`` extracts an answer bit from output, and
  ``dump_program``/``load_program`` preserve source in portable JSON.
* Catalog: ``describe`` and ``list_languages`` provide registry facts.

Boolean evaluation over every row is private certification machinery,
not public API.  ``Language(name)`` binds these functions to one language.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
"""

import importlib
import inspect
import re
from collections.abc import Callable
from functools import cache, partial
from math import isqrt
from typing import Any, cast

from esolangs._language import Language
from esolangs.compressed import CompressedText, TextLimits
from esolangs.debugger import make_debugger
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    HaltError,
    InputExhaustedError,
    InterpreterLimitError,
    MissingDependencyError,
    ProgramError,
    ProgramNotFoundError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.generation.helpers import (
    check_table_text,
    mark_runs,
    same_up_to_wrapping,
    unmark,
)
from esolangs.generation.token_balance import CELL_ASPECT

# Imported private: it takes a *generator function*, not a language name, so
# a caller reaching for ``esolangs.takes_width(language)`` got False for
# every language in the registry, contradicting both its own docstring and
# ``describe(...)["width_effect"] == "layout"`` -- the question they asked.
from esolangs.generation.wrap import (
    balance_program,
    wrap_program,
)
from esolangs.generation.wrap import takes_width as _takes_width
from esolangs.portable import dump_program, load_program
from esolangs.raster import Raster
from esolangs.registry import (
    LANGUAGES,
    SourceKind,
    recover_setters,
    render_template,
    resolve,
    template_body,
    template_char,
)
from esolangs.registry._describe import (
    LanguageInfo,
    describe,
    list_languages,
)
from esolangs.runtime._answers import encode_inputs, read_answer
from esolangs.runtime._execution import (
    check_signal_timeout,
    interpreter_errors,
    interpreter_module,
    prepare_call,
    run_under_alarm,
)
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._isolated import run_isolated as _run_isolated
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime._source import (
    InputSource,
    ProgramSource,
    _FileSource,
    check_input,
    check_scale_for,
    text_source,
)
from esolangs.runtime._validate import (
    check_bits,
    check_flag,
    check_scale,
    check_seed,
    check_timeout,
    check_whole,
    check_width,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.tagged import _Tagged, _Template


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


def _bind_annotation_names() -> None:
    """Let ``typing.get_type_hints`` resolve the public classes' annotations.

    ``compressed``, ``raster`` and ``tagged`` name ``DialectSettings`` only
    under ``TYPE_CHECKING`` (``settings`` imports the registry, which imports
    them), so ``get_type_hints(Raster)`` raised NameError on 3.12 to 3.14.
    """
    import esolangs.compressed
    import esolangs.raster
    import esolangs.tagged

    for module in (esolangs.compressed, esolangs.raster, esolangs.tagged):
        module.DialectSettings = DialectSettings  # type: ignore[attr-defined]


_bind_annotation_names()


#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ArgumentError",
    "CompressedText",
    "DialectSettings",
    "EsolangError",
    "ExecutionTimeoutError",
    "GeneratorCapError",
    "HaltError",
    "InputExhaustedError",
    "InputSource",
    "InterpreterLimitError",
    "Language",
    "LanguageInfo",
    "MissingDependencyError",
    "Program",
    "ProgramError",
    "ProgramNotFoundError",
    "ProgramSource",
    "Raster",
    "TemplateError",
    "TextLimits",
    "TruthTableError",
    "UnknownLanguageError",
    "describe",
    "dump_program",
    "encode_inputs",
    "generate",
    "instantiate",
    "list_languages",
    "load_program",
    "read_answer",
    "run",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)


def generate(
    language: str,
    truth_table: str,
    *,
    width: int | None = None,
    balance: bool = False,
    scale: int = 1,
    settings: DialectSettings | None = None,
) -> Program:
    """Return a program in ``language`` computing ``truth_table``.

    Languages that embed inputs in the program text return a *template*: one
    run of one character per input (``$`` unless the language declares
    another), as long as the code :func:`instantiate` fills it with.
    ``describe(language)["parameterized"]`` says which you have; :func:`run`
    refuses a template.  Tagged results retain ``settings`` for execution.

    Args:
        truth_table: Binary string of length ``2**n``, MSB first.
        width: A request, not a bound (``describe(language)["width_effect"]``):
            it does nothing where newlines are semantic, and a token longer
            than the width still overruns it.  A template wraps with each run
            kept whole, so every row breaks in the same places.
        balance: Pick the supported layout fitting the smallest on-screen
            square: text minimizes max(columns, 2 * rows), a character cell
            being about twice as tall as wide, then source length, then
            width.  A raster minimizes max(width, height) in pixels, then
            pixel area, then width.  Excludes ``width``.
        scale: Raster only; replicates pixels after layout (1: native output).
        settings: Dialect choices; see ``describe(language)["dialect_settings"]``.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        TruthTableError: ``truth_table`` is not a binary string of length
            ``2**n``.
        ArgumentError: The language has no Boolean generator (``esolangs list
            --details`` marks it ``int``), or an option is invalid or combined
            with one it excludes (``balance`` with ``width``, ``scale`` for a
            text language).
        GeneratorCapError: The table exceeds the generator's cap
            (``describe(language)["generator_max_inputs"]`` and
            ``["generator_restrictions"]``).
    """
    options = dialect_options(language, settings)
    check_scale(scale)
    check_flag(balance, "balance")
    if scale != 1:
        if LANGUAGES[resolve(language)].source_kind is not SourceKind.RASTER:
            raise with_hint(
                ArgumentError("scale is only supported for raster generators"),
                "omit scale for text languages; apply it only to raster source",
            )
        source = generate(
            language, truth_table, width=width, balance=balance, settings=settings
        )
        return cast(Raster, source).upscaled(scale)
    if balance and width is not None:
        raise with_hint(
            ArgumentError("balance and width are mutually exclusive"),
            (
                "omit width when balance=True, or disable "
                "balance when choosing a fixed width"
            ),
        )
    if balance:
        return _generate_balanced(language, truth_table, options, settings)
    resolved = resolve(language)
    lang = LANGUAGES[resolved]
    fn = lang.boolean
    if fn is None:
        # The language reads input but cannot meet the generator's size contract.
        raise ArgumentError(
            f"{resolved} has no boolean generator under this repository's "
            f"generator contracts. `esolangs list --details` marks it 'int'"
        )
    check_table_text(truth_table)
    check_width(width)
    laid_out = width is not None and _takes_width(fn)
    try:
        generated = (
            fn(truth_table, width, **options)
            if laid_out
            else fn(truth_table, **options)
        )
    except EsolangError:
        raise
    except ValueError as error:
        raise ArgumentError(str(error)) from error
    if lang.source_kind is SourceKind.RASTER:
        if not isinstance(generated, Raster):  # pragma: no cover - registry invariant
            raise ProgramError(f"{resolved}'s generator did not return a Raster")
        # Tagged the way a text program is ``_Tagged``: a raster fed to a
        # text interpreter otherwise passed ``_check_program`` and answered '', a
        # confident garbage result rather than a refusal.
        return generated.tagged(resolved, settings=settings, scale=1)
    if isinstance(generated, CompressedText):
        return generated.wrapped(width).tagged(resolved, settings=settings)
    slots = str(generated)
    if not lang.parameterized:
        program = slots if laid_out else wrap_program(slots, lang.id, width)
        return _Tagged(program, resolved, settings=settings)
    # The generator spells each input as a run; the public template is
    # that, wrapped with every run whole (see render_template).
    inputs = len(truth_table).bit_length() - 1
    wrap_to = None if laid_out else width
    text, char, pairs = render_template(lang.id, slots, inputs, wrap_to)
    return _Template(text, resolved, char, pairs, settings=settings)


def _generate_balanced(
    language: str,
    truth_table: str,
    options: dict[str, Any],
    settings: DialectSettings | None,
) -> Program:
    """Return ``generate(..., balance=True)``: the default, rebuilt squarest."""
    default = generate(language, truth_table, settings=settings)
    name = resolve(language)
    lang = LANGUAGES[name]
    balancer = lang.balance
    if isinstance(default, CompressedText):
        return default.wrapped(max(1, isqrt(CELL_ASPECT * len(default))))
    if isinstance(default, Raster):
        if balancer is None:
            return default
        raster_balance = cast(Callable[[str, Raster], Raster], balancer)
        return raster_balance(truth_table, default).tagged(
            name, settings=settings, scale=1
        )
    if balancer is not None:
        # A dialect setting the balancer names changes what it rebuilds.
        accepted = inspect.signature(balancer).parameters
        balance_options = {
            key: value for key, value in options.items() if key in accepted
        }
        text = cast(Callable[..., str], balancer)(
            truth_table, default, **balance_options
        )
        if isinstance(default, _Template):
            text, char, pairs = render_template(lang.id, text, default.inputs)
            return _Template(text, default.language, char, pairs, settings=settings)
        return _Tagged(text, name, settings=settings)
    if isinstance(default, _Template):
        marked = mark_runs(default, default.char, default.setters)
        text = unmark(balance_program(marked, lang.id), default.char, default.inputs)
        return _Template(
            text, default.language, default.char, default.setters, settings=settings
        )
    return _Tagged(balance_program(default, lang.id), name, settings=settings)


def _is_template_for(
    template: str, name: str, truth_table: str, settings: DialectSettings | None = None
) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    Compare wrapping using the language's whitespace rules.
    """
    plain = generate(name, truth_table, settings=settings)
    if not isinstance(plain, str):
        return False
    if template == plain:
        return True
    generator = LANGUAGES[name].boolean
    width_aware = generator is not None and _takes_width(generator)

    @cache
    def layout(width: int) -> Program:
        return generate(name, truth_table, width=width, settings=settings)

    # Layouts may switch representations; their floor is a named candidate,
    # unlike whitespace wrapping, so compare that template exactly too.
    if width_aware and template == layout(1):
        return True
    # A layout built for its own widest line: ArrowQueue's ``width=5`` shifts
    # the setter column, matching neither the default nor ``layout(1)``.
    widest = max(map(len, template.splitlines()), default=0)
    if width_aware and widest and template == layout(widest):
        return True
    same_layout = LANGUAGES[name].same_layout or (
        lambda template, plain, _layout: same_up_to_wrapping(template, plain)
    )
    return same_layout(template, plain, layout)


def _check_template_source(
    name: str,
    template: Program,
    truth_table: str | None,
    settings: DialectSettings | None,
) -> str:
    """Return the setter character for ``template``, or refuse an unfillable one."""
    if isinstance(template, Raster):
        # Accepted by the annotation so ``instantiate(lang, generate(lang,
        # table), bits)`` type-checks; no raster generator emits a template.
        raise with_hint(
            TemplateError(
                f"{name} source is a Raster, and raster programs read their "
                f"inputs rather than embedding them, so there is nothing to "
                f"instantiate"
            ),
            "run the raster with stdin=encode_inputs(language, bits)",
        )
    if not isinstance(template, str):
        # Before the provenance check, which calls ``template.replace`` and
        # so leaked an ``AttributeError`` for a non-string.
        raise with_hint(
            TemplateError(
                f"template must be the string generate() returned, got "
                f"{type(template).__name__}"
            ),
            (
                "pass the template returned by generate(), "
                "then supply integer bits to instantiate()"
            ),
        )
    if truth_table is not None and not _is_template_for(
        template, name, truth_table, settings
    ):
        # The provenance check a tag cannot make: a hand-written string is
        # untagged by design (a tag cannot survive a file), and
        # `instantiate(language, "hello $$", [1])` filled it happily.
        # Given the table it should have come from, that is decidable.
        raise with_hint(
            TemplateError(
                f"this is not the template generate({name!r}, {truth_table!r}) "
                f"returns, so filling it would produce a program that does not "
                f"compute that table"
            ),
            (
                "regenerate the template from the intended "
                "language and truth table before instantiating "
                "it"
            ),
        )
    char = template_char(LANGUAGES[name].id)
    if char is None:
        raise with_hint(
            TemplateError(
                f"{name} reads its inputs rather than embedding them, so there "
                f"is nothing to instantiate; pass them in as stdin instead"
            ),
            "run the generated program with stdin=encode_inputs(language, bits)",
        )
    origin = getattr(template, "language", None)
    if origin is not None and origin != name:
        raise with_hint(
            TemplateError(
                f"this template came from generate({origin!r}, ...), so filling "
                f"it as {name} would substitute {name}'s setter code into a "
                f"{origin} program -- which runs, and answers the wrong row"
            ),
            "instantiate the template using the language that generated it",
        )
    return char


def instantiate(
    language: str,
    template: Program,
    bits: list[int] | tuple[int, ...],
    *,
    width: int | None = None,
    truth_table: str | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Fill a parameterized generator's template with ``bits``.

    Hand substitution fails: each language spells a set-input its own way.  A
    template from :func:`generate` carries its setters; a plain string has them
    recovered from the language's own.  Retained dialect choices follow the
    filled program; explicit ``settings`` override individual ones.

    Args:
        template: :func:`generate`'s result, or the same text as a plain string.
        bits: One integer 0 or 1 per input.
        width: As for :func:`generate`.
        truth_table: The table ``template`` was generated from; when given,
            a template :func:`generate` would not return for it is refused.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        TemplateError: Nothing to fill: the language reads its inputs, the
            template came from another language or table, is a raster, is
            already filled, or has a different input count than ``bits``.
        ArgumentError: A bit is not an integer 0 or 1, or an option is
            invalid.
    """
    settings = effective_settings(language, template, settings)
    dialect_options(language, settings)
    check_width(width)
    name = resolve(language)
    char = _check_template_source(name, template, truth_table, settings)
    assert isinstance(template, str)  # the check refuses a Raster
    bits = check_bits(bits, "bits")
    tagged = (
        template
        if isinstance(template, _Template)
        else _recover_template(name, template, char, settings)
    )
    if len(bits) != tagged.inputs:
        given = (
            f"{len(bits)} bit was given"
            if len(bits) == 1
            else f"{len(bits)} bits were given"
        )
        raise with_hint(
            TemplateError(
                f"this {name} template has {tagged.inputs} input"
                f"{'' if tagged.inputs == 1 else 's'}, but {given}"
            ),
            f"pass exactly {tagged.inputs} integer bits to instantiate(), "
            "one per input",
        )
    program = template_body(LANGUAGES[name].id, tagged.fill(bits))
    return _Tagged(
        wrap_program(program, LANGUAGES[name].id, width), name, settings=settings
    )


def _recover_template(
    name: str, template: str, char: str, settings: DialectSettings | None
) -> _Template:
    """Tag a plain-string template, recovering its setters from the language's."""
    if char not in template:
        # An ordinary program and an already-filled template look the
        # same from here, so the message names both.
        raise with_hint(
            TemplateError(
                f"this {name} text has no run of {char!r} to fill: it is either "
                f"an ordinary program or a template instantiate() has already "
                f"been applied to, and generate({name!r}, table) returns the "
                f"template to fill"
            ),
            (
                "keep the original unfilled generate() result "
                "and instantiate it separately for each row"
            ),
        )
    try:
        pairs = recover_setters(LANGUAGES[name].id, template)
    except ValueError as exc:
        raise with_hint(
            TemplateError(f"not a {name} template: {exc}"),
            (
                "recreate the template with generate(); avoid "
                "manually editing its placeholder runs"
            ),
        ) from exc
    return _Template(template, name, char, pairs, settings=settings)


#: ``run(..., isolated=True)``'s deadline when ``timeout`` is None: the
#: subprocess needs one, and unbounded is what None means everywhere else.
_ISOLATED_TIMEOUT = 30.0

#: Characters a filename is made of, and a program mostly is not.
_PATH_CHARS = re.compile(r"^[\w./\\~-]+$")

#: A short extension, which is what makes a bare name look like a file.
_PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _looks_like_a_path(program: Program) -> bool:
    """Whether ``program`` is a filename someone meant to open.

    A path is legal text in most of these languages
    (``run("brainfuck", "prog.bf")`` returns a null byte).  Shape-based: one
    line of path characters, rooted (``/``, ``./``, ``../``, ``~/``) or ending
    in a short extension.  ``.``, ``..`` and ``~`` are accepted as programs
    (``~~`` is two legal source characters).
    """
    if not isinstance(program, str):
        return False
    if "\n" in program or not _PATH_CHARS.match(program):
        return False
    rooted = program.startswith(("/", "./", "../", "~/"))
    return rooted or bool(_PATH_EXTENSION.search(program))


def _check_runnable(language: str, program: Program) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are valid input to an interpreter and each produced a confident
    wrong answer (an unfilled template can run as nothing).  Shared by
    ``_check_program`` and the CLI's ``debug``.
    """
    name = resolve(language)
    if isinstance(program, (Raster, CompressedText)):
        return
    if not isinstance(program, str):
        # A non-source value otherwise fell through: an ``int`` leaked a
        # ``TypeError`` from ``char in program`` for a template language and
        # was silently accepted by every other one.
        raise ProgramError(
            f"program must be a string of source or a Raster, got "
            f"{type(program).__name__}"
        )
    if not LANGUAGES[name].path_like_source and _looks_like_a_path(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r})"
        )
    char = template_char(LANGUAGES[name].id)
    if char is not None and char in program:
        unfilled = LANGUAGES[name].example.unfilled
        if (
            unfilled is not None
            and not isinstance(program, _Template)
            and not unfilled(program)
        ):
            return
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled runs of {char!r} ({program.count(char)} characters); "
            f"fill them with esolangs.instantiate({name!r}, program, bits)"
        )


def _read_source(language: str, program: ProgramSource | _FileSource) -> Program:
    """Load source and check its kind and origin, allowing unfilled templates."""
    name = resolve(language)
    module = interpreter_module(name)
    loader = getattr(module, "load_source", text_source)
    program = loader(program)
    origin = getattr(program, "language", None)
    if origin is not None and origin != name:
        # The program says where it came from; a plain string does not and
        # is taken at its word (see :class:`_Tagged`).
        raise ProgramError(
            f"this program was generated for {origin}, so running it as "
            f"{name} would read it as {name} source -- which may well run, "
            f"and answer nonsense"
        )
    return program


def _check_program(
    language: str, program: ProgramSource, stdin: InputSource = ""
) -> Program:
    """Return ``program`` as source, having checked what can be checked here.

    Not a load check: it refuses the wrong *kind* of thing (a path as a
    string, an unfilled template, an unsupported container, an unreadable file, an
    unknown name) and type-checks ``stdin``, but ``_check_program("brainfuck",
    "[")`` returns the program and :func:`make_vm` raises ``ProgramError``.
    :func:`make_vm` calls this, so it cannot build a machine to check.
    A :class:`~pathlib.Path`
    is read here with one trailing newline stripped (some readers reject
    one), so the whole call is::

        path = importlib.resources.files("esolangs") / describe(lang)["examples"][0]
        run(lang, path, stdin=encode_inputs(lang, [0, 1]))

    Programs may also be UTF-8 text bytes, PNG bytes, or readable streams.
    The interpreter chooses the decoder. Stdin streams are checked without
    being consumed; execution snapshots their remaining text.
    """
    name = resolve(language)
    program = _read_source(name, program)
    check_input(stdin)
    _check_runnable(name, program)
    return program


def _run_bounded(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    *,
    max_steps: int,
    settings: DialectSettings | None = None,
    timeout: float | None = None,
    scale: int | None = None,
) -> str:
    """Execute a program cooperatively, returning output only on halt.

    Supply at least one bound. Limits raise :class:`ExecutionTimeoutError`
    with ``partial_output``. Works on Windows and worker threads; loading
    and individual steps cannot be interrupted.
    """
    check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    debugger = make_debugger(
        language, program, stdin=stdin, scale=scale, settings=settings
    )
    try:
        reason = debugger.run(max_steps=max_steps, timeout=timeout)
    except EsolangError as exc:
        exc.partial_output = debugger.output
        raise
    if reason != "halted":
        # One wording per bound: a timeout reads as it does unstepped.
        error = ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
            if reason == "timeout"
            else f"execution stopped at the {reason} bound"
        )
        error.partial_output = debugger.output
        error.bound = reason
        raise error
    return debugger.output


def run(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    timeout: float | None = None,
    seed: int | None = None,
    isolated: bool = False,
    max_steps: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Execute ``program`` and return its output.

    Args:
        program: Source or a :class:`~pathlib.Path`; a string shaped like a
            filename is refused.  A file loses one trailing newline and has
            CRLF and lone CR read as LF; a string keeps both.  Bytes hold UTF-8
            text or PNG; a readable stream is consumed from its current
            position and left open.
        stdin: Consumed verbatim in the language's input unit, without
            Boolean validation; binary is decoded as UTF-8.  Build a
            Boolean-generated program's stdin with :func:`encode_inputs`,
            which validates the bits.
        timeout: Wall-clock seconds (None: unbounded), via ``SIGALRM``, so it
            needs a Unix main thread; off it, use ``isolated`` or
            ``max_steps``.
        seed: Integer fixing the languages that draw
            (``describe(language)["random"]``); the rest refuse it.
        isolated: Run in a subprocess whose deadline covers startup and
            loading (``timeout``, or 30 seconds when None); works on Windows
            and in worker threads.  Excludes ``max_steps``.
        max_steps: Cooperative stepping bound, for text and raster programs;
            ``timeout`` then excludes loading and cannot interrupt a single
            step.  Excludes ``seed``.
        scale: Raster scale factor; detected when None.
        max_output: Isolated output cap in Unicode characters (zero allowed);
            the prefix is kept.
        max_memory: Linux worker virtual address space cap in bytes, including
            Python overhead; other platforms refuse it.  Loading in the
            parent is not capped.
        settings: Dialect choices.  Tagged source retains its own; these
            override individual ones.  Plain source uses these.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: An option is invalid or combined with one it excludes
            (``isolated`` with ``max_steps``, ``seed`` for a deterministic
            language).
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: The program does not load (base of the above).
        TemplateError: ``program`` is an unfilled template; see
            :func:`instantiate`.
        InputExhaustedError: A read past the end of ``stdin``.  Languages with
            ``describe(language)["eof_is_a_value"]`` supply a value instead,
            and some halt.
        ExecutionTimeoutError: ``timeout`` elapsed or ``max_steps`` ran out.
            Also a :class:`TimeoutError` and a ``HaltError``; catch it, not the
            base.
        InterpreterLimitError: ``max_output`` was exceeded, or the interpreter
            hit another implementation limit.
        HaltError: The program halted on an invalid operation (base of the two
            above).
        MissingDependencyError: The language needs an uninstalled extra
            (``esolangs[image]`` for PNG, ``esolangs[math]`` for Polynomial).
    """
    settings = effective_settings(language, program, settings)
    dialect_options(language, settings)  # validate before any route
    check_scale_for(language, scale)
    check_seed(seed)
    check_timeout(timeout)
    check_flag(isolated, "isolated")
    check_limits(max_output, max_memory, isolated=isolated)
    if isolated:
        if max_steps is not None:
            raise with_hint(
                ArgumentError("isolated and max_steps are mutually exclusive"),
                "use isolation with timeout, or use max_steps without isolation",
            )
        deadline = _ISOLATED_TIMEOUT if timeout is None else timeout
        # Every option defaults to None, so passing them unconditionally
        # matches the old per-combination cascade exactly.
        return _run_isolated(
            language,
            program,
            stdin,
            deadline,
            seed=seed,
            scale=scale,
            max_output=max_output,
            max_memory=max_memory,
            settings=settings,
        )
    if max_steps is not None:
        if seed is not None:
            raise with_hint(
                ArgumentError("seed is unsupported with max_steps"),
                (
                    "omit max_steps for seeded execution and use "
                    "timeout to bound the run"
                ),
            )
        return _run_bounded(
            language,
            program,
            stdin,
            max_steps=max_steps,
            timeout=timeout,
            scale=scale,
            settings=settings,
        )
    # Before ``_run``, so every ValueError from the run is the
    # interpreter's.  The message names both routes out for a worker
    # thread.  Not a silent fallback to stepping: two paths for one
    # function is how they diverged (``tests/runtime/test_stepping_parity.py``).
    check_signal_timeout(
        timeout,
        "the timeout guard uses SIGALRM and needs a Unix main thread; "
        "off it, either pass isolated=True, which times a subprocess, or "
        "bound the run cooperatively with "
        "esolangs.debugger.make_debugger(language, program, stdin)"
        ".run(timeout=...), "
        "which steps and so needs no signal",
    )
    name = resolve(language)
    program = _check_program(name, program, stdin)
    settings = effective_settings(name, program, settings)
    dialect = dialect_options(name, settings)
    run_fn = interpreter_module(name).run
    program_args, options = prepare_call(name, program, run_fn, scale=scale, seed=seed)
    options.update(dialect)
    if options:
        run_fn = partial(run_fn, **options)
    io_obj = ScriptedIO(stdin)
    with interpreter_errors(
        f"the {name} interpreter recursed deeper than CPython's stack "
        "limit allows on this program; the program is well formed, and "
        "sys.setrecursionlimit can raise the limit if this interpreter's "
        "depth grows with program size",
        io_obj,
        language=name,
    ):
        _run(run_fn, program_args, io_obj, timeout)
    return io_obj.getvalue()


def _run(
    run_fn: Callable[..., Any],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float | None,
) -> None:
    """Run ``run_fn``, applying the wall-clock ``timeout`` guard when set."""
    if timeout is None:
        run_fn(program, io_obj)
    else:
        run_under_alarm(run_fn, program, io_obj, timeout)
