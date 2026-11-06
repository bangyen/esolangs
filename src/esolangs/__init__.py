"""Generate programs, run supplied source, and describe languages.

Public operations split by who supplies the program:

* Generator-made: ``generate`` returns a program artifact or template;
  ``instantiate`` fills a template into a runnable artifact.
* Caller-supplied: ``run`` returns output, input consumption and completion
  evidence in an immutable execution result.
  Stepping and debugging live in :mod:`esolangs.debugger`.
* Contract adapters: ``encode_inputs`` spells input bits as stdin,
  ``read_answer`` extracts an answer bit from output,
  ``save_program`` writes native source files, and
  ``dump_program``/``load_program`` preserve source in portable JSON.
* Catalog: ``describe`` and ``list_languages`` provide registry facts.

Boolean evaluation over every row is private certification machinery,
not public API.  ``Language(name)`` binds these functions to one language.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
"""

import importlib
import re
from collections.abc import Callable
from functools import cache, partial
from math import isqrt
from typing import TYPE_CHECKING, Any, cast

from esolangs._language import Language
from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
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
from esolangs.generation.wrap import (
    balance_program,
    wrap_program,
)
from esolangs.portable import dump_program, load_program, save_program
from esolangs.raster import Raster
from esolangs.registry import (
    LANGUAGES,
    SourceKind,
    render_template,
    resolve,
    template_char,
    template_setters,
)
from esolangs.registry._describe import (
    LanguageInfo,
    describe,
    list_languages,
)
from esolangs.results import ExecutionResult
from esolangs.runtime._answers import encode_inputs, read_answer
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import (
    check_signal_timeout,
    interpreter_module,
    prepare_call,
    run_prepared,
    run_under_alarm,
)
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._isolated import run_isolated_result as _run_isolated_result
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime._source import (
    ProgramSource,
    _FileSource,
    check_scale_for,
    effective_scale,
    source_for,
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
from esolangs.vm import _capture_observation, _capture_result

#: From the installed distribution (a hand-kept copy said 0.1.0 at 0.2.0);
#: the fallback covers an uninstalled tree.  Read on first access, not
#: import: ``importlib.metadata`` was 23ms of the 56ms import (PEP 562).
#: Hidden from type checkers, which otherwise typed ``esolangs.generat`` as
#: ``str`` and ``from esolangs import generat`` as ``Any``.
if TYPE_CHECKING:
    __version__: str
else:

    def __getattr__(name: str) -> str:
        """Resolve ``__version__`` lazily; everything else is a normal miss."""
        if name != "__version__":
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        import importlib.metadata

        try:
            version = importlib.metadata.version("esolangs")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            # A source tree that was never installed.
            version = "0.0.0+unknown"
        globals()["__version__"] = version
        return version


def _bind_annotation_names() -> None:
    """Let ``typing.get_type_hints`` resolve the public classes' annotations.

    ``artifacts``, ``compressed`` and ``raster`` name ``DialectSettings`` only
    under ``TYPE_CHECKING`` (``settings`` imports the registry, which imports
    them), so ``get_type_hints(Raster)`` raised NameError on 3.12 to 3.14.
    """
    import esolangs.artifacts
    import esolangs.compressed
    import esolangs.raster

    for module in (
        esolangs.artifacts,
        esolangs.compressed,
        esolangs.raster,
    ):
        module.DialectSettings = DialectSettings  # type: ignore[attr-defined]


_bind_annotation_names()


#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ArgumentError",
    "Artifact",
    "CompressedText",
    "DialectSettings",
    "EsolangError",
    "ExecutionResult",
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
    "ProgramArtifact",
    "ProgramError",
    "ProgramNotFoundError",
    "ProgramSource",
    "Raster",
    "TemplateArtifact",
    "TemplateBindings",
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
    "save_program",
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
) -> Artifact:
    """Return an immutable program or template computing ``truth_table``.

    Languages that embed inputs in the program text return a *template*: one
    run of one character per input (``$`` unless the language declares
    another), as long as the code :func:`instantiate` fills it with.
    A TemplateArtifact exposes fill(bits); run refuses an unfilled template.
    Records retain source, language, settings and raster scale explicitly.

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
        if LANGUAGES[resolve(language)].runtime.source_kind is not SourceKind.RASTER:
            raise with_hint(
                ArgumentError("scale is only supported for raster generators"),
                "omit scale for text languages; apply it only to raster source",
            )
        artifact = cast(
            ProgramArtifact[Raster],
            generate(
                language, truth_table, width=width, balance=balance, settings=settings
            ),
        )
        return ProgramArtifact(
            artifact.source.upscaled(scale), artifact.language, settings, scale
        )
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
    backend = lang.backend
    if backend is None:
        # The language reads input but cannot meet the generator's size contract.
        raise ArgumentError(
            f"{resolved} has no boolean generator under this repository's "
            f"generator contracts. `esolangs list --details` marks it 'int'"
        )
    fn = backend.generate
    check_table_text(truth_table)
    check_width(width)
    laid_out = width is not None and backend.layout_width
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
    if lang.runtime.source_kind is SourceKind.RASTER:
        if not isinstance(generated, Raster):  # pragma: no cover - registry invariant
            raise ProgramError(f"{resolved}'s generator did not return a Raster")
        return ProgramArtifact(generated, resolved, settings, scale=1)
    if isinstance(generated, CompressedText):
        return ProgramArtifact(generated.wrapped(width), resolved, settings)
    slots = str(generated)
    if not lang.parameterized:
        program = slots if laid_out else wrap_program(slots, lang.id, width)
        return ProgramArtifact(program, resolved, settings)
    # The generator spells each input as a run; the public template is
    # that, wrapped with every run whole (see render_template).
    inputs = len(truth_table).bit_length() - 1
    wrap_to = None if laid_out else width
    text, char, pairs = render_template(lang.id, slots, inputs, wrap_to)
    return TemplateArtifact(text, resolved, TemplateBindings(char, pairs), settings)


def _generate_balanced(
    language: str,
    truth_table: str,
    options: dict[str, Any],
    settings: DialectSettings | None,
) -> Artifact:
    """Return ``generate(..., balance=True)``: the default, rebuilt squarest."""
    default = generate(language, truth_table, settings=settings)
    source = default.source
    name = resolve(language)
    lang = LANGUAGES[name]
    backend = lang.backend
    assert backend is not None  # the default was generated above
    balancer = backend.balance
    if isinstance(source, CompressedText):
        return ProgramArtifact(
            source.wrapped(max(1, isqrt(CELL_ASPECT * len(source)))), name, settings
        )
    if isinstance(source, Raster):
        if balancer is None:
            return default
        raster_balance = cast(Callable[[str, Raster], Raster], balancer)
        return ProgramArtifact(
            raster_balance(truth_table, source), name, settings, scale=1
        )
    if balancer is not None:
        # A dialect setting the balancer names changes what it rebuilds.
        accepted = backend.balance_parameters
        balance_options = {
            key: value for key, value in options.items() if key in accepted
        }
        text = cast(Callable[..., str], balancer)(
            truth_table, source, **balance_options
        )
        if isinstance(default, TemplateArtifact):
            text, char, pairs = render_template(lang.id, text, default.bindings.inputs)
            return TemplateArtifact(text, name, TemplateBindings(char, pairs), settings)
        return ProgramArtifact(text, name, settings)
    if isinstance(default, TemplateArtifact):
        bindings = default.bindings
        marked = mark_runs(default.source, bindings.char, bindings.setters)
        text = unmark(balance_program(marked, lang.id), bindings.char, bindings.inputs)
        return TemplateArtifact(text, name, bindings, settings)
    return ProgramArtifact(balance_program(source, lang.id), name, settings)


def _is_template_for(
    template: TemplateArtifact,
    name: str,
    truth_table: str,
    settings: DialectSettings | None = None,
) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    Compare wrapping using the language's whitespace rules.
    """
    canonical = generate(name, truth_table, settings=settings)
    if not isinstance(canonical, TemplateArtifact):
        return False
    bindings = canonical.bindings
    expected = TemplateBindings(
        bindings.char,
        template_setters(LANGUAGES[name].id, template.source, bindings.inputs),
    )
    if template.bindings != expected:
        return False
    text = template.source
    plain = canonical.source
    if text == plain:
        return True
    backend = LANGUAGES[name].backend
    assert backend is not None  # generate above refuses absent backends
    width_aware = backend.layout_width

    @cache
    def layout(width: int) -> Program:
        return generate(name, truth_table, width=width, settings=settings).source

    # Layouts may switch representations; their floor is a named candidate,
    # unlike whitespace wrapping, so compare that template exactly too.
    if width_aware and text == layout(1):
        return True
    # A layout built for its own widest line: ArrowQueue's ``width=5`` shifts
    # the setter column, matching neither the default nor ``layout(1)``.
    widest = max(map(len, text.splitlines()), default=0)
    if width_aware and widest and text == layout(widest):
        return True
    same_layout = backend.same_layout or (
        lambda template, plain, _layout: same_up_to_wrapping(template, plain)
    )
    return same_layout(text, plain, layout)


