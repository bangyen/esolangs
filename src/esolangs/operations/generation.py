"""Generate and bind explicit program artifacts."""

from collections.abc import Callable
from dataclasses import replace
from functools import cache
from typing import cast

from esolangs._dialect import DialectSchema, Scalar
from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
    _freeze_span,
)
from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import (
    ArgumentError,
    ProgramError,
    TemplateError,
)
from esolangs.generation._template_replay import TemplateProbes, matches_template
from esolangs.generation.helpers import _validate_truth_table, check_table_text
from esolangs.generation.reflow import _layout_compressed, balance_program, wrap_program
from esolangs.generation.requests import (
    BalanceRequest,
    GeneratedProgram,
    GenerationRequest,
    Options,
    call_backend,
)
from esolangs.generation.template import TemplateLayout
from esolangs.generation.wrap import (
    TokenWrapper,
    balance_character_slots,
    can_balance_template,
    can_wrap_template,
    wrap_character_slots,
)
from esolangs.raster import Raster
from esolangs.registry import (
    SourceKind,
    render_template,
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
    return _generate_checked(
        resolved,
        truth_table,
        options,
        settings,
        width=width,
        balance=balance,
        scale=scale,
        catalog=catalog,
    )


def _generate_checked(
    resolved: str,
    truth_table: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    width: int | None,
    balance: bool,
    scale: int | None,
    catalog: Catalog,
) -> Artifact:
    """Generate after explicit choices have been validated once."""
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
    probes: TemplateProbes | None = None,
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
                probes=probes,
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
    if balance and not backend.balances_natively:
        return _generate_balanced(
            resolved, truth_table, options, settings, catalog=catalog, probes=probes
        )
    width = check_width(width)
    inputs = _validate_truth_table(truth_table)
    backend.check_arity(resolved, inputs)
    fn = backend.generate
    laid_out = balance or (width is not None and backend.layout_width)
    request = GenerationRequest(
        truth_table,
        width if laid_out else None,
        _backend_options(schema, options),
        balance=balance,
    )
    generated = (
        call_backend(fn, request) if probes is None else probes.generate(fn, request)
    )
    if _has_backing_type(generated, TemplateLayout):
        if backend.template is None or lang.runtime.source_kind is SourceKind.RASTER:
            raise ProgramError(
                f"{resolved}'s generator returned an undeclared template"
            )
        generation_width = request.width
        if width is not None and not laid_out and backend.wrap is not None:
            generated = _check_reflow_layout(generated)
            if not can_wrap_template(generated, backend.wrap):
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
            generation_width = width
        return _structured_template(
            generated,
            lang.id,
            resolved,
            inputs,
            settings,
            catalog,
            probes=probes,
            generation_width=generation_width,
        )
    if lang.runtime.source_kind is SourceKind.RASTER:
        if not _has_backing_type(generated, Raster):
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
    if not _has_backing_type(generated, str):
        raise ProgramError(f"{resolved}'s generator did not return text")
    text = str.__str__(generated)
    program = text if laid_out else wrap_program(text, lang.id, width, catalog=catalog)
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
    *,
    probes: TemplateProbes | None = None,
    generation_width: int | None = None,
) -> TemplateArtifact:
    """Preserve the backend's slot positions alongside its rendered source."""
    if not _has_backing_type(layout, TemplateLayout):
        raise ProgramError(f"{name}'s template wrapper did not return slots")
    text = layout.source
    if not _has_backing_type(text, str):
        raise TemplateError("template needs text source and TemplateBindings")
    # A backend-supplied str subclass may carry data its own setter reads.
    if type(text) is not str:
        probes = None
    key = text, inputs
    bindings = probes.bindings.get(key) if probes is not None else None
    if bindings is None:
        text, char, pairs = call_backend(
            render_template, language_id, text, inputs, catalog=catalog
        )
        bindings = TemplateBindings(char=char, setters=pairs)
        if bindings.inputs != inputs:
            raise ProgramError(f"{name}'s template must bind all {inputs} inputs")
        if probes is not None:
            probes.bindings[key] = bindings
    return TemplateArtifact(
        text,
        name,
        bindings,
        settings=settings,
        spans=layout.spans,
        generation_width=generation_width,
    )


