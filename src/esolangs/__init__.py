"""Generate programs, run supplied source, and describe languages.

``generate`` builds source; ``instantiate`` fills templates; ``run`` executes
caller-supplied source.  Boolean evaluation is private certification
machinery, not public API.
``encode_inputs`` and ``read_answer`` handle rows.
``dump_program`` and ``load_program`` preserve source provenance in portable JSON.
``describe`` and ``list_languages``
provide registry facts. Stepping and debugging live in :mod:`esolangs.debugger`.
``Language(name)`` binds these functions to one language.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
"""

import importlib
import re
import signal
import threading
from collections.abc import Callable, Sequence
from functools import cache, partial
from typing import Any, TypedDict, cast

from esolangs._answers import encode_inputs, read_answer
from esolangs._describe import (
    _EXAMPLES,
    LanguageInfo,
    describe,
    list_languages,
)
from esolangs._evaluate import _DEFAULT, _Default
from esolangs._execution import (
    check_signal_timeout,
    interpreter_errors,
    interpreter_module,
    prepare_call,
)
from esolangs._isolated import run_isolated as _run_isolated
from esolangs._language import Language
from esolangs._program import Program, RunnerProgram
from esolangs._source import (
    InputSource,
    ProgramSource,
    check_input,
    check_scale_for,
    text_source,
)
from esolangs._validate import check_bits, check_scale, check_timeout, check_width
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    HaltError,
    InputExhaustedError,
    InputMismatchWarning,
    InterpreterLimitError,
    MissingDependencyError,
    ProgramError,
    ProgramNotFoundError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.source_hints import with_hint
from esolangs.portable import dump_program, load_program
from esolangs.raster import Raster
from esolangs.registry import (
    INTERPRETERS,
    LANGUAGES,
    SourceKind,
    parameterized_ids,
    recover_setters,
    render_template,
    resolve,
    template_body,
    template_char,
)
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.tagged import _Tagged, _Template
from esolangs.tools.balance import BALANCERS as _BALANCERS
from esolangs.tools.helpers import mark_runs, unmark