def instantiate(
    language: str,
    template: Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    width: int | None = None,
    truth_table: str | None = None,
    settings: DialectSettings | None = None,
) -> ProgramArtifact[str]:
    """Fill a parameterized generator's template with ``bits``.

    Hand substitution fails: each language spells a set-input its own way.  A
    TemplateArtifact from :func:`generate` retains explicit bindings.
    Retained dialect choices follow the
    filled program; explicit ``settings`` override individual ones.

    Args:
        template: The TemplateArtifact returned by :func:`generate` or portable loading.
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
    name = resolve(language)
    settings = effective_settings(name, template, settings)
    dialect_options(name, settings)
    check_width(width)
    body = (
        template.source
        if isinstance(template, (ProgramArtifact, TemplateArtifact))
        else template
    )
    if isinstance(body, Raster):
        raise with_hint(
            TemplateError(
                f"{name} source is a Raster, and raster programs read their "
                "inputs rather than embedding them, so there is nothing to instantiate"
            ),
            "run the raster with stdin=encode_inputs(language, bits)",
        )
    if not LANGUAGES[name].parameterized:
        raise with_hint(
            TemplateError(
                f"{name} reads its inputs rather than embedding them, "
                "so there is nothing to instantiate"
            ),
            "run the generated program with stdin=encode_inputs(language, bits)",
        )
    if not isinstance(template, TemplateArtifact):
        raise with_hint(
            TemplateError(
                "template must be the TemplateArtifact generate() returned, "
                f"got {type(template).__name__}"
            ),
            "retain generate()'s template or restore it with load_program()",
        )
    if template.language != name:
        raise TemplateError(f"template belongs to {template.language}, not {name}")
    if truth_table is not None and not _is_template_for(
        template, name, truth_table, settings
    ):
        raise with_hint(
            TemplateError(
                f"this is not the template generate({name!r}, {truth_table!r}) "
                "returns, so filling it would produce a program that "
                "does not compute that table"
            ),
            "regenerate the template from the intended language and truth table",
        )
    bits = check_bits(bits, "bits")
    artifact = template
    inputs = artifact.bindings.inputs
    if len(bits) != inputs:
        given = (
            f"{len(bits)} bit was given"
            if len(bits) == 1
            else f"{len(bits)} bits were given"
        )
        raise with_hint(
            TemplateError(
                f"this {name} template has {inputs} input"
                f"{'' if inputs == 1 else 's'}, but {given}"
            ),
            f"pass exactly {inputs} integer bits to instantiate(), one per input",
        )
    filled = artifact.fill(bits)
    program = wrap_program(filled.source, LANGUAGES[name].id, width)
    if program is not filled.source or settings is not filled.settings:
        filled = ProgramArtifact(program, name, settings)
    return filled


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
    in a short extension, naming something (a letter).  ``.``, ``..``,
    ``~~`` and Befunge's ``/`` are accepted as programs.
    """
    if not isinstance(program, str):
        return False
    if "\n" in program or not _PATH_CHARS.match(program):
        return False
    if not re.search("[A-Za-z]", program):
        return False
    rooted = program.startswith(("/", "./", "../", "~/"))
    return rooted or bool(_PATH_EXTENSION.search(program))