def _check_reflow_layout(layout: TemplateLayout) -> TemplateLayout:
    """Validate raw offsets before a wrapper uses them to slice source."""
    if not _has_backing_type(layout.source, str):
        raise TemplateError("template needs text source and TemplateBindings")
    if not _has_backing_type(layout.spans, tuple):
        raise TemplateError("template needs one span per input")
    position, size = 0, str.__len__(layout.source)
    spans = []
    try:
        for span in tuple.__iter__(layout.spans):
            start, end = _freeze_span(span)
            if type(start) is not int or type(end) is not int:
                raise ValueError("template spans must be pairs of offsets")
            if not position <= start <= end <= size:
                raise ValueError(f"invalid template span {(start, end)!r}")
            spans.append((start, end))
            position = end
    except ValueError as error:
        raise TemplateError(str(error)) from error
    return TemplateLayout(layout.source, tuple(spans))


def _generate_balanced(
    name: str,
    truth_table: str,
    options: dict[str, Scalar],
    settings: DialectSettings | None,
    *,
    catalog: Catalog,
    probes: TemplateProbes | None = None,
) -> Artifact:
    """Return ``generate(..., balance=True)``: the default, rebuilt squarest."""
    default = _generate(
        name, truth_table, options, settings, catalog=catalog, probes=probes
    )
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
            if _has_backing_type(result, CompressedText):
                balanced = _freeze_compressed(result)._inherit_limits(source.limits)  # noqa: SLF001
            elif _has_backing_type(result, str) and not lang.runtime.compressed_source:
                balanced_text = str.__str__(result)
                if len(balanced_text) == len(source):
                    offset = 0
                    for chunk in source.chunks():
                        if not balanced_text.startswith(chunk, offset):
                            break
                        offset += len(chunk)
                    else:
                        return default
                balanced = CompressedText.from_chunks(
                    (balanced_text,), limits=source.limits
                )
            else:
                raise ProgramError(f"{name}'s balancer did not return CompressedText")
        return replace(default, source=balanced)
    if isinstance(source, Raster):
        assert isinstance(default, ProgramArtifact)
        if balancer is None:
            return default
        result = call_backend(
            balancer,
            BalanceRequest(truth_table, source, choices),
        )
        if not _has_backing_type(result, Raster):
            raise ProgramError(f"{name}'s balancer did not return a Raster")
        return replace(default, source=result)
    if balancer is not None:
        balance_source: GeneratedProgram = source
        if isinstance(default, TemplateArtifact):
            balance_source = TemplateLayout(default.source, default.spans)
        text = call_backend(
            balancer,
            BalanceRequest(truth_table, balance_source, choices),
        )
        if _has_backing_type(text, TemplateLayout) and isinstance(
            default, TemplateArtifact
        ):
            return _structured_template(
                text,
                lang.id,
                name,
                default.bindings.inputs,
                settings,
                catalog,
                probes=probes,
            )
        if isinstance(default, TemplateArtifact):
            raise ProgramError(f"{name}'s template balancer did not return slots")
        if not _has_backing_type(text, str):
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


def _balance_template(
    template: TemplateArtifact,
    name: str,
    *,
    wrapper: Callable[[str, int], str] | None,
) -> TemplateArtifact:
    """Balance source by moving positional slots with a slot-aware wrapper."""
    layout = TemplateLayout(template.source, template.spans)
    if not can_balance_template(layout, wrapper):
        raise ProgramError(f"{name} requires a slot-aware balancer")
    if isinstance(wrapper, TokenWrapper):
        balanced = call_backend(
            wrapper.balance_template, layout, char=template.bindings.char
        )
    else:
        balanced = balance_character_slots(layout)
    if not _has_backing_type(balanced, TemplateLayout):
        raise ProgramError(f"{name}'s template wrapper did not return slots")
    return replace(template, source=balanced.source, spans=balanced.spans)


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
    probes = TemplateProbes()

    @cache
    def render(width: int | None = None, *, balance: bool = False) -> Artifact:
        return _generate(
            name,
            truth_table,
            options,
            settings,
            width=width,
            balance=balance,
            catalog=catalog,
            probes=probes,
        )

    return matches_template(
        template, name, width=width, catalog=catalog, probes=probes, render=render
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
        width: As for :func:`generate`. Checked replay uses the retained
            generation width if no width is supplied.
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
    settings = effective_settings(name, template, settings, catalog=catalog)
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
    return _fill_checked_template(
        name, template, bits, width=width, settings=settings, catalog=catalog
    )


def _fill_checked_template(
    name: str,
    template: TemplateArtifact,
    bits: list[int],
    *,
    width: int | None,
    settings: DialectSettings | None,
    catalog: Catalog,
) -> ProgramArtifact[str]:
    """Fill and wrap a template after its owner, dialect and row are checked."""
    filled = TemplateArtifact.fill(template, bits)
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