# Imported private: it takes a *generator function*, not a language name, so
# a caller reaching for ``esolangs.takes_width("LaserFuck")`` got False for
# every language in the registry, contradicting both its own docstring and
# ``describe(...)["width_aware"]`` -- which is the question they were asking.
from esolangs.tools.wrap import (
    balance_program,
    wrap_program,
)
from esolangs.tools.wrap import takes_width as _takes_width


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
    "ArgumentError",
    "DialectSettings",
    "EsolangError",
    "ExecutionTimeoutError",
    "GeneratorCapError",
    "HaltError",
    "InputExhaustedError",
    "InputMismatchWarning",
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
    width: int | None = None,
    *,
    balance: bool = False,
    scale: int = 1,
    settings: DialectSettings | None = None,
) -> Program:
    """Return a program in ``language`` computing ``truth_table``.

    ``truth_table`` is a binary string of length ``2**n``, MSB first, so its
    length implies ``n``.  Some languages embed their inputs in the
    program text; for those this returns a *template* with each input as a
    run of one character (``$`` unless the language declares another), one
    run per input, exactly as long as the code :func:`instantiate` fills it
    with.  ``describe(language)["parameterized"]`` says which you have; a
    template handed to :func:`run` is refused.

    ``width`` is a request, not a bound (``describe(language)["width_effect"]``):
    it does nothing where newlines are semantic, and a single token longer
    than the width still overruns it.  A template wraps with each run kept
    whole, so every row breaks in the same places.
    ``balance`` minimizes the rendered width/height difference across supported
    layouts, breaking ties by source length (raster pixel area), then width.
    Token and routing constraints can prevent a square layout.
    Raster ``scale`` replicates pixels after layout; 1 preserves native output.
    Tagged results retain ``settings`` for execution.
    """
    options = dialect_options(language, settings)
    check_scale(scale)
    if scale != 1:
        if LANGUAGES[resolve(language)].source_kind is not SourceKind.RASTER:
            raise with_hint(
                ArgumentError("scale is only supported for raster generators"),
                ("omit scale for text languages; apply it only to raster source"),
            )
        source = generate(
            language, truth_table, width, balance=balance, settings=settings
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
        default = generate(language, truth_table, settings=settings)
        lang = LANGUAGES[resolve(language)]
        balancer = _BALANCERS.get(lang.id)
        if isinstance(default, Raster):
            if balancer is None:
                return default
            raster_balance = cast(Callable[[str, Raster], Raster], balancer)
            return raster_balance(truth_table, default).tagged(
                resolve(language), settings=settings
            )
        if balancer is not None:
            # Alight notation changes a balancer's reconstructed instructions.
            balance_options = options if lang.id == "alight" else {}
            text = cast(Callable[..., str], balancer)(
                truth_table, default, **balance_options
            )
            if isinstance(default, _Template):
                text, char, pairs = render_template(lang.id, text, default.inputs)
                return _Template(text, default.language, char, pairs, settings=settings)
            return _Tagged(text, resolve(language), settings=settings)
        if isinstance(default, _Template):
            marked = mark_runs(default, default.char, default.setters)
            text = unmark(
                balance_program(marked, lang.id), default.char, default.inputs
            )
            return _Template(
                text, default.language, default.char, default.setters, settings=settings
            )
        text = balance_program(default, lang.id)
        return _Tagged(text, resolve(language), settings=settings)
    resolved = resolve(language)
    lang = LANGUAGES[resolved]
    fn = lang.boolean
    if fn is None:
        # Unary reads input but cannot meet the generator's size contract.
        raise ArgumentError(
            f"{resolved} has no boolean generator under this repository's "
            f"generator contracts. `esolangs list --details` marks it 'int'"
        )
    if not isinstance(truth_table, str):
        raise with_hint(
            TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            ),
            ("pass truth-table text, for example '0110' for two-input XOR"),
        )
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
        # Tagged the way a text program is ``_Tagged``: a Line raster fed to
        # Piet otherwise passed ``_check_program`` and answered '', a
        # confident garbage result rather than a refusal.
        return generated.tagged(resolved, settings=settings)
    slots = str(generated)
    if lang.id not in parameterized_ids():
        program = slots if laid_out else wrap_program(slots, lang.id, width)
        return _Tagged(program, resolved, settings=settings)
    # The generator spells each input as a run; the public template is
    # that, wrapped with every run whole (see render_template).
    inputs = len(truth_table).bit_length() - 1
    wrap_to = None if laid_out else width
    text, char, pairs = render_template(lang.id, slots, inputs, wrap_to)
    return _Template(text, resolved, char, pairs, settings=settings)


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
    language_id = LANGUAGES[name].id
    generator = LANGUAGES[name].boolean
    width_aware = generator is not None and _takes_width(generator)
    observed_width = max(1, max(map(len, template.splitlines()), default=0))

    @cache
    def layout(width: int) -> Program:
        return generate(name, truth_table, width, settings=settings)

    def same_tokens(program: Program) -> bool:
        return isinstance(program, str) and template.split() == program.split()

    # Layouts may switch representations; their floor is a named candidate,
    # unlike whitespace wrapping, so compare that template exactly too.
    if width_aware and template == layout(1):
        return True
    if language_id == "minsky_swap" and template in (
        layout(10),
        layout(15),
    ):
        return True
    if language_id == "back" and template == layout(observed_width):
        return True
    if language_id == "intercal":
        from esolangs.tools.intercal import _intercal_tokens

        narrow = layout(1)
        if isinstance(narrow, str) and _intercal_tokens(template) == _intercal_tokens(
            narrow
        ):
            return True
        # Its primitive layout fits between the natural and simplified floors.
        # Rebuild at the observed bound rather than accepting equivalent syntax.
        if template == layout(observed_width):
            return True
    if language_id in {"minifuck", "smallfuck"} and width_aware:
        for width in (1, 4):
            narrow = str(layout(width))
            if language_id == "minifuck" and narrow.startswith("q\n"):
                # Exact layouts were checked above; these LF absorb skips.
                continue
            if template.replace("\n", "") == narrow.replace("\n", ""):
                return True
    if language_id in {"fractran", "bitdeque", "crement"} and width_aware:
        narrow = layout(1)
        if same_tokens(narrow):
            return True
    if language_id in {"fractran", "crement"}:
        # Short setters coexist with fitting layouts that retain the old pair.
        observed = layout(observed_width)
        if same_tokens(observed):
            return True
    if language_id == "underload":
        from esolangs.tools.underload import _underload_layout_tokens

        for width in (1, 4):
            narrow = str(layout(width))
            if isinstance(narrow, str) and _underload_layout_tokens(
                template
            ) == _underload_layout_tokens(narrow):
                return True
    # BIO discards whitespace; the other three tokenize on it. Their wrappers
    # replace spaces with newlines, so removing newlines loses token boundaries.
    if language_id == "bio":
        return "".join(template.split()) == "".join(plain.split())
    if language_id in {"bitdeque", "ram0", "fractran"}:
        return same_tokens(plain)
    return template == plain or (
        "\n" not in plain and template.replace("\n", "") == plain
    )


