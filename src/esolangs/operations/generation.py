"""Generate and bind explicit program artifacts."""

from collections.abc import Callable
from dataclasses import replace
from functools import cache
from math import isqrt
from typing import cast

from esolangs._dialect import Scalar
from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError, TemplateError
from esolangs.generation.helpers import check_table_text, same_up_to_wrapping
from esolangs.generation.requests import (
    BalanceRequest,
    GeneratedProgram,
    GenerationRequest,
    Options,
)
from esolangs.generation.template import TemplateLayout
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import (
    TokenWrapper,
    balance_character_slots,
    balance_program,
    wrap_character_slots,
    wrap_chars,
    wrap_program,
)
from esolangs.raster import Raster
from esolangs.registry import (
    SourceKind,
    render_template,
    template_setters,
)
from esolangs.registry._catalog import Catalog
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
    catalog: "Catalog | None" = None,
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
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    options = dialect_options(language, settings, catalog=catalog)
    check_scale(scale)
    check_flag(balance, "balance")
    if scale != 1:
        if (
            catalog.languages[catalog.resolve(language)].runtime.source_kind
            is not SourceKind.RASTER
        ):
            raise with_hint(
                ArgumentError("scale is only supported for raster generators"),
                "omit scale for text languages; apply it only to raster source",
            )
        artifact = cast(
            ProgramArtifact[Raster],
            generate(
                language,
                truth_table,
                width=width,
                balance=balance,
                settings=settings,
                catalog=catalog,
            ),
        )
        return replace(artifact, source=artifact.source.upscaled(scale), scale=scale)
    if balance and width is not None:
        raise with_hint(
            ArgumentError("balance and width are mutually exclusive"),
            (
                "omit width when balance=True, or disable "
                "balance when choosing a fixed width"
            ),
        )
    if balance:
        return _generate_balanced(
            language, truth_table, options, settings, catalog=catalog
        )
    resolved = catalog.resolve(language)
    lang = catalog.languages[resolved]
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
        schema = lang.runtime.dialect_schema
        choices = (schema.defaults if schema is not None else {}) | options
        generated = fn(
            GenerationRequest(
                truth_table,
                width if laid_out else None,
                Options(tuple(choices.items())),
            )
        )
    except EsolangError:
        raise
    except ValueError as error:
        raise ArgumentError(str(error)) from error
    inputs = len(truth_table).bit_length() - 1
    if isinstance(generated, TemplateLayout):
        if width is not None and not laid_out and backend.wrap is not None:
            if backend.wrap is wrap_chars and _character_slots(generated):
                generated = wrap_character_slots(generated, width)
            elif isinstance(backend.wrap, TokenWrapper):
                generated = backend.wrap.wrap_template(generated, width)
            else:
                raise ProgramError(f"{resolved} requires a slot-aware wrapper")
        return _structured_template(
            generated,
            lang.id,
            resolved,
            inputs,
            settings,
            catalog,
        )
    if lang.runtime.source_kind is SourceKind.RASTER:
        if not isinstance(generated, Raster):  # pragma: no cover - registry invariant
            raise ProgramError(f"{resolved}'s generator did not return a Raster")
        return ProgramArtifact(
            generated, resolved, settings, scale=1, input_arity=inputs
        )
    if isinstance(generated, CompressedText):
        return ProgramArtifact(
            generated.wrapped(width), resolved, settings, input_arity=inputs
        )
    slots = str(generated)
    if not lang.parameterized:
        program = (
            slots if laid_out else wrap_program(slots, lang.id, width, catalog=catalog)
        )
        return ProgramArtifact(program, resolved, settings, input_arity=inputs)
    raise ProgramError(f"{resolved}'s template generator did not return slots")


def _backend_options(
    language: str, options: dict[str, Scalar], *, catalog: "Catalog | None" = None
) -> Options:
    """Return complete choices for the selected backend request."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    schema = catalog.languages[catalog.resolve(language)].runtime.dialect_schema
    return Options(
        tuple(((schema.defaults if schema is not None else {}) | options).items())
    )


def _structured_template(
    layout: TemplateLayout,
    language_id: str,
    name: str,
    inputs: int,
    settings: DialectSettings | None,
    catalog: Catalog,
) -> TemplateArtifact:
    """Preserve the backend's slot positions alongside its rendered source."""
    text, char, pairs = render_template(
        language_id, layout.source, inputs, catalog=catalog
    )
    return TemplateArtifact(
        text, name, TemplateBindings(char, pairs), settings, spans=layout.spans
    )