def _check_runnable(language: str, program: Program) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are valid input to an interpreter and each produced a confident
    wrong answer (an unfilled template can run as nothing).  Shared by
    ``_check_program`` and :func:`make_vm`.
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
    if not LANGUAGES[name].runtime.path_like_source and _looks_like_a_path(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r}); "
            f"source that only looks like one runs with a trailing newline"
        )
    char = template_char(LANGUAGES[name].id)
    if char is not None and char in program:
        backend = LANGUAGES[name].backend
        assert backend is not None
        spec = backend.template
        assert spec is not None  # template_char uses the same declaration
        unfilled = spec.unfilled
        if unfilled is not None and not unfilled(program):
            return
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled runs of {char!r} ({program.count(char)} characters); "
            f"fill them with esolangs.instantiate({name!r}, program, bits)"
        )


def _read_source(language: str, program: ProgramSource | _FileSource) -> Program:
    """Load source and check its kind and origin, allowing unfilled templates."""
    name = resolve(language)

    def check_origin(source: object) -> None:
        if isinstance(
            source, (ProgramArtifact, TemplateArtifact, Raster, CompressedText)
        ):
            origin = source.language
            if origin is not None and origin != name:
                raise ProgramError(
                    f"this program was generated for {origin}, so running it as "
                    f"{name} would read it as {name} source -- which may well run, "
                    "and answer nonsense"
                )

    check_origin(program)
    if isinstance(program, (ProgramArtifact, TemplateArtifact)):
        program = program.source
    check_origin(program)
    program = source_for(name, program)
    check_origin(program)
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
    if isinstance(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    explicit = isinstance(program, ProgramArtifact)
    program = _read_source(name, program)
    check_input(stdin)
    if not explicit:
        _check_runnable(name, program)
    return program


def _run_bounded_result(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    *,
    max_steps: int,
    settings: DialectSettings | None = None,
    timeout: float | None = None,
    scale: int | None = None,
    seed: int | None = None,
) -> ExecutionResult:
    """Execute cooperatively, returning a result only after completed halt.

    Supply at least one bound. Limits raise :class:`ExecutionTimeoutError`
    with ``partial_output``. Works on Windows and worker threads; loading
    and individual steps cannot be interrupted.
    """
    check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    debugger = make_debugger(
        language, program, stdin=stdin, scale=scale, settings=settings, seed=seed
    )
    try:
        reason = debugger.run(max_steps=max_steps, timeout=timeout)
    except EsolangError as exc:
        exc.partial_output = debugger.output
        observation = exc.execution or _capture_observation(debugger.vm)
        exc.execution = observation._replace(steps=debugger._steps)  # noqa: SLF001
        raise
    if reason != "halted":
        # One wording per bound: a timeout reads as it does unstepped.
        error = ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
            if reason == "timeout"
            else f"execution stopped at the {reason} bound"
        )
        error.partial_output = debugger.output
        error.bound = "timeout" if reason == "timeout" else "max_steps"
        error.execution = _capture_observation(debugger.vm)._replace(
            steps=debugger._steps  # noqa: SLF001
        )
        raise error
    return _capture_result(debugger.vm)._replace(steps=debugger._steps)  # noqa: SLF001


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
) -> ExecutionResult:
    """Execute ``program`` and return output, input usage and completion evidence.

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
            and in worker threads. Can combine with ``max_steps``.
        max_steps: Cooperative stepping bound, for text and raster programs;
            ``timeout`` then excludes loading and cannot interrupt a single
            step. With isolation, the worker also enforces its wall-clock
            deadline.
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
        ArgumentError: An option is invalid or inapplicable
            (for example, ``seed`` for a deterministic language).
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
            (``esolangs[image]`` for PNG).
    """
    return _run_result(
        language,
        program,
        stdin=stdin,
        timeout=timeout,
        seed=seed,
        isolated=isolated,
        max_steps=max_steps,
        scale=scale,
        max_output=max_output,
        max_memory=max_memory,
        settings=settings,
    )


