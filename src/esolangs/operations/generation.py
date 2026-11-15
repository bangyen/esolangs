"""Generate and bind explicit program artifacts."""

from collections.abc import Callable
from dataclasses import replace
from functools import cache
from typing import cast

from esolangs._bindings import check_setters, validate_spans
from esolangs._dialect import DialectSchema, Scalar
from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    GeneratorCapError,
    ProgramError,
    TemplateError,
)
from esolangs.generation.helpers import _validate_truth_table, check_table_text
from esolangs.generation.requests import (
    BalanceRequest,
    GeneratedProgram,
    GenerationRequest,
    Options,
    call_backend,
)
from esolangs.generation.template import TemplateLayout, layout_fragments
from esolangs.generation.wrap import (
    TokenWrapper,
    _layout_compressed,
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
from esolangs.runtime._validate import (
    _has_backing_type,
    check_bit_count,
    check_bits,
    check_flag,
    check_scale,
    check_width,
)
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import (
    DialectSettings,
    _settings_for,
    dialect_options,
    effective_settings,
)


def generate(
    language: str,
    truth_table: str,
    *,
    width: int | None = None,
    balance: bool = False,
    scale: int | None = None,
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
        width: A layout request (``describe(language).width_effect``):
            it does nothing where newlines are semantic, and a token longer
            than the width still overruns it.  A template wraps with each run
            kept whole, so every row breaks in the same places.
        balance: Pick the supported layout fitting the smallest on-screen
            square: text minimizes max(columns, 2 * rows), a character cell
            being about twice as tall as wide, then source length, then
            width.  A raster minimizes max(width, height) in pixels, then
            pixel area, then width.  Excludes ``width``.
        scale: Replicate pixels after layout for runtimes supporting raster
            scaling. None and 1 keep the native size.
        settings: Dialect choices from ``describe(language).dialect_settings``.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        TruthTableError: ``truth_table`` is not a binary string of length
            ``2**n``.
        ArgumentError: The language has no Boolean generator (``esolangs list
            --details`` marks it ``int``), or an option is invalid or combined
            with one it excludes (``balance`` with ``width``, a scale above 1
            for a runtime that does not support raster scaling).
        GeneratorCapError: The table exceeds the generator's cap
            (``describe(language).generator_max_inputs`` and
            ``.generator_restrictions``).
        ProgramError: The backend returned an incompatible source type.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    options = dialect_options(language, settings, catalog=catalog)
    resolved = catalog.resolve(language)
    settings = _generation_settings(resolved, options, settings, catalog=catalog)
    return _generate(
        resolved,
        truth_table,
        options,
        settings,
        width=width,
        balance=balance,
        scale=scale,
        catalog=catalog,
    )


def _generation_settings(
    name: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    catalog: Catalog,
) -> DialectSettings | None:
    """Retain all choices used to generate the source, validating added defaults."""
    schema = catalog.languages[name].runtime.dialect_schema
    if schema is not None and (choices := schema.defaults | options) != options:
        return _settings_for(name, choices, catalog=catalog)
    return settings


def _generate(
    resolved: str,
    truth_table: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    width: int | None = None,
    balance: bool = False,
    scale: int | None = None,
    catalog: Catalog,
) -> Artifact:
    """Render with validated dialect choices, including during layout probes."""
    lang = catalog.languages[resolved]
    schema = lang.runtime.dialect_schema
    check_flag(balance, "balance")
    if scale is not None:
        scale = check_scale(scale)
    if scale not in (None, 1):
        if lang.runtime.source_kind is not SourceKind.RASTER:
            raise with_hint(
                ArgumentError("scale is only supported for raster generators"),
                "omit scale for text languages; apply it only to raster source",
            )
        if not lang.runtime.capabilities.supports_scale:
            raise with_hint(
                ArgumentError(f"{resolved} does not support raster scaling"),
                "omit scale or use scale=1 to keep the native size",
            )
        artifact = cast(
            ProgramArtifact[Raster],
            _generate(
                resolved,
                truth_table,
                options,
                settings,
                width=width,
                balance=balance,
                catalog=catalog,
            ),
        )
        # Materialize the base so upscaled() checks the pixel limit now, not
        # at the first pickle, dump or run.
        base = artifact.source
        _ = base.rows
        assert scale is not None
        return replace(artifact, source=base.upscaled(scale), scale=scale)
    if balance and width is not None:
        raise with_hint(
            ArgumentError("balance and width are mutually exclusive"),
            (
                "omit width when balance=True, or disable "
                "balance when choosing a fixed width"
            ),
        )
    backend = lang.backend
    if backend is None:
        # The language reads input but cannot meet the generator's size contract.
        raise ArgumentError(
            f"{resolved} has no boolean generator under this repository's "
            f"generator contracts. `esolangs list --details` marks it 'int'"
        )
    truth_table = check_table_text(truth_table)
    if balance:
        return _generate_balanced(
            resolved, truth_table, options, settings, catalog=catalog
        )
    width = check_width(width)
    inputs = _validate_truth_table(truth_table)
    backend.check_arity(resolved, inputs)
    fn = backend.generate
    laid_out = width is not None and backend.layout_width
    generated = call_backend(
        fn,
        GenerationRequest(
            truth_table,
            width if laid_out else None,
            _backend_options(schema, options),
        ),
    )
    if isinstance(generated, TemplateLayout):
        if backend.template is None or lang.runtime.source_kind is SourceKind.RASTER:
            raise ProgramError(
                f"{resolved}'s generator returned an undeclared template"
            )
        if width is not None and not laid_out and backend.wrap is not None:
            if not _can_wrap_template(generated, backend.wrap):
                raise ProgramError(f"{resolved} requires a slot-aware wrapper")
            if isinstance(backend.wrap, TokenWrapper):
                generated = call_backend(
                    backend.wrap.wrap_template,
                    generated,
                    width,
                    char=backend.template.char,
                )
            else:
                generated = wrap_character_slots(generated, width)
        return _structured_template(
            generated,
            lang.id,
            resolved,
            inputs,
            settings,
            catalog,
        )
    if lang.runtime.source_kind is SourceKind.RASTER:
        if not isinstance(generated, Raster):
            raise ProgramError(f"{resolved}'s generator did not return a Raster")
        return ProgramArtifact(
            generated,
            resolved,
            settings=settings,
            scale=1 if lang.runtime.capabilities.supports_scale else None,
            input_arity=inputs,
        )
    if backend.template is not None:
        raise ProgramError(f"{resolved}'s template generator did not return slots")
    if _has_backing_type(generated, CompressedText):
        return ProgramArtifact(
            generated
            if laid_out
            else _layout_compressed(generated, lang.id, width, catalog=catalog),
            resolved,
            settings=settings,
            input_arity=inputs,
        )
    if not isinstance(generated, str):
        raise ProgramError(f"{resolved}'s generator did not return text")
    program = (
        generated
        if laid_out
        else wrap_program(generated, lang.id, width, catalog=catalog)
    )
    return ProgramArtifact(program, resolved, settings=settings, input_arity=inputs)


def _backend_options(
    schema: DialectSchema | None, options: dict[str, Scalar]
) -> Options:
    """Return complete choices for the selected backend request."""
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
    text, char, pairs = call_backend(
        render_template, language_id, layout.source, inputs, catalog=catalog
    )
    bindings = TemplateBindings(char=char, setters=pairs)
    if bindings.inputs != inputs:
        raise ProgramError(f"{name}'s template must bind all {inputs} inputs")
    return TemplateArtifact(
        text,
        name,
        bindings,
        settings=settings,
        spans=layout.spans,
    )


def _generate_balanced(
    name: str,
    truth_table: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    catalog: Catalog,
) -> Artifact:
    """Return ``generate(..., balance=True)``: the default, rebuilt squarest."""
    default = _generate(name, truth_table, options, settings, catalog=catalog)
    source = default.source
    inputs = len(truth_table).bit_length() - 1
    lang = catalog.languages[name]
    backend = lang.backend
    assert backend is not None  # the default was generated above
    balancer = backend.balance
    choices = _backend_options(lang.runtime.dialect_schema, options)
    if isinstance(source, CompressedText):
        assert isinstance(default, ProgramArtifact)
        if balancer is None:
            balanced = _layout_compressed(
                source, lang.id, balance=True, catalog=catalog
            )
        else:
            result = call_backend(
                balancer,
                BalanceRequest(truth_table, source, choices),
            )
            if not _has_backing_type(result, CompressedText):
                raise ProgramError(f"{name}'s balancer did not return CompressedText")
            balanced = _freeze_compressed(result)._inherit_limits(source.limits)  # noqa: SLF001
        return replace(default, source=balanced)
    if isinstance(source, Raster):
        assert isinstance(default, ProgramArtifact)
        if balancer is None:
            return default
        result = call_backend(
            balancer,
            BalanceRequest(truth_table, source, choices),
        )
        if not isinstance(result, Raster):
            raise ProgramError(f"{name}'s balancer did not return a Raster")
        return replace(default, source=result)
    if balancer is not None:
        balance_source: GeneratedProgram = source
        if isinstance(default, TemplateArtifact) and default.spans is not None:
            balance_source = TemplateLayout(default.source, default.spans)
        text = call_backend(
            balancer,
            BalanceRequest(truth_table, balance_source, choices),
        )
        if isinstance(text, TemplateLayout) and isinstance(default, TemplateArtifact):
            return _structured_template(
                text, lang.id, name, default.bindings.inputs, settings, catalog
            )
        if isinstance(default, TemplateArtifact):
            raise ProgramError(f"{name}'s template balancer did not return slots")
        if not isinstance(text, str):
            raise ProgramError(f"{name}'s balancer did not return text")
        return ProgramArtifact(text, name, settings=settings, input_arity=inputs)
    if isinstance(default, TemplateArtifact):
        return _balance_template(
            default,
            name,
            wrapper=None if backend.wrap_balance is not None else backend.wrap,
        )
    return ProgramArtifact(
        balance_program(source, lang.id, catalog=catalog),
        name,
        settings=settings,
        input_arity=inputs,
    )


def _character_slots(layout: TemplateLayout) -> bool:
    """Whether character folding can preserve every input slot."""
    return "\n" not in layout.source and all(
        end == start + 1 for start, end in layout.spans
    )


def _can_wrap_template(
    layout: TemplateLayout, wrapper: Callable[[str, int], str] | None
) -> bool:
    """Whether the wrapper can lay out this template's slots."""
    return isinstance(wrapper, TokenWrapper) or (
        wrapper is wrap_chars and _character_slots(layout)
    )


def _can_balance_template(
    layout: TemplateLayout, wrapper: Callable[[str, int], str] | None
) -> bool:
    """Whether default balancing can reflow a single line with input slots."""
    return (
        bool(layout.spans)
        and "\n" not in layout.source
        and _can_wrap_template(layout, wrapper)
    )


def _balance_template(
    template: TemplateArtifact,
    name: str,
    *,
    wrapper: Callable[[str, int], str] | None,
) -> TemplateArtifact:
    """Balance source by moving positional slots with a slot-aware wrapper."""
    layout = TemplateLayout(template.source, template.spans or ())
    if not _can_balance_template(layout, wrapper):
        raise ProgramError(f"{name} requires a slot-aware balancer")
    if isinstance(wrapper, TokenWrapper):
        balanced = call_backend(
            wrapper.balance_template, layout, char=template.bindings.char
        )
    else:
        balanced = balance_character_slots(layout)
    return replace(template, source=balanced.source, spans=balanced.spans)


def _matches_width_layout(
    text: str, layout: Callable[[int], str], width: int | None
) -> bool:
    """Compare a requested width and bounded candidates inferred from source."""
    if width is not None and text == layout(width):
        return True
    # A narrow layout can switch representations. Either it or the widest
    # stored line can exceed a backend cap.
    widest = max(map(len, text.splitlines()), default=0)
    for inferred_width in (1, widest) if widest > 1 else (1,):
        try:
            if text == layout(inferred_width):
                return True
        except GeneratorCapError:
            continue
    return False


def _is_template_for(
    template: TemplateArtifact,
    name: str,
    truth_table: str,
    settings: DialectSettings | None,
    *,
    width: int | None,
    catalog: Catalog,
) -> bool:
    """Return whether ``template`` is what ``name`` generates for the table.

    Compare wrapping using the language's whitespace rules, with slots
    spelled in the generator's marker.
    """
    options = {} if settings is None else DialectSettings.options(settings)
    settings = _generation_settings(name, options, settings, catalog=catalog)
    backend = catalog.languages[name].backend
    try:
        canonical = _generate(name, truth_table, options, settings, catalog=catalog)
        default_available = True
    except GeneratorCapError:
        if width is None or backend is None or not backend.layout_width:
            raise
        canonical = _generate(
            name, truth_table, options, settings, width=width, catalog=catalog
        )
        default_available = False
    if not isinstance(canonical, TemplateArtifact):
        return False
    bindings = canonical.bindings
    if len(template.bindings.setters) != bindings.inputs:
        return False
    text = template.source
    if template.bindings.char != bindings.char:
        spans = template.spans
        if spans is None:
            return False
        text = layout_fragments(
            TemplateLayout(text, spans).fragments(), char=bindings.char
        ).source
        try:
            validate_spans(text, bindings.char, template.bindings.setters, spans)
        except ValueError:
            return False
    try:
        expected = check_setters(
            template_setters(
                catalog.languages[name].id, text, bindings.inputs, catalog=catalog
            )
        )
    except EsolangError:
        raise
    except ValueError:
        # A setter extractor can reject a caller-supplied source layout.
        return False
    if template.bindings.setters != expected:
        return False
    plain = canonical.source
    matches_canonical = text == plain
    if matches_canonical or not default_available:
        return matches_canonical
    assert backend is not None  # _generate above refuses absent backends
    assert canonical.spans is not None
    canonical_layout = TemplateLayout(plain, canonical.spans)
    width_aware = backend.layout_width or _can_wrap_template(
        canonical_layout, backend.wrap
    )

    @cache
    def layout(width: int) -> str:
        source = _generate(
            name, truth_table, options, settings, width=width, catalog=catalog
        ).source
        if not isinstance(source, str):
            raise TemplateError("template layouts must return text")
        return source

    if width_aware and _matches_width_layout(text, layout, width):
        return True
    if backend.same_layout is not None:
        matches: object = call_backend(backend.same_layout, text, plain, layout)
        if type(matches) is not bool:
            raise ProgramError(f"{name}'s layout matcher did not return a boolean")
        if matches:
            return True
    if backend.balance is None and (
        backend.wrap_balance is not None
        or not _can_balance_template(canonical_layout, backend.wrap)
    ):
        return False
    try:
        balanced = _generate(
            name, truth_table, options, settings, balance=True, catalog=catalog
        )
    except GeneratorCapError:
        return False
    return (
        isinstance(balanced, TemplateArtifact)
        and text == balanced.source
        and template.spans == balanced.spans
        and template.bindings.setters == balanced.bindings.setters
    )


def _stdin_template_error(name: str) -> TemplateError:
    """Explain how to supply bits to a language that reads them at runtime."""
    return with_hint(
        TemplateError(
            f"{name} reads its inputs rather than embedding them, "
            "so there is nothing to instantiate"
        ),
        "run the generated program with stdin=encode_inputs(language, bits)",
    )


def _raster_template_error(message: str) -> TemplateError:
    """Explain how to supply bits after refusing raster instantiation."""
    return with_hint(
        TemplateError(message),
        "run the raster with stdin=encode_inputs(language, bits)",
    )


def _check_template_bits(
    name: str, bits: list[int] | tuple[int, ...], inputs: int
) -> list[int]:
    """Validate a row before generating or filling its template."""
    values = check_bits(bits, "bits", allow_empty=inputs == 0)
    try:
        check_bit_count(values, inputs, f"{name} template")
    except ArgumentError as error:
        raise with_hint(
            error,
            f"pass exactly {inputs} integer bits to instantiate(), one per input",
        ) from None
    return values


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
    Retained dialect choices follow the filled program. Explicit ``settings``
    can supply choices the template does not retain.

    Args:
        template: The TemplateArtifact returned by :func:`generate` or portable loading.
        bits: One integer 0 or 1 per input.
        width: As for :func:`generate`.
        truth_table: Check whether the layout and setters match that table's
            generated template. The placeholder marker may be relabeled.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        TemplateError: Nothing to fill: the language reads its inputs, the
            template came from another language or table, is a raster, or is
            already filled.
        ArgumentError: A bit is not an integer 0 or 1, ``bits`` does not
            match the template's input count, or an option is invalid.
    """
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings = effective_settings(name, template, settings, catalog=catalog)
    width = check_width(width)
    body = (
        template.source
        if _has_backing_type(template, ProgramArtifact)
        or _has_backing_type(template, TemplateArtifact)
        else template
    )
    if _has_backing_type(body, Raster):
        raise _raster_template_error(
            f"{name} source is a Raster, and raster programs read their "
            "inputs rather than embedding them, so there is nothing to instantiate"
        )
    if not catalog.languages[name].parameterized:
        raise _stdin_template_error(name)
    if not _has_backing_type(template, TemplateArtifact):
        raise with_hint(
            TemplateError(
                "template must be the TemplateArtifact generate() returned, "
                f"got {type(template).__name__}"
            ),
            "retain generate()'s template or restore it with from_json()",
        )
    if resolve_origin(template.language, catalog=catalog) != name:
        raise TemplateError(f"template belongs to {template.language}, not {name}")
    bits = _check_template_bits(name, bits, len(template.bindings.setters))
    if truth_table is not None:
        truth_table = check_table_text(truth_table)
        if not _is_template_for(
            template, name, truth_table, settings, width=width, catalog=catalog
        ):
            raise with_hint(
                TemplateError(
                    f"this is not the template generate({name!r}, {truth_table!r}) "
                    "returns, so filling it would produce a program that "
                    "does not compute that table"
                ),
                "regenerate the template from the intended language and truth table",
            )
    else:
        # With a table, generation validates the effective dialect.
        dialect_options(
            name,
            settings,
            catalog=catalog,
            validate_defaults=True,
            _sparse_validated=True,
        )
    filled = template.fill(bits)
    program = wrap_program(
        filled.source, catalog.languages[name].id, width, catalog=catalog
    )
    if (
        program is not filled.source
        or settings is not filled.settings
        or filled.language != name
    ):
        filled = ProgramArtifact(program, name, settings=settings)
    return filled