def _generate_balanced(
    language: str,
    truth_table: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    catalog: "Catalog | None" = None,
) -> Artifact:
    """Return ``generate(..., balance=True)``: the default, rebuilt squarest."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    default = generate(language, truth_table, settings=settings, catalog=catalog)
    source = default.source
    inputs = len(truth_table).bit_length() - 1
    name = catalog.resolve(language)
    lang = catalog.languages[name]
    backend = lang.backend
    assert backend is not None  # the default was generated above
    balancer = backend.balance
    if isinstance(source, CompressedText):
        return ProgramArtifact(
            source.wrapped(max(1, isqrt(CELL_ASPECT * len(source)))),
            name,
            settings,
            input_arity=inputs,
        )
    if isinstance(source, Raster):
        if balancer is None:
            return default
        balanced = balancer(
            BalanceRequest(
                truth_table, source, _backend_options(lang.id, options, catalog=catalog)
            )
        )
        if not isinstance(balanced, Raster):
            raise ProgramError(f"{name}'s balancer did not return a Raster")
        return ProgramArtifact(balanced, name, settings, scale=1, input_arity=inputs)
    if balancer is not None:
        balance_source: GeneratedProgram = source
        if isinstance(default, TemplateArtifact) and default.spans is not None:
            balance_source = TemplateLayout(default.source, default.spans)
        text = balancer(
            BalanceRequest(
                truth_table,
                balance_source,
                _backend_options(lang.id, options, catalog=catalog),
            )
        )
        if isinstance(text, TemplateLayout) and isinstance(default, TemplateArtifact):
            return _structured_template(
                text, lang.id, name, default.bindings.inputs, settings, catalog
            )
        if isinstance(default, TemplateArtifact):
            raise ProgramError(f"{name}'s template balancer did not return slots")
        if not isinstance(text, str):
            raise ProgramError(f"{name}'s balancer did not return text")
        return ProgramArtifact(text, name, settings, input_arity=inputs)
    if isinstance(default, TemplateArtifact):
        return _balance_template(
            default,
            name,
            wrapper=None if backend.wrap_balance is not None else backend.wrap,
        )
    return ProgramArtifact(
        balance_program(source, lang.id, catalog=catalog),
        name,
        settings,
        input_arity=inputs,
    )


def _character_slots(layout: TemplateLayout) -> bool:
    """Whether character folding can preserve every input slot."""
    return "\n" not in layout.source and all(
        end == start + 1 for start, end in layout.spans
    )


def _balance_template(
    template: TemplateArtifact,
    name: str,
    *,
    wrapper: Callable[[str, int], str] | None,
) -> TemplateArtifact:
    """Balance source by moving positional slots with a slot-aware wrapper."""
    if template.spans and "\n" not in template.source:
        layout = TemplateLayout(template.source, template.spans)
        if wrapper is wrap_chars and _character_slots(layout):
            balanced = balance_character_slots(layout)
            return replace(template, source=balanced.source, spans=balanced.spans)
        if isinstance(wrapper, TokenWrapper):
            balanced = wrapper.balance_template(layout)
            return replace(template, source=balanced.source, spans=balanced.spans)
    raise ProgramError(f"{name} requires a slot-aware balancer")


def _is_template_for(
    template: TemplateArtifact,
    name: str,
    truth_table: str,
    settings: DialectSettings | None = None,
    *,
    catalog: "Catalog | None" = None,
) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    Compare wrapping using the language's whitespace rules.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    canonical = generate(name, truth_table, settings=settings, catalog=catalog)
    if not isinstance(canonical, TemplateArtifact):
        return False
    bindings = canonical.bindings
    expected = TemplateBindings(
        bindings.char,
        template_setters(
            catalog.languages[name].id,
            template.source,
            bindings.inputs,
            catalog=catalog,
        ),
    )
    if template.bindings != expected:
        return False
    text = template.source
    plain = canonical.source
    if text == plain:
        return True
    backend = catalog.languages[name].backend
    assert backend is not None  # generate above refuses absent backends
    width_aware = backend.layout_width

    @cache
    def layout(width: int) -> str:
        source = generate(
            name, truth_table, width=width, settings=settings, catalog=catalog
        ).source
        if not isinstance(source, str):
            raise TemplateError("template layouts must return text")
        return source

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
    catalog: "Catalog | None" = None,
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
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings = effective_settings(name, template, settings, catalog=catalog)
    dialect_options(name, settings, catalog=catalog)
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
    if not catalog.languages[name].parameterized:
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
    if catalog.resolve(template.language) != name:
        raise TemplateError(f"template belongs to {template.language}, not {name}")
    if truth_table is not None and not _is_template_for(
        template, name, truth_table, settings, catalog=catalog
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
    program = wrap_program(
        filled.source, catalog.languages[name].id, width, catalog=catalog
    )
    if (
        program is not filled.source
        or settings is not filled.settings
        or filled.language != name
    ):
        filled = ProgramArtifact(program, name, settings)
    return filled