def _run_result(
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
) -> ExecutionResult:
    """Execute through one route, retaining its result metadata."""
    record = isinstance(program, ProgramArtifact)
    settings = effective_settings(language, program, settings)
    scale = effective_scale(language, program, scale)
    dialect_options(language, settings)  # validate before any route
    check_scale_for(language, scale)
    check_seed(seed)
    check_timeout(timeout)
    check_flag(isolated, "isolated")
    check_limits(max_output, max_memory, isolated=isolated)
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    if isolated:
        deadline = _ISOLATED_TIMEOUT if timeout is None else timeout
        # Every option defaults to None, so passing them unconditionally
        # matches the old per-combination cascade exactly.
        return _run_isolated_result(
            language,
            program,
            stdin,
            deadline,
            seed=seed,
            scale=scale,
            max_output=max_output,
            max_memory=max_memory,
            settings=settings,
            max_steps=max_steps,
        )
    if max_steps is not None:
        return _run_bounded_result(
            language,
            program,
            stdin,
            max_steps=max_steps,
            timeout=timeout,
            scale=scale,
            settings=settings,
            seed=seed,
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
    if not record:
        settings = effective_settings(name, program, settings)
    scale = effective_scale(language, program, scale)
    entrypoint = LANGUAGES[name].runtime.completion_entrypoint
    run_fn = getattr(interpreter_module(name), entrypoint)
    program_args, options = prepare_call(
        name, program, ExecutionContext(scale=scale, seed=seed, settings=settings)
    )
    if options:
        run_fn = partial(run_fn, **options)
    io_obj = ScriptedIO(stdin)
    return run_prepared(
        name,
        run_fn,
        program_args,
        io_obj,
        timeout,
    )


def _run[T](
    run_fn: Callable[..., T],
    program: RunnerProgram,
    io_obj: ScriptedIO,
    timeout: float | None,
) -> T:
    """Return ``run_fn``'s result, applying the wall-clock guard when set."""
    if timeout is None:
        return run_fn(program, io_obj)
    return run_under_alarm(run_fn, program, io_obj, timeout)