def instantiate(
    language: str,
    template: str,
    bits: list[int] | tuple[int, ...],
    width: int | None = None,
    truth_table: str | None = None,
    *,
    settings: DialectSettings | None = None,
) -> str:
    """Fill a parameterized generator's template with ``bits``.

    Substituting the runs by hand does not work: each language spells a
    set-input its own way.  A language whose generator reads its inputs, or
    a template from a different language, raises
    :class:`~esolangs.exceptions.TemplateError`.  ``width`` applies here too.
    A template :func:`generate` returned carries its setters; a plain string
    has them recovered from the language's own. Retained dialect choices follow
    the filled program; explicit settings overrides individual choices.
    """
    settings = effective_settings(language, template, settings)
    dialect_options(language, settings)
    check_width(width)
    name = resolve(language)
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
        # `instantiate("Minifuck", "hello $$", [1])` filled it happily.
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
            ("run the generated program with stdin=encode_inputs(language, bits)"),
        )
    origin = getattr(template, "language", None)
    if origin is not None and origin != name:
        raise with_hint(
            TemplateError(
                f"this template came from generate({origin!r}, ...), so filling "
                f"it as {name} would substitute {name}'s setter code into a "
                f"{origin} program -- which runs, and answers the wrong row"
            ),
            ("instantiate the template using the language that generated it"),
        )
    bits = check_bits(bits, "bits")
    tagged = template if isinstance(template, _Template) else None
    if tagged is None:
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
        tagged = _Template(template, name, char, pairs, settings=settings)
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
    (``~~`` is two ArrowQueue commands).
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
    wrong answer (Minifuck runs a ``$`` run as nothing).  Public because the
    debugger stepped a template to ``output: '0'``; the CLI's ``debug`` calls it.
    """
    name = resolve(language)
    if isinstance(program, Raster):
        return
    if not isinstance(program, str):
        # A non-source value otherwise fell through: an ``int`` leaked a
        # ``TypeError`` from ``char in program`` for a template language and
        # was silently accepted by every other one.
        raise ProgramError(
            f"program must be a string of source or a Raster, got "
            f"{type(program).__name__}"
        )
    # /// uses path-shaped strings as substitution rules.
    if LANGUAGES[name].id != "slashes" and _looks_like_a_path(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r})"
        )
    char = template_char(LANGUAGES[name].id)
    if char is not None and char in program:
        if LANGUAGES[name].id == "slashes" and not isinstance(program, _Template):
            from esolangs.tools.slashes import _is_unfilled_template

            if not _is_unfilled_template(program):
                return
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled runs of {char!r} ({program.count(char)} characters); "
            f"fill them with esolangs.instantiate({name!r}, program, bits)"
        )


def _read_source(language: str, program: ProgramSource) -> Program:
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
    is read here with one trailing newline stripped (CV(N)(C), Grapheme and
    NoComment reject one), so the whole call is::

        path = pathlib.Path(describe(lang)["examples"][0])
        run(lang, path, encode_inputs(lang, [0, 1]))

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
    from esolangs._validate import check_whole

    check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    from esolangs.debugger import make_debugger

    debugger = make_debugger(language, program, stdin, scale=scale, settings=settings)
    try:
        reason = debugger.run(max_steps=max_steps, timeout=timeout)
    except EsolangError as exc:
        exc.partial_output = debugger.output
        raise
    if reason != "halted":
        error = ExecutionTimeoutError(f"execution stopped at the {reason} bound")
        error.partial_output = debugger.output
        raise error
    return debugger.output


def run(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    timeout: float | _Default | None = _DEFAULT,
    seed: int | None = None,
    *,
    isolated: bool = False,
    max_steps: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Execute ``program`` and return its output.

    Raster scale is detected unless ``scale`` supplies an explicit factor.
    Tagged source retains dialect choices; explicit ``settings`` overrides
    individual retained choices. Plain source uses the supplied settings.
    ``program`` is source or a :class:`~pathlib.Path`; a string shaped like a
    filename is refused.  A Path and its text are
    not quite the same argument: a file loses one trailing newline, a
    string keeps it.

    Bytes contain UTF-8 text or PNG source, as accepted by the interpreter.
    Readable streams are consumed from their current position and left open.
    Binary stdin is decoded as UTF-8, preserving the same character stream
    as text stdin.

    ``isolated=True`` uses a subprocess deadline, including startup and loading
    (30 seconds by default). It works on Windows and worker threads.
    ``max_steps`` uses cooperative stepping; its optional timeout excludes loading
    and cannot interrupt a single step. Text and raster programs support stepping.
    Isolation and step bounds cannot be combined; stepping does not support seed.
    ``max_output`` bounds isolated output in Unicode characters, retaining the
    prefix and raising ``InterpreterLimitError`` when exceeded; zero is allowed.
    ``max_memory`` caps Linux worker virtual address space in bytes, including
    Python overhead; other platforms refuse it. Loading in the parent is not capped.

    ``stdin`` is consumed verbatim using the language's input unit, without
    Boolean validation. Reading past
    the end usually raises :class:`~esolangs.exceptions.InputExhaustedError`;
    ``describe(language)["eof_is_a_value"]`` marks languages supplying a value.
    Some halt instead. Use the private stdin check
    explicitly to validate input for a Boolean-generated program.

    ``timeout`` is wall-clock seconds and raises
    :class:`~esolangs.exceptions.ExecutionTimeoutError` (a
    :class:`TimeoutError` and a :class:`~esolangs.exceptions.HaltError`; catch
    it, not the base).  It is ``SIGALRM``, so needs a Unix main thread; off it,
    :meth:`Debugger.run` bounds by stepping.  ``seed`` fixes the five
    languages that draw.  An unloadable program raises
    :class:`~esolangs.exceptions.ProgramError`.
    """
    settings = effective_settings(language, program, settings)
    dialect = dialect_options(language, settings)
    check_scale_for(language, scale)
    if isinstance(timeout, _Default):
        timeout = 30.0 if isolated else None
    check_timeout(timeout)
    from esolangs._isolated import check_memory

    check_memory(max_memory, isolated=isolated)
    if max_output is not None:
        from esolangs._validate import check_whole

        check_whole(max_output, "max_output")
        if not isolated:
            raise with_hint(
                ArgumentError("max_output requires isolated=True"),
                ("set isolated=True to bound output, or omit max_output"),
            )
    if isolated:
        if max_steps is not None:
            raise with_hint(
                ArgumentError("isolated and max_steps are mutually exclusive"),
                ("use isolation with timeout, or use max_steps without isolation"),
            )
        if timeout is None:
            raise with_hint(
                ArgumentError("isolated execution requires a finite timeout"),
                ("set a positive finite timeout, for example timeout=5.0"),
            )
        if max_output is not None or max_memory is not None:
            return _run_isolated(
                language,
                program,
                stdin,
                timeout,
                seed=seed,
                scale=scale,
                max_output=max_output,
                max_memory=max_memory,
                settings=settings,
            )
        if settings is not None:
            return _run_isolated(
                language,
                program,
                stdin,
                timeout,
                seed=seed,
                scale=scale,
                settings=settings,
            )
        if scale is None:
            return _run_isolated(language, program, stdin, timeout, seed=seed)
        return _run_isolated(language, program, stdin, timeout, seed=seed, scale=scale)
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
    # function is how they diverged (``tests/test_stepping_parity.py``).
    check_signal_timeout(
        timeout,
        "the timeout guard uses SIGALRM and needs a Unix main thread; "
        "off it, either bound the run cooperatively with "
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
        _run_timed_signal(run_fn, program, io_obj, timeout)


def _run_timed_signal(
    run_fn: Callable[..., Any],
    program: RunnerProgram,
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
    pending, interval = signal.setitimer(signal.ITIMER_REAL, timeout)
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
            signal.setitimer(signal.ITIMER_REAL, pending, interval)
