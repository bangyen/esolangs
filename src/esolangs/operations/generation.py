"""Generate and bind explicit program artifacts."""

from collections.abc import Callable
from functools import cache
from math import isqrt
from typing import Any, cast

from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError, TemplateError
from esolangs.generation.helpers import (
    check_table_text,
    mark_runs,
    same_up_to_wrapping,
    unmark,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_program, wrap_program
from esolangs.raster import Raster
from esolangs.registry import (
    LANGUAGES,
    SourceKind,
    render_template,
    resolve,
    template_setters,
)
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_bits, check_flag, check_scale, check_width
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings, dialect_options, effective_settings


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
    if resolve(template.language) != name:
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
    if (
        program is not filled.source
        or settings is not filled.settings
        or filled.language != name
    ):
        filled = ProgramArtifact(program, name, settings)
    return filled
