"""Bind input bits to an explicit generated template."""

from functools import cache

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import ArgumentError, TemplateError
from esolangs.generation._template_replay import TemplateProbes, matches_template
from esolangs.generation.helpers import check_table_text
from esolangs.generation.reflow import wrap_program
from esolangs.raster import Raster
from esolangs.registry._catalog import Catalog
from esolangs.runtime._validate import (
    _has_backing_type,
    check_bit_count,
    check_bits,
    check_width,
)
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings, dialect_options, effective_settings


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
    from esolangs.operations.generation import _generate, _generation_settings

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
    TemplateArtifact from :func:`esolangs.generate` retains explicit bindings.
    Retained dialect choices follow the filled program. Explicit ``settings``
    can supply choices the template does not retain.

    Args:
        template: The TemplateArtifact returned by :func:`esolangs.generate` or
            portable loading.
        bits: One integer 0 or 1 per input.
        width: As for :func:`esolangs.generate`. Checked replay uses the retained
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
